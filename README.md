# Wiki Explorer

A multi-interface tool for exploring how Wikipedia articles connect to each other. Enter any topic and see the graph of related articles — then drill down, save, and revisit interesting knowledge maps.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [File Tree](#file-tree)
- [Quick Start](#quick-start)
- [Running the Interfaces](#running-the-interfaces)
  - [Web UI](#web-ui)
  - [CLI](#cli)
  - [TUI](#tui)
  - [GUI](#gui)
- [API Reference](#api-reference)
- [Testing](#testing)
- [How It Works](#how-it-works)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Client Interfaces                    │
│                                                          │
│   Web (D3.js)   CLI (argparse)   TUI (Rich)   GUI (Tk)  │
└──────────┬──────────────┬──────────────┬────────────────┘
           │              │              │
           │     ┌────────▼──────────────▼──────┐
           │     │      client/api.py            │
           │     │  (shared Python HTTP client)  │
           │     └────────────────┬──────────────┘
           │                      │
           └──────────────────────▼
                    ┌─────────────────────┐
                    │   FastAPI Server     │
                    │   :8001              │
                    │                     │
                    │  ┌───────────────┐  │
                    │  │   SQLite DB   │  │
                    │  │  (wiki.db)    │  │
                    │  └───────────────┘  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Wikipedia API      │
                    │ en.wikipedia.org     │
                    └─────────────────────┘
```

One FastAPI server handles caching and graph building. Four independent client interfaces all talk to it — the web UI directly via `fetch`, the CLI/TUI/GUI via the shared `client/api.py` module.

---

## File Tree

```
wiki-explorer/
├── server/
│   ├── app.py          # FastAPI server: Wikipedia fetch, SQLite cache, graph API
│   └── wiki.db         # SQLite database (auto-created on first run)
├── client/
│   └── api.py          # Shared Python API client used by CLI, TUI, GUI
├── cli/
│   └── main.py         # Command-line interface (argparse + ANSI colours)
├── tui/
│   └── main.py         # Terminal UI (Rich library, menu-driven)
├── gui/
│   └── main.py         # Desktop GUI (Tkinter, draggable canvas)
├── web/
│   └── index.html      # Single-file browser UI (D3.js force graph, no build step)
├── tests/
│   ├── conftest.py     # Shared fixtures and helpers
│   ├── test_server.py  # 67 server unit/contract/integration tests
│   ├── test_client.py  # 30 client library unit tests
│   ├── test_cli.py     # 28 CLI unit tests
│   └── test_tui.py     # 27 TUI unit tests
├── docs/
│   ├── api.md          # Full API reference
│   ├── architecture.md # Deep architecture documentation
│   ├── testing.md      # Testing guide
│   └── setup.md        # Standalone setup guide
└── pyproject.toml      # Project metadata, dependencies, pytest/coverage config
```

---

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url> && cd wiki-explorer

# 2. Create and activate a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install fastapi uvicorn requests rich httpx pytest pytest-cov

# 4. Start the server
python3 -m uvicorn server.app:app --reload --port 8001

# 5. Open the web UI
open http://localhost:8001
```

---

## Running the Interfaces

### Web UI

```bash
python3 -m uvicorn server.app:app --reload --port 8001
# then open http://localhost:8001 in your browser
```

Type a topic in the search box, pick depth (1–3), and click **Explore**. Nodes are draggable; hover for summaries; click **Expand** on any node to add its neighbours. Save named graphs to revisit later.

### CLI

```bash
# Search for articles
python3 cli/main.py search "Nikola Tesla"

# Build and display a graph (depth 1–3)
python3 cli/main.py explore "Black hole" --depth 2

# List all saved graphs
python3 cli/main.py list

# Load a saved graph by ID
python3 cli/main.py load 1
```

Example output:
```
Exploring: Black hole  (depth=1)

Nodes: 12   Edges: 11

-- Root ----------------------------------------
  * Black hole
      A black hole is a region of spacetime where gravity is so strong...

-- Depth 1 -------------------------------------
  * Albert Einstein
  * General relativity
  ...
```

### TUI

```bash
python3 tui/main.py
```

An interactive menu opens in the terminal. Use numbers to navigate: 1=Explore, 2=Search, 3=View saved, 4=Load saved, q=Quit.

### GUI

```bash
python3 gui/main.py
```

Opens a Tkinter window with a search bar and an interactive canvas. Nodes are draggable; hover for tooltips; Save/Load buttons persist graphs.

---

## API Reference

| Method | Path | Params | Response | Description |
|--------|------|--------|----------|-------------|
| GET | `/api/search` | `q` (str) | `["Title", ...]` | Wikipedia OpenSearch autocomplete |
| GET | `/api/graph` | `title` (str), `depth` (int, 1–3) | `{nodes, edges}` | BFS graph from root article |
| GET | `/api/expand` | `title` (str) | `{node, links}` | Fetch one node and its outgoing links |
| GET | `/api/graphs` | — | `[{id, name, root, depth}, ...]` | List saved graphs (newest first) |
| POST | `/api/graphs` | body: `{name, root, depth, data}` | `{ok: true}` | Save a graph |
| GET | `/api/graphs/{id}` | — | `{id, name, root, depth, data}` | Load a saved graph by ID |

Full documentation with example `curl` commands and response schemas: [docs/api.md](docs/api.md)

Interactive docs (Swagger UI) are also available at `http://localhost:8001/docs` while the server is running.

---

## Testing

```bash
# Run the full test suite with coverage
python3 -m pytest tests/ -v --cov=. --cov-report=term-missing
```

Expected output:
```
154 passed in ~2s
TOTAL  370  3  99%
```

The suite has **154 tests** across four files covering unit, contract, and integration scenarios. No real Wikipedia API calls are made — all network calls are mocked with `unittest.mock.patch`.

See [docs/testing.md](docs/testing.md) for a full explanation of the test structure, how to add new tests, and how to read the coverage report.

---

## How It Works

1. **Fetch** — When a topic is requested, `fetch_article()` calls the Wikipedia API (`action=query`) with `prop=extracts|categories|links`. Namespace-prefixed links (`Wikipedia:`, `Help:`, `Template:`, `Portal:`) are filtered out. The extract is truncated to 500 characters.

2. **Cache** — `get_or_fetch()` checks the SQLite `articles` table first. On a cache miss it calls `fetch_article()`, then writes the result to `articles` and `links` tables. Subsequent requests for the same title skip the network entirely.

3. **Graph** — `build_graph()` runs a BFS starting from the root article, fetching each article up to `depth` hops away (max 15 links per node). It returns `{nodes, edges}` where edges only include pairs where both endpoints are in the fetched node set.

4. **Render** — The web UI uses D3.js force simulation to lay out nodes. The CLI/TUI print coloured ASCII trees. The GUI draws nodes on a Tkinter canvas in concentric rings by depth.
