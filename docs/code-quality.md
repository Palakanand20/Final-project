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
