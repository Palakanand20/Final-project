# Architecture Cleanup Super-Prompt

Copy everything below the line and run it in Claude Code from `~/Desktop/wiki-explorer`.

---

You are performing a **production-grade architecture cleanup** of the Wiki Explorer project at `~/Desktop/wiki-explorer`. Work in that directory. Do not ask questions — complete all tasks and commit at the end.

Read these files before starting so you understand the full codebase:
- `server/app.py`
- `client/api.py`
- `cli/main.py`
- `tui/main.py`
- `gui/main.py`
- `pyproject.toml`
- All files in `tests/`

---

## PHASE 1 — CONFIGURATION FILE

Create `config.py` in the project root with all magic numbers and constants extracted from the codebase:

```python
"""
Central configuration for Wiki Explorer.
All tuneable values live here so they can be changed in one place.
"""

# Server
SERVER_HOST: str = "127.0.0.1"
SERVER_PORT: int = 8001

# Wikipedia API
WIKI_API_URL: str = "https://en.wikipedia.org/w/api.php"
WIKI_USER_AGENT: str = "WikiExplorer/1.0 (educational project; palakanand912@gmail.com)"
WIKI_TIMEOUT_SECONDS: int = 10
WIKI_SEARCH_TIMEOUT_SECONDS: int = 5
WIKI_SEARCH_LIMIT: int = 8
WIKI_CATEGORIES_LIMIT: int = 10
WIKI_LINKS_LIMIT: int = 50

# Graph construction
GRAPH_MAX_DEPTH: int = 3
GRAPH_MAX_LINKS_PER_NODE: int = 15
GRAPH_EXPAND_MAX_LINKS: int = 20

# Article caching
ARTICLE_SUMMARY_MAX_CHARS: int = 500

# Client
CLIENT_BASE_URL: str = f"http://{SERVER_HOST}:{SERVER_PORT}"
CLIENT_TIMEOUT_SECONDS: int = 30

# Link namespace prefixes to filter out (navigational, not conceptual)
FILTERED_LINK_PREFIXES: tuple[str, ...] = (
    "Wikipedia:", "Help:", "Template:", "Portal:",
    "File:", "Category:", "Special:",
)
```

Then update every file that hardcodes any of these values to import from `config` instead:
- `server/app.py`: import `WIKI_API_URL`, `WIKI_USER_AGENT`, `WIKI_TIMEOUT_SECONDS`, `WIKI_SEARCH_TIMEOUT_SECONDS`, `WIKI_SEARCH_LIMIT`, `WIKI_CATEGORIES_LIMIT`, `WIKI_LINKS_LIMIT`, `GRAPH_MAX_DEPTH`, `GRAPH_MAX_LINKS_PER_NODE`, `GRAPH_EXPAND_MAX_LINKS`, `ARTICLE_SUMMARY_MAX_CHARS`, `FILTERED_LINK_PREFIXES`
- `client/api.py`: import `CLIENT_BASE_URL`, `CLIENT_TIMEOUT_SECONDS`
- After updating, verify the code still runs by importing each module: `python3 -c "import server.app; import client.api"`

---

## PHASE 2 — STRUCTURED LOGGING

Add logging to `server/app.py` using Python's standard `logging` module. Do NOT use `print()` for any server-side diagnostics.

At the top of `server/app.py`, after imports, add:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("wiki_explorer")
```

Add log calls at these points:
- `fetch_article`: `logger.info("Fetching article from Wikipedia: %s", title)` before the request; `logger.warning("Article not found: %s", title)` when `"missing" in page`; `logger.debug("Fetched article: %s (%d links, %d categories)", real_title, len(links), len(cats))`
- `get_or_fetch`: `logger.debug("Cache hit: %s", title)` on DB hit; `logger.info("Cache miss, fetching: %s", title)` on miss
- `build_graph`: `logger.info("Building graph: root=%s depth=%d", root, depth)` at start; `logger.info("Graph complete: %d nodes, %d edges", len(nodes), len(edges))` at end
- `save_graph` route: `logger.info("Saving graph: name=%s root=%s", name, root)`
- `init_db`: `logger.info("Database initialised at %s", DB_PATH)`

---

## PHASE 3 — INPUT VALIDATION

### In `server/app.py`:

1. **`/api/graph`** — Add validation before calling `build_graph`:
   ```python
   if not title or not title.strip():
       raise HTTPException(status_code=400, detail="title must not be empty")
   if len(title) > 300:
       raise HTTPException(status_code=400, detail="title too long (max 300 characters)")
   depth = max(0, min(depth, GRAPH_MAX_DEPTH))  # clamp, never raise
   title = title.strip()
   ```

2. **`/api/expand`** — Add:
   ```python
   if not title or not title.strip():
       raise HTTPException(status_code=400, detail="title must not be empty")
   if len(title) > 300:
       raise HTTPException(status_code=400, detail="title too long (max 300 characters)")
   title = title.strip()
   ```

3. **`/api/search`** — Add:
   ```python
   if len(q) > 200:
       return []  # silently ignore absurdly long queries
   ```

4. **`POST /api/graphs`** — Strengthen existing validation:
   ```python
   if len(name) > 200:
       raise HTTPException(status_code=400, detail="name too long (max 200 characters)")
   if not isinstance(depth, int) or depth < 0:
       depth = 1
   ```

### CORS — document the intentional `allow_origins=["*"]`:

Add a comment above the CORS middleware:
```python
# CORS is intentionally open (allow_origins=["*"]) because this is a
# single-user local tool. The server only listens on 127.0.0.1 (loopback),
# so external hosts cannot reach it regardless of CORS policy.
```

---

## PHASE 4 — HEALTH CHECK ENDPOINT

Add a `GET /api/health` endpoint to `server/app.py`. It must:
- Check DB connectivity (run `SELECT 1` against the DB)
- Return a structured response

```python
import time

START_TIME = time.time()

@app.get("/api/health", summary="Health check", tags=["Meta"])
def health():
    """
    Returns server health status.

    Checks database connectivity and returns uptime.
    Response: {status, uptime_seconds, db_ok, version}
    """
    db_ok = False
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "db_ok": db_ok,
        "version": "1.0.0",
    }
```

Also add `START_TIME = time.time()` near the top of `server/app.py` (after imports, before `init_db()`).

---

## PHASE 5 — DATABASE CONNECTION CLEANUP

The current `get_db()` opens a new connection on every call. Improve it:

1. Add a module-level `threading.local()` for thread-safe connection reuse:

```python
import threading

_local = threading.local()

def get_db() -> sqlite3.Connection:
    """Return a thread-local SQLite connection, creating one if needed."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn
```

2. Add a FastAPI lifespan context manager for graceful shutdown:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise on startup, close DB on shutdown."""
    init_db()
    logger.info("Wiki Explorer server started")
    yield
    if hasattr(_local, "conn") and _local.conn:
        _local.conn.close()
        logger.info("Database connection closed")

app = FastAPI(title="Wiki Explorer API", lifespan=lifespan)
```

3. Remove the bare `init_db()` call that was at module level (it's now inside the lifespan).

4. Keep `init_db()` callable standalone (needed by tests) — just don't call it at module level anymore. Tests that need the DB should call `init_db()` explicitly in their setup, or use their existing temp-DB fixtures.

**Important:** After this change, run the tests to ensure nothing broke. If tests fail because `init_db()` is no longer called at import time, add `init_db()` calls to the test fixtures that need them. Do not remove test coverage to make tests pass.

---

## PHASE 6 — TYPE ANNOTATIONS

Add full type annotations to every function in `server/app.py`, `client/api.py`, `cli/main.py`, and `tui/main.py`.

### `server/app.py` function signatures (add return types and param types):

```python
def get_db() -> sqlite3.Connection: ...
def init_db() -> None: ...
def fetch_article(title: str) -> dict | None: ...
def get_or_fetch(title: str) -> dict | None: ...
def build_graph(root: str, depth: int = 1, max_links: int = GRAPH_MAX_LINKS_PER_NODE) -> dict: ...
```

For route functions, FastAPI already validates types from annotations — add them anyway for clarity:
```python
def search(q: str = "") -> list[str]: ...
def graph(title: str, depth: int = 1) -> dict: ...
def expand(title: str) -> dict: ...
def list_graphs() -> list[dict]: ...
def save_graph(body: dict) -> dict: ...
def load_graph(gid: int) -> dict: ...
def health() -> dict: ...
```

### `client/api.py` — add types to all 6 functions:
```python
def search(q: str) -> list[str]: ...
def get_graph(title: str, depth: int = 1) -> dict: ...
def expand_node(title: str) -> dict: ...
def list_graphs() -> list[dict]: ...
def save_graph(name: str, root: str, depth: int, data: dict) -> dict: ...
def load_graph(gid: int) -> dict: ...
```

Add `from __future__ import annotations` at the top of each file for forward-reference support.

---

## PHASE 7 — LINTING WITH RUFF

Add `ruff` to the project and configure it in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "UP",  # pyupgrade
]
ignore = [
    "E501",  # line too long — ruff format handles this
    "B008",  # do not perform function calls in default arguments (FastAPI pattern)
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["F401", "F811"]  # allow unused imports and redefinitions in tests
```

Install ruff and run it:
```bash
pip install ruff --break-system-packages
ruff check . --fix
ruff format .
```

Fix any remaining issues that `--fix` didn't auto-resolve. Do not suppress errors with `# noqa` unless there is a genuine reason (document it inline).

---

## PHASE 8 — MYPY TYPE CHECKING

Add mypy configuration to `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.11"
strict = false
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
exclude = ["gui/", "tests/"]

[[tool.mypy.overrides]]
module = ["server.app", "client.api"]
disallow_untyped_defs = true
warn_return_any = true
```

Install mypy and run it:
```bash
pip install mypy --break-system-packages
python3 -m mypy server/app.py client/api.py
```

Fix all mypy errors in `server/app.py` and `client/api.py`. For `cli/main.py` and `tui/main.py`, fix any errors that are straightforward; leave a `# type: ignore[<code>]` comment with explanation for anything that would require major refactoring.

---

## PHASE 9 — GITHUB ACTIONS CI PIPELINE

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["main"]

jobs:
  test:
    name: Tests + Coverage
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install fastapi uvicorn requests rich httpx pytest pytest-cov ruff mypy

      - name: Lint with ruff
        run: |
          ruff check .
          ruff format --check .

      - name: Type check with mypy
        run: |
          python -m mypy server/app.py client/api.py

      - name: Run tests with coverage
        run: |
          python -m pytest tests/ -v --cov=. --cov-report=term-missing --cov-fail-under=90

      - name: Upload coverage report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: .coverage
```

Also add `ruff` and `mypy` to the dependencies list in `pyproject.toml`:

```toml
dependencies = [
    "fastapi",
    "uvicorn",
    "requests",
    "rich",
    "httpx",
    "pytest",
    "pytest-cov",
    "ruff",
    "mypy",
]
```

---

## PHASE 10 — UPDATE DOCUMENTATION

### Create `docs/code-quality.md`:

```markdown
# Code Quality

## Tools

| Tool | Purpose | Config |
|------|---------|--------|
| ruff | Linting and formatting | `[tool.ruff]` in `pyproject.toml` |
| mypy | Static type checking | `[tool.mypy]` in `pyproject.toml` |
| pytest-cov | Coverage measurement | `[tool.coverage.*]` in `pyproject.toml` |

## Running Locally

```bash
# Lint and format
ruff check .
ruff format .

# Type check
python3 -m mypy server/app.py client/api.py

# Tests with coverage
python3 -m pytest tests/ -v --cov=. --cov-report=term-missing

# All quality gates in one shot
ruff check . && ruff format --check . && python3 -m mypy server/app.py client/api.py && python3 -m pytest tests/ --cov=. --cov-fail-under=90 -q
```

## CI

Every push to `main` and every pull request triggers the CI pipeline (`.github/workflows/ci.yml`), which runs all three quality gates. A failing lint or type check blocks the merge.

## Coverage Policy

- Minimum: 90% total
- Target: 95%+
- Excluded: `gui/` (requires display server), `*/test_*`, `*/conftest*`
- Intentionally uncovered: `if __name__ == "__main__"` guard blocks

## Configuration Notes

- `ruff` line length is 100 (wider than PEP 8's 79 to accommodate FastAPI decorator patterns)
- `mypy` is set to `strict = false` with targeted strictness on `server/app.py` and `client/api.py` — the most critical modules
- `B008` (function calls in defaults) is ignored because FastAPI's `Depends()` pattern requires it
```

### Update `docs/architecture.md`:

Add a section at the bottom:

```markdown
## Configuration

All tuneable constants live in `config.py` at the project root. No magic numbers appear in application code. Import from `config` to use them:

```python
from config import GRAPH_MAX_DEPTH, ARTICLE_SUMMARY_MAX_CHARS
```

See the file for the full list and their documented purpose.

## Logging

The server uses Python's standard `logging` module (logger name: `wiki_explorer`). Log levels:
- `INFO`: Wikipedia fetches, cache misses, graph completion, server start/stop
- `DEBUG`: Cache hits, per-article fetch details
- `WARNING`: Missing Wikipedia articles

To increase verbosity, set `level=logging.DEBUG` in `server/app.py`.

## Health Check

`GET /api/health` returns server status, DB connectivity, uptime, and version. It never raises an HTTP error — a degraded state is reported in the response body.
```

### Update `README.md`:

Add a "Code Quality" badge section near the top (after the title, before the description):

```markdown
[![CI](https://github.com/Palakanand20/Final-project/actions/workflows/ci.yml/badge.svg)](https://github.com/Palakanand20/Final-project/actions/workflows/ci.yml)
```

Add a "Quality Gates" section after the Documentation section:

```markdown
## Quality Gates

```bash
# All checks in one command
ruff check . && ruff format --check . \
  && python3 -m mypy server/app.py client/api.py \
  && python3 -m pytest tests/ --cov=. --cov-fail-under=90 -q
```

See [docs/code-quality.md](docs/code-quality.md) for details.
```

---

## PHASE 11 — FINAL VERIFICATION

Run every quality gate in sequence. Fix any failures before proceeding.

```bash
cd ~/Desktop/wiki-explorer

# 1. Lint
ruff check .

# 2. Format check
ruff format --check .

# 3. Type check
python3 -m mypy server/app.py client/api.py

# 4. Full test suite with coverage
python3 -m pytest tests/ -v --cov=. --cov-report=term-missing

# 5. Confirm health endpoint works (server must not be running)
python3 -c "
from fastapi.testclient import TestClient
from server.app import app
client = TestClient(app)
r = client.get('/api/health')
print(r.json())
assert r.json()['status'] in ('ok', 'degraded')
print('Health check: PASSED')
"

# 6. Confirm config imports cleanly
python3 -c "import config; print('Config loaded:', vars(config))"
```

Do not move to commit until all 6 checks pass.

---

## PHASE 12 — COMMIT AND PUSH

```bash
cd ~/Desktop/wiki-explorer
git add -A
git commit -m "Architecture cleanup: config, logging, types, linting, CI, health endpoint

- Extracted all magic numbers into config.py
- Added structured logging throughout server/app.py
- Added input validation to /api/graph, /api/expand, /api/search, POST /api/graphs
- Added GET /api/health endpoint (DB check + uptime)
- Improved DB connection management with thread-local reuse
- Added FastAPI lifespan handler for graceful shutdown
- Added full type annotations to server/app.py and client/api.py
- Configured ruff (lint + format) and mypy (type check)
- Added GitHub Actions CI pipeline (.github/workflows/ci.yml)
- Added docs/code-quality.md
- Updated docs/architecture.md with config, logging, health sections
- Updated README.md with CI badge and quality gates section"
git push
```

If `git push` is rejected, run `git push --force`.

---

**You are done when:**
1. `ruff check .` exits 0
2. `ruff format --check .` exits 0
3. `python3 -m mypy server/app.py client/api.py` exits 0
4. `python3 -m pytest tests/ --cov=. --cov-fail-under=90 -q` exits 0
5. `GET /api/health` returns `{"status": "ok", ...}` via TestClient
6. `config.py` exists and is imported by `server/app.py` and `client/api.py`
7. `.github/workflows/ci.yml` exists
8. `docs/code-quality.md` exists
9. Everything is committed and pushed to GitHub
