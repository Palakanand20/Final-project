# Testing Guide

## Test Types

Wiki Explorer uses three test types, each with a specific purpose:

### Unit Tests

Test a **single function in isolation**. All dependencies are mocked so the test only exercises the logic of that one function.

Example from this codebase: `TestFetchArticle.test_fetch_article_filters_wikipedia_prefix_links` in `tests/test_server.py`. It mocks `requests.get` to return a controlled Wikipedia API response, then asserts that links starting with `Wikipedia:` are absent from the result. `fetch_article` is tested alone — the DB, the server, and the network are all irrelevant.

Use unit tests for: pure logic (parsing, filtering, transformation, BFS traversal).

### Contract Tests

Verify that **API response shapes match what clients expect**. They use a real FastAPI `TestClient` but mock the underlying data sources (Wikipedia API, sometimes `build_graph`).

Example: `TestGraphEndpoint.test_graph_nodes_have_correct_fields` POSTs to the real `/api/graph` route and asserts the returned nodes have `id`, `summary`, `categories`, and `depth`. If the server's response shape changes, this test catches it before a client breaks.

Use contract tests for: every API endpoint that a client depends on.

### Integration Tests

Test **multiple components end-to-end** with a real (temporary) database. No mocking of internal functions — only external Wikipedia calls are still mocked.

Example: `TestIntegration.test_full_save_list_load_cycle` saves a graph, lists all graphs, then loads the saved one by ID. It verifies the complete save→list→load workflow works with real SQLite writes and reads.

Use integration tests for: critical multi-step workflows (save/load, duplicate overwrites, pipeline flows).

---

## Running Tests

```bash
# All tests, verbose
python3 -m pytest tests/ -v

# With coverage report
python3 -m pytest tests/ -v --cov=. --cov-report=term-missing

# Single file
python3 -m pytest tests/test_server.py -v

# Single test
python3 -m pytest tests/test_server.py::TestFetchArticle::test_fetch_article_missing_page_returns_none -v
```

---

## Reading the Coverage Report

After running with `--cov`, you'll see something like:

```
Name                 Stmts   Miss  Cover   Missing
--------------------------------------------------
cli/main.py             96      1    99%   136
client/__init__.py       0      0   100%
client/api.py           26      0   100%
server/__init__.py       0      0   100%
server/app.py          110      1    99%   132
tui/main.py            138      1    99%   195
--------------------------------------------------
TOTAL                  370      3    99%
```

- **Stmts** — total executable lines in the file
- **Miss** — lines that were never executed during the test run
- **Cover** — percentage of statements that ran
- **Missing** — line numbers that were not covered

The three uncovered lines (`cli/main.py:136`, `server/app.py:132`, `tui/main.py:195`) are all `if __name__ == "__main__": main()` guard blocks and an internal `continue` that requires a very specific execution path. These are intentionally not targeted — see "What Is Not Tested" below.

---

## How to Add a New Test

**Step 1: Identify what you're testing.** Is it a single function (unit test), an API endpoint shape (contract test), or a multi-step workflow (integration test)?

**Step 2: Choose the right file.**
- Server logic → `tests/test_server.py`
- Client library → `tests/test_client.py`
- CLI commands → `tests/test_cli.py`
- TUI menus → `tests/test_tui.py`

**Step 3: Write the test.** Every test must have a docstring. Here is a complete worked example — adding a test that verifies `/api/expand` returns the node's title in the `node.id` field:

```python
def test_expand_node_id_matches_article_title(self, client):
    """The node.id in the expand response matches the article's canonical title."""
    mock_article = {
        "title": "Albert Einstein",
        "summary": "German physicist.",
        "categories": ["Scientists"],
        "links": ["Special relativity"],
    }
    with patch("server.app.get_or_fetch", return_value=mock_article):
        response = client.get("/api/expand?title=Albert+Einstein")
    assert response.json()["node"]["id"] == "Albert Einstein"
```

**Step 4: Run it.**
```bash
python3 -m pytest tests/test_server.py::TestExpandEndpoint::test_expand_node_id_matches_article_title -v
```

**Step 5: Check coverage didn't regress.**
```bash
python3 -m pytest tests/ --cov=. --cov-report=term-missing -q
```

---

## How Mocking Works

All tests use `unittest.mock.patch`. Here is a concrete before/after showing why mocking is necessary:

**Without mocking** — this test would make a real Wikipedia HTTP call:
```python
def test_fetch_article_bad():
    from server.app import fetch_article
    result = fetch_article("Black hole")
    # Fails when offline, slow, rate-limited, or Wikipedia is down
    assert result["title"] == "Black hole"
```

**With mocking** — the test controls exactly what the "Wikipedia API" returns:
```python
def test_fetch_article_good():
    from server.app import fetch_article
    fake_response = {
        "query": {
            "pages": {
                "123": {
                    "title": "Black hole",
                    "extract": "A black hole is...",
                    "categories": [{"title": "Category:Astrophysics"}],
                    "links": [{"title": "Albert Einstein"}],
                }
            }
        }
    }
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = fake_response
        mock_get.return_value.raise_for_status = MagicMock()
        result = fetch_article("Black hole")
    assert result["title"] == "Black hole"
    assert "Albert Einstein" in result["links"]
```

`patch("requests.get")` replaces the real `requests.get` function with a `MagicMock` for the duration of the `with` block. When `fetch_article` calls `requests.get(...)`, it gets the mock. After the `with` block, `requests.get` is restored to the real function.

For patching functions that are **imported by name** (e.g., `from client.api import search` in `cli/main.py`), you must patch the name in the importing module's namespace:
```python
# Wrong: patches requests in the requests module — cli.main already has a reference
with patch("client.api.search"):
    ...

# Right: patches the name 'search' as bound in cli.main
with patch("cli.main.search"):
    ...
```

---

## What Is Intentionally Not Tested

**`if __name__ == "__main__"` blocks** — These guard blocks in `cli/main.py` and `tui/main.py` are only executed when the file is run directly (`python3 cli/main.py`). Tests always import the module, so these lines are never reached. They're excluded from coverage expectations because triggering them would require subprocess-level testing that adds fragility without adding value.

**`gui/main.py`** — The GUI requires a display server (X11 or macOS window server). CI environments typically don't have one. GUI code is excluded from coverage via `omit = ["gui/*"]` in `pyproject.toml`. Testing Tkinter widgets is possible with `tkinter.Tk()` mocking but is brittle and platform-dependent.

**The Wikipedia API itself** — We never test that Wikipedia returns a specific response to a specific query. That's Wikipedia's responsibility. Our tests verify that our code handles whatever shape of response we give it, including edge cases like missing pages and network errors.

**Database migration** — There is no migration system; the schema is created fresh with `CREATE TABLE IF NOT EXISTS`. Tests always use a temporary database.
