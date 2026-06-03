# Architecture

## Overview

Wiki Explorer follows a **client-server architecture**. A single server process owns all the data and exposes it via a REST API. Multiple client interfaces connect to that API independently.

```
Wikipedia API
     │
     ▼
┌─────────────────────────────┐
│         Server              │
│  FastAPI + SQLite cache     │
│  REST API on :8001          │
└─────────┬───────────────────┘
          │ HTTP
    ┌─────┼──────────────┐
    ▼     ▼              ▼
  Web    CLI            TUI / GUI
(browser) (terminal)  (desktop)
```

## Components

### Server (`server/app.py`)
The heart of the application. It:
- Fetches articles from the Wikipedia API
- Caches them in a local SQLite database so repeated lookups are instant
- Builds graph data (nodes + edges) from article links
- Exposes everything via a REST API built with FastAPI

### Client (`client/api.py`)
A shared Python module used by the CLI, TUI, and GUI. Instead of each interface making raw HTTP calls, they all import from `client/api.py`. This means if the API URL ever changes, you only update one file.

### Web (`web/index.html`)
A single HTML file served directly by the server. Uses D3.js to render an interactive force-directed graph in the browser. No build step required.

### CLI (`cli/main.py`)
A command-line tool for quick lookups from the terminal. Uses `argparse` and `rich` for colored output.

### TUI (`tui/main.py`)
A terminal user interface with menus, tables, and tree views. Built with the `rich` library.

### GUI (`gui/main.py`)
A desktop window built with Python's built-in `tkinter`. Shows the graph as a visual canvas with draggable nodes.

## Data Flow

1. User enters a topic in any interface
2. Interface calls `client/api.py` (or the web frontend calls the API directly)
3. Server checks SQLite cache — if found, returns immediately
4. If not cached, server fetches from Wikipedia API and stores in SQLite
5. Server builds the graph and returns `{nodes, edges}` as JSON
6. Interface renders the graph

## See Also

- `docs/architecture.mmd` — Mermaid diagram of the component relationships
- `docs/testing.md` — Testing plan and test structure
