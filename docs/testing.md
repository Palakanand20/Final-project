# Testing Plan

## Overview

Wiki Explorer uses three types of tests, organized by scope and purpose.

## Test Types

### Unit Tests
Test a single function in isolation. External dependencies (Wikipedia API, database, HTTP calls) are replaced with **mocks** — fake objects that return predictable data. This makes tests fast and reliable.

**Example:** `TestFetchArticle.test_fetch_article_returns_dict` — calls `fetch_article()` with a mocked HTTP response and checks that the result has the right keys.

**When to use:** Testing pure logic — parsing, filtering, data transformation.

### Contract Tests
Test that the API returns responses in the exact shape that clients expect. These verify the "contract" between the server and its clients — if the shape changes, the contract test fails before any client breaks.

**Example:** `TestAPIContracts.test_graph_response_shape` — checks that `/api/graph` always returns `{nodes: [...], edges: [...]}`.

**When to use:** Any API endpoint that clients depend on.

### Integration Tests
Test multiple components working together end-to-end. No mocks — real database, real API calls within the app.

**Example:** `TestIntegration.test_save_and_load_graph` — saves a graph via the API, then loads it back and verifies the data matches.

**When to use:** Critical workflows that span multiple components.

## Test Files

| File | Component | Test Types |
|------|-----------|------------|
| `tests/test_server.py` | Server | Unit, Contract, Integration |
| `tests/test_client.py` | Client library | Unit |

## Running Tests

```bash
python3 -m pytest tests/ -v
```

Expected output: all tests pass in under 5 seconds (no real network calls needed).

## Test Coverage by Component

| Component | Covered |
|-----------|---------|
| `fetch_article()` | Unit |
| `get_or_fetch()` caching | Unit |
| `build_graph()` | Unit |
| `GET /api/search` | Contract |
| `GET /api/graph` | Contract |
| `GET /api/graphs` | Contract |
| `POST /api/graphs` | Contract |
| `GET /api/graphs/{id}` | Contract |
| Save + load cycle | Integration |
| Duplicate name handling | Integration |
| `client.api.search` | Unit |
| `client.api.get_graph` | Unit |
| `client.api.save_graph` | Unit |
| `client.api.list_graphs` | Unit |
| `client.api.load_graph` | Unit |
