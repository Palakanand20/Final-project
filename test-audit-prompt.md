# Test Audit + Documentation Super-Prompt

Copy everything below the line and run it in Claude Code from `~/Desktop/wiki-explorer`.

---

You are performing a **test audit** and **documentation expansion** on the Wiki Explorer project at `~/Desktop/wiki-explorer`. Work in that directory. Do not ask questions — complete all tasks and commit at the end.

---

## PHASE 1 — TEST LEGITIMACY AUDIT

Read every test file: `tests/test_server.py`, `tests/test_client.py`, `tests/test_cli.py`, `tests/test_tui.py`.

For each test, evaluate it against ALL of these audit criteria:

### Audit Criteria

**A. Reverse-engineering red flags — a test FAILS this if it:**
- Asserts the exact internal implementation (e.g., checks which mock was called with which internal SQL string rather than the observable output)
- Passes only because it mirrors the implementation — e.g., it constructs the expected value the same way the production code does instead of using a hardcoded expected value
- Has a meaningless assertion like `assert result is not None` or `assert True` that would pass even if the function returned garbage
- Tests nothing observable — e.g., calls a function, ignores the return value, asserts only that no exception was raised when the function's real contract is about what it returns
- Has an assertion that is trivially true regardless of what the function does

**B. Quality failures — a test FAILS this if it:**
- Has no docstring
- Has a docstring that restates the test name without explaining what behaviour is expected and why
- Tests the wrong module (e.g., a "client test" that imports from `server.app`)
- Has a mock that is set up but never used by any assertion or by the code under test
- Patches a symbol that doesn't exist in the actual import path used by the module under test (the classic "patch the wrong namespace" bug)
- Has an assertion that could never fail (e.g., `assert len(result) >= 0`)

**C. Correctness failures — a test FAILS this if it:**
- Would fail on the correct implementation (a false positive)
- Would pass on a clearly broken implementation (a false negative)
- Asserts a field name, status code, or return shape that doesn't match what the actual endpoint/function returns

### What to do with each failing test

- **Minor issues** (missing or weak docstring, unused mock): fix in place. Rewrite the docstring to clearly state the expected behavior and why it matters. Remove unused mocks.
- **Reverse-engineered or trivially-true assertions**: rewrite the test so it uses a hardcoded, independently-derived expected value. For example, if the test previously did `assert result == build_the_same_way_as_production(input)`, replace with `assert result == <literal expected value>`.
- **Wrong namespace patch**: fix the patch target to match the actual import in the module under test.
- **Tests that cannot be salvaged**: replace the test body entirely with a test that covers the same scenario but tests observable behavior (inputs → outputs) rather than implementation internals.
- **Tests that are near-duplicates of another test with no additional coverage value**: consolidate into one well-named test and replace the other with a new test covering a different edge case.

### After auditing, produce a file `docs/test-audit.md` with:

```markdown
# Test Audit Report

## Summary
- Total tests audited: N
- Tests with issues found: N
- Tests rewritten: N
- Tests fixed in place: N
- Net new tests added: N
- Final test count: N

## Issues Found and Fixed

For each issue:
### <TestClass>::<test_name>
**File:** tests/test_X.py
**Issue type:** [reverse-engineered | trivially-true | wrong-namespace | weak-docstring | unused-mock | near-duplicate | false-positive | false-negative]
**Problem:** <one sentence describing what was wrong>
**Fix:** <one sentence describing what was changed>

## Tests That Passed Audit (No Changes Needed)
List them in a table: | Class | Test | Verdict |

## Coverage After Audit
Paste the full output of:
  python3 -m pytest tests/ -v --cov=. --cov-report=term-missing -q
```

---

## PHASE 2 — EXPAND THE TEST SUITE

After the audit, add net-new tests to fill any coverage gaps and to cover scenarios the audit revealed were missing. Target: **≥ 125 total tests, ≥ 95% coverage**.

Focus areas for new tests (check actual coverage misses first):

**server/app.py gaps:**
- `fetch_article` with a response that has zero links (empty links list)
- `fetch_article` with categories list that has non-`Category:` prefixed entries (should strip prefix only from `Category:` entries)
- `get_or_fetch` when the DB raises an exception mid-read (simulate `sqlite3.OperationalError`)
- `build_graph` with `depth=0` (should return only the root node, no edges)
- `build_graph` with `max_links=0` (no edges should be produced)
- `build_graph` where a link appears as both a source and a target (cycle detection)
- `POST /api/graphs` with missing `data` field (should still save with empty data)
- `GET /api/graphs/{gid}` with `gid=0` (should 404)
- `GET /api/search` with a query that returns an empty list from Wikipedia

**client/api.py gaps:**
- `get_graph` with `depth=0`
- `save_graph` with `depth=0`
- `load_graph` raises on non-integer `gid` (or verifies URL construction with string coercion)

**cli/main.py gaps:**
- `explore` when the graph has nodes but zero edges
- `list` when the server returns an empty list (prints a message, doesn't crash)
- `load` when the server returns a graph with zero nodes

**tui/main.py gaps:**
- Menu choice `4` (load) when `list_graphs` returns an empty list (should print a message, not crash)
- Menu choice `1` (explore) when `get_graph` returns a graph with zero edges (still prints node list)

All new tests must have docstrings. All new tests must use hardcoded expected values.

---

## PHASE 3 — DOCUMENTATION EXPANSION

Write or expand the following markdown files. Every file must be standalone — a reader who hasn't seen the codebase should understand it.

### `docs/decisions.md` — Architecture Decision Records (ADRs)

Write one ADR per design decision, using this format for each:

```markdown
## ADR-N: <Title>
**Status:** Accepted
**Date:** 2025
**Context:** <Why this decision needed to be made — what problem existed>
**Decision:** <What was decided>
**Consequences:** <Trade-offs, what gets easier, what gets harder>
```

Cover at minimum:
- ADR-1: Choice of FastAPI over Flask
- ADR-2: SQLite as the cache store
- ADR-3: BFS with a visited set for graph traversal
- ADR-4: Filtering namespace-prefixed links (Wikipedia:, Help:, Template:, Portal:)
- ADR-5: Truncating article summaries to 500 characters
- ADR-6: `INSERT OR REPLACE` on articles vs `INSERT OR IGNORE` on links
- ADR-7: Separating client interfaces (CLI, TUI, GUI, Web) behind a shared `client/api.py`
- ADR-8: Serving the web frontend as FastAPI static files instead of a separate dev server

### `docs/data-model.md` — Data Model Reference

Document every table in `server/wiki.db`:
- Purpose of the table
- Column-by-column description (type, constraints, what it stores, nullability)
- How rows are created / updated / never deleted
- How tables relate to each other (with an ASCII diagram)
- Example rows (3–5 rows per table, realistic values)

### `docs/contributing.md` — Contributor Guide

Cover:
- How to set up a local dev environment (reference `docs/setup.md` for install steps, don't repeat them)
- Coding conventions: naming, docstrings (every function and test must have one), type hints (encouraged, not required)
- How to add a new API endpoint (step-by-step: route, client method, CLI subcommand, test)
- How to add a new client interface (what it must implement to be consistent with existing interfaces)
- Test conventions: which file, which class, which test type, required docstring format
- How to run the full quality gate before opening a PR: `pytest --cov`, check `docs/test-audit.md`
- Branch and commit message conventions

### `docs/endpoints.md` — Endpoint Behavior Specification (separate from api.md)

For each of the 6 endpoints, write a behavior spec (not just parameter docs — that's `docs/api.md`):
- **Normal path**: what happens step by step in the server code
- **Edge cases**: all known edge cases and what the server returns for each
- **Error cases**: all HTTP error responses, conditions that trigger them, response body shape
- **Performance notes**: which calls are cached, which hit Wikipedia
- **Client usage**: which `client/api.py` function maps to this endpoint

### `docs/graph-algorithm.md` — BFS Algorithm Walkthrough

Document `build_graph()` in depth:
- Plain English description of the BFS algorithm
- Step-by-step walkthrough with a concrete example (root="Black hole", depth=1, max_links=3)
  - Show the queue state after each iteration
  - Show which nodes get added, which edges get added
  - Show why visited tracking prevents infinite loops
- Edge filtering: why edges where the target is not in `nodes` are excluded
- Complexity analysis: time and space complexity as a function of depth and max_links
- Limitations and known edge cases (cycles, missing pages, depth cap of 3)

### `docs/test-strategy.md` — Test Strategy Document

Write a comprehensive test strategy covering:
- Testing philosophy for this codebase (what we test, what we don't, why)
- The three test types with decision rules for which to use (expand beyond what's in testing.md)
- Mock discipline: what is always mocked (Wikipedia API, sometimes SQLite), what is never mocked (our own pure logic), why
- Coverage policy: which modules are included, which are excluded (`gui/`), why
- Flakiness prevention: why every test that touches the DB uses a temp DB, why Wikipedia is always mocked
- How to interpret a test failure: is it a test bug or a production bug? Decision tree.
- Known gaps: what the suite intentionally doesn't cover and why that's an accepted risk

### Update `docs/testing.md`

Add a section at the bottom:
```markdown
## Test Audit

All tests in this suite have been audited for legitimacy. See [docs/test-audit.md](test-audit.md) for the full audit report including a list of issues found and fixed.
```

### Update `README.md`

Add a "Documentation" section after the Quick Start section listing all docs files with one-line descriptions:

```markdown
## Documentation

| File | Description |
|------|-------------|
| [docs/setup.md](docs/setup.md) | Installation and running each interface |
| [docs/architecture.md](docs/architecture.md) | Component overview, data flow, SQLite schema |
| [docs/api.md](docs/api.md) | REST API reference with curl examples |
| [docs/testing.md](docs/testing.md) | Test types, how to add tests, coverage guide |
| [docs/test-audit.md](docs/test-audit.md) | Test audit report |
| [docs/test-strategy.md](docs/test-strategy.md) | Testing philosophy and strategy |
| [docs/data-model.md](docs/data-model.md) | SQLite schema and data model |
| [docs/graph-algorithm.md](docs/graph-algorithm.md) | BFS algorithm walkthrough |
| [docs/endpoints.md](docs/endpoints.md) | Endpoint behavior specifications |
| [docs/decisions.md](docs/decisions.md) | Architecture decision records |
| [docs/contributing.md](docs/contributing.md) | Contributor guide |
```

---

## PHASE 4 — FINAL VERIFICATION

Run the full test suite and confirm ≥ 95% coverage:

```bash
cd ~/Desktop/wiki-explorer
python3 -m pytest tests/ -v --cov=. --cov-report=term-missing
```

If coverage is below 95%, add tests until it is met. Do not mark the audit as complete until this passes.

Then run a sanity check to confirm no test is trivially passing:

```bash
# This should show all tests discovered
python3 -m pytest tests/ --collect-only -q
```

---

## PHASE 5 — COMMIT AND PUSH

```bash
cd ~/Desktop/wiki-explorer
git add -A
git commit -m "Test audit, expanded docs suite, and coverage improvements

- Audited all 154 tests for reverse-engineering and legitimacy
- Fixed issues: wrong-namespace patches, trivially-true assertions, weak docstrings
- Added net-new tests targeting coverage gaps
- Added docs/test-audit.md, docs/test-strategy.md, docs/data-model.md
- Added docs/graph-algorithm.md, docs/endpoints.md, docs/decisions.md, docs/contributing.md
- Updated README.md with full docs index
- Final coverage: 95%+"
git push
```

If `git push` is rejected, run `git push --force`.

---

**You are done when:**
1. `python3 -m pytest tests/ -v --cov=. --cov-report=term-missing` exits 0 with ≥ 95% total coverage
2. `docs/test-audit.md` exists and lists every issue found (or confirms no issues)
3. All 7 new docs files exist and are non-empty
4. `README.md` has the Documentation table
5. Everything is committed and pushed to GitHub
