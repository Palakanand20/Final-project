# Architecture

## Overview

Wiki Explorer follows a **client-server architecture**. A single FastAPI server process owns all data, caches Wikipedia articles, and exposes a REST API. Four independent client interfaces connect to that API — they share no code with each other except through `client/api.py`.

The design makes it easy to add new interfaces (e.g., a Jupyter notebook, a Slack bot) without touching the server, and to swap the server (e.g., replace SQLite with Postgres) without touching any client.

---

## Components

### Server (`server/app.py`)

The server does three things:

1. **Fetch from Wikipedia** — `fetch_article(title)` calls the Wikipedia API with `action=query`, requesting the article extract, categories, and links in one round-trip. It filters out namespace-prefixed links (`Wikipedia:`, `Help:`, `Template:`, `Portal:`) since those are navigational, not conceptual. The extract is truncated to 500 characters to keep the API responses small.

2. **Cache in SQLite** — `get_or_fetch(title)` wraps `fetch_article` with a check against the local database. Cache hits never touch Wikipedia. This is the key performance win: a depth-2 graph typically requires 100+ Wikipedia fetches on the first load but zero on the second.

3. **Build graphs** — `build_graph(root, depth, max_links)` runs a BFS from the root article, calling `get_or_fetch` for each article it discovers. It caps expansion at `max_links=15` per node and `depth` levels deep (3 maximum). Visited tracking prevents infinite loops on circular links. The returned `{nodes, edges}` only includes edges whose both endpoints are in the fetched node set.

The server also serves the web UI as static files mounted at `/`.

### Client (`client/api.py`)

A thin Python module wrapping six `httpx` calls. It exists purely to avoid copy-pasting the same HTTP calls in three different Python interfaces (CLI, TUI, GUI). Every function calls `raise_for_status()` so callers get an exception on any HTTP error without having to check status codes themselves.

### Web (`web/index.html`)

A single self-contained HTML file — no build step, no npm, no bundler. It uses:
- **D3.js** force simulation to position nodes in a physics-based layout
- Vanilla `fetch` for all API calls
- Real-time search autocomplete with a 250ms debounce
- Node drag (D3 drag), hover tooltips, and a category filter dropdown

The web UI is the most feature-rich interface: it supports expanding individual nodes, filtering by category, and saving/loading from the sidebar.

### CLI (`cli/main.py`)

Uses Python's `argparse` for subcommands (`search`, `explore`, `list`, `load`) and ANSI escape codes for coloured output. No dependencies beyond the standard library plus `client/api.py`. Errors on server unavailability print a `uvicorn` hint to stderr and exit with code 1.

### TUI (`tui/main.py`)

A Rich-powered REPL loop. Rich handles table/tree rendering and the `Prompt.ask` input. The menu covers all four API operations plus a save workflow after exploring. All errors are caught and printed inline rather than crashing the loop.

### GUI (`gui/main.py`)

A Tkinter application with a canvas-based node graph. Nodes are positioned in concentric rings by depth (root at centre), coloured by depth level. Nodes are draggable — the canvas redraws edges in real time during drag. Hover tooltips show summaries and categories.

---

## Data Flow (Numbered)

1. User enters a topic in any interface.
2. Interface calls `client/api.py` (or `fetch` in web) → `GET /api/graph?title=X&depth=N`.
3. Server's `graph()` route calls `build_graph(X, depth=N)`.
4. `build_graph` initialises a BFS queue with `[(X, 0)]`.
5. For each `(title, level)` in the queue, it calls `get_or_fetch(title)`.
6. `get_or_fetch` queries the `articles` SQLite table.
   - **Cache hit**: returns stored `{title, summary, categories}` plus links from the `links` table.
   - **Cache miss**: calls `fetch_article(title)`, stores the result, returns it.
7. `build_graph` adds the article to `nodes`, adds its links to `edges`, and (if `level < depth`) enqueues each linked title at `level+1`.
8. After BFS completes, edges are filtered to only include pairs where both nodes were fetched.
9. `{nodes, edges}` is returned as JSON.
10. The interface renders the graph.

---

## SQLite Schema

### `articles`

| Column | Type | Constraint | Purpose |
|--------|------|------------|---------|
| `title` | TEXT | PRIMARY KEY | Wikipedia article title (exact match) |
| `summary` | TEXT | | First 500 chars of the article extract |
| `categories` | TEXT | | JSON array of category names (prefix stripped) |

### `links`

| Column | Type | Constraint | Purpose |
|--------|------|------------|---------|
| `source` | TEXT | part of PK | Article that contains the link |
| `target` | TEXT | part of PK | Title of the linked article |

The composite primary key `(source, target)` prevents duplicate edges. `INSERT OR IGNORE` is used on writes so re-caching an article never raises an error.

### `saved_graphs`

| Column | Type | Constraint | Purpose |
|--------|------|------------|---------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Stable ID for loading |
| `name` | TEXT | UNIQUE | Human-readable name; duplicates overwrite via `INSERT OR REPLACE` |
| `root` | TEXT | | Root article title for display |
| `depth` | INTEGER | | Depth used to build the graph |
| `data` | TEXT | | Full `{nodes, edges}` object serialised as JSON |

---

## Design Decisions

**Why FastAPI?** Auto-generated Swagger docs (`/docs`), built-in request validation via type annotations, async-ready if needed, and minimal boilerplate. The alternative would have been Flask, which lacks the built-in validation and OpenAPI generation.

**Why SQLite?** Zero-config, file-based, perfect for a single-user desktop tool. The entire cache is one file (`server/wiki.db`) that can be deleted to clear the cache. The trade-off is no concurrent writes — acceptable here since the server is single-threaded.

**How caching works and its trade-offs:**
- `articles` rows are never evicted. This means stale data (Wikipedia edits Wikipedia won't be reflected). The trade-off is predictable, fast repeat queries.
- Links are stored as separate rows in `links` rather than a JSON column. This makes it possible to query "what does article X link to?" without deserializing. The trade-off is two writes per article (one to `articles`, one batch to `links`).
- `INSERT OR REPLACE` on `articles` and `INSERT OR IGNORE` on `links` means re-fetching an article updates its summary/categories but preserves existing link rows (avoiding duplicate-key errors).

**How D3.js builds the graph:**
- D3 `forceSimulation` runs a physics engine in the browser. Each node has repulsive charge (`-300`), links have a rest length (`110px`), and a centering force keeps the graph visible. The simulation runs until kinetic energy drops below a threshold, then stops — the user can then drag nodes manually.
- Node radius is 18px for the root (depth=0) and 10px for others.
- Colours encode depth: blue=0, green=1, yellow=2, red=3+.
