"""
Wiki Explorer - REST API Server
Fetches Wikipedia articles, stores them in SQLite, and serves a graph API.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import (
    ARTICLE_SUMMARY_MAX_CHARS,
    FILTERED_LINK_PREFIXES,
    GRAPH_EXPAND_MAX_LINKS,
    GRAPH_MAX_DEPTH,
    GRAPH_MAX_LINKS_PER_NODE,
    WIKI_API_URL,
    WIKI_CATEGORIES_LIMIT,
    WIKI_LINKS_LIMIT,
    WIKI_SEARCH_LIMIT,
    WIKI_SEARCH_TIMEOUT_SECONDS,
    WIKI_TIMEOUT_SECONDS,
    WIKI_USER_AGENT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("wiki_explorer")

START_TIME = time.time()

DB_PATH = os.path.join(os.path.dirname(__file__), "wiki.db")
WIKI_API = WIKI_API_URL  # alias kept for test compatibility
WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")

_local = threading.local()


# ── Database ──────────────────────────────────────────────────────────────────


def get_db() -> sqlite3.Connection:
    """Return a thread-local SQLite connection, creating one if needed."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return cast(sqlite3.Connection, _local.conn)  # threading.local attrs are untyped


def init_db() -> None:
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                title TEXT PRIMARY KEY,
                summary TEXT,
                categories TEXT
            );
            CREATE TABLE IF NOT EXISTS links (
                source TEXT,
                target TEXT,
                PRIMARY KEY (source, target)
            );
            CREATE TABLE IF NOT EXISTS saved_graphs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                root TEXT,
                depth INTEGER,
                data TEXT
            );
        """)
    logger.info("Database initialised at %s", DB_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise on startup, close DB on shutdown."""
    init_db()
    logger.info("Wiki Explorer server started")
    yield
    if hasattr(_local, "conn") and _local.conn:
        _local.conn.close()
        logger.info("Database connection closed")


# CORS is intentionally open (allow_origins=["*"]) because this is a
# single-user local tool. The server only listens on 127.0.0.1 (loopback),
# so external hosts cannot reach it regardless of CORS policy.
app = FastAPI(title="Wiki Explorer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Wikipedia helpers ─────────────────────────────────────────────────────────


def fetch_article(title: str) -> dict[str, Any] | None:
    logger.info("Fetching article from Wikipedia: %s", title)
    params: dict[str, Any] = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts|categories|links",
        "exintro": True,
        "explaintext": True,
        "cllimit": WIKI_CATEGORIES_LIMIT,
        "pllimit": WIKI_LINKS_LIMIT,
        "redirects": True,
    }
    headers = {"User-Agent": WIKI_USER_AGENT}
    r = requests.get(WIKI_API_URL, params=params, headers=headers, timeout=WIKI_TIMEOUT_SECONDS)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    page = next(iter(pages.values()))
    if "missing" in page:
        logger.warning("Article not found: %s", title)
        return None
    real_title = page.get("title", title)
    summary = page.get("extract", "")[:ARTICLE_SUMMARY_MAX_CHARS]
    cats = [c["title"].replace("Category:", "") for c in page.get("categories", [])]
    links = [
        lnk["title"]
        for lnk in page.get("links", [])
        if not lnk["title"].startswith(FILTERED_LINK_PREFIXES)
    ]
    logger.debug("Fetched article: %s (%d links, %d categories)", real_title, len(links), len(cats))
    return {"title": real_title, "summary": summary, "categories": cats, "links": links}


def get_or_fetch(title: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM articles WHERE title=?", (title,)).fetchone()
        if row:
            logger.debug("Cache hit: %s", title)
            cached_links = [
                r["target"]
                for r in conn.execute(
                    "SELECT target FROM links WHERE source=?", (title,)
                ).fetchall()
            ]
            return {
                "title": row["title"],
                "summary": row["summary"],
                "categories": json.loads(row["categories"]),
                "links": cached_links,
            }
    logger.info("Cache miss, fetching: %s", title)
    data = fetch_article(title)
    if not data:
        return None
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO articles (title, summary, categories) VALUES (?,?,?)",
            (data["title"], data["summary"], json.dumps(data["categories"])),
        )
        conn.executemany(
            "INSERT OR IGNORE INTO links (source, target) VALUES (?,?)",
            [(data["title"], t) for t in data["links"]],
        )
    return data


def build_graph(
    root: str, depth: int = 1, max_links: int = GRAPH_MAX_LINKS_PER_NODE
) -> dict[str, Any]:
    logger.info("Building graph: root=%s depth=%d", root, depth)
    nodes: dict[str, Any] = {}
    edges: set[tuple[str, str]] = set()
    queue: list[tuple[str, int]] = [(root, 0)]
    visited: set[str] = set()
    while queue:
        title, level = queue.pop(0)
        if title in visited or level > depth:
            continue
        visited.add(title)
        data = get_or_fetch(title)
        if not data:
            continue
        nodes[data["title"]] = {
            "id": data["title"],
            "summary": data["summary"],
            "categories": data["categories"],
            "depth": level,
        }
        for link in data["links"][:max_links]:
            edges.add((data["title"], link))
            if level < depth and link not in visited:
                queue.append((link, level + 1))
    logger.info("Graph complete: %d nodes, %d edges", len(nodes), len(edges))
    return {
        "nodes": list(nodes.values()),
        "edges": [{"source": s, "target": t} for s, t in edges if t in nodes],
    }


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/api/search", summary="Search Wikipedia titles", tags=["Wikipedia"])
def search(q: str = "") -> list[str]:
    """
    Autocomplete search using the Wikipedia OpenSearch API.

    Returns up to 8 article titles matching the query string.
    Returns an empty list when `q` is blank or the Wikipedia API is unreachable.
    """
    if not q:
        return []
    if len(q) > 200:
        return []
    headers = {"User-Agent": WIKI_USER_AGENT}
    search_params: dict[str, Any] = {
        "action": "opensearch",
        "search": q,
        "limit": WIKI_SEARCH_LIMIT,
        "format": "json",
    }
    r = requests.get(
        WIKI_API_URL,
        params=search_params,
        headers=headers,
        timeout=WIKI_SEARCH_TIMEOUT_SECONDS,
    )
    return r.json()[1] if r.ok else []  # type: ignore[no-any-return]


@app.get("/api/graph", summary="Build article graph", tags=["Graph"])
def graph(title: str, depth: int = 1) -> dict[str, Any]:
    """
    Build a BFS graph starting from the given Wikipedia article title.

    Fetches each article from the cache or Wikipedia, then follows links
    up to `depth` hops (capped at 3). Returns `{nodes, edges}` where each
    node contains `{id, summary, categories, depth}`.
    """
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="title must not be empty")
    if len(title) > 300:
        raise HTTPException(status_code=400, detail="title too long (max 300 characters)")
    depth = max(0, min(depth, GRAPH_MAX_DEPTH))
    title = title.strip()
    return build_graph(title, depth=depth)


@app.get("/api/expand", summary="Expand a single node", tags=["Graph"])
def expand(title: str) -> dict[str, Any]:
    """
    Return a single article node plus its outgoing links.

    Useful for lazily adding neighbours to an existing graph without
    rebuilding it from scratch. Returns 404 if the article is not found.
    Response shape: `{node: {id, summary, categories}, links: [str, ...]}`.
    """
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="title must not be empty")
    if len(title) > 300:
        raise HTTPException(status_code=400, detail="title too long (max 300 characters)")
    title = title.strip()
    data = get_or_fetch(title)
    if not data:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "node": {"id": data["title"], "summary": data["summary"], "categories": data["categories"]},
        "links": data["links"][:GRAPH_EXPAND_MAX_LINKS],
    }


@app.get("/api/graphs", summary="List saved graphs", tags=["Saved Graphs"])
def list_graphs() -> list[dict[str, Any]]:
    """
    Return metadata for all saved graphs, newest first.

    Each item contains `{id, name, root, depth}`. The heavy `data` field
    is intentionally excluded — use `GET /api/graphs/{id}` to retrieve it.
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, root, depth FROM saved_graphs ORDER BY rowid DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/graphs", summary="Save a graph", tags=["Saved Graphs"])
def save_graph(body: dict[str, Any]) -> dict[str, Any]:
    """
    Persist a graph to the database.

    Required fields: `name` (string, unique), `root` (article title),
    `depth` (integer, defaults to 1), `data` (the full `{nodes, edges}` object).
    Saving with a duplicate name overwrites the previous entry.
    Returns `{ok: true}` on success, 400 if `name` or `root` is empty.
    """
    name = str(body.get("name", "")).strip()
    root = str(body.get("root", "")).strip()
    depth = body.get("depth", 1)
    data = body.get("data", {})
    if not name or not root:
        raise HTTPException(status_code=400, detail="name and root required")
    if len(name) > 200:
        raise HTTPException(status_code=400, detail="name too long (max 200 characters)")
    if not isinstance(depth, int) or depth < 0:
        depth = 1
    logger.info("Saving graph: name=%s root=%s", name, root)
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO saved_graphs (name, root, depth, data) VALUES (?,?,?,?)",
            (name, root, depth, json.dumps(data)),
        )
    return {"ok": True}


@app.get("/api/graphs/{gid}", summary="Load a saved graph", tags=["Saved Graphs"])
def load_graph(gid: int) -> dict[str, Any]:
    """
    Retrieve a single saved graph by its integer ID.

    Returns the full row including the `data` field (parsed from JSON).
    Returns 404 if no graph with the given ID exists.
    """
    with get_db() as conn:
        row = conn.execute("SELECT * FROM saved_graphs WHERE id=?", (gid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    result = dict(row)
    result["data"] = json.loads(result["data"])
    return result


@app.get("/api/health", summary="Health check", tags=["Meta"])
def health() -> dict[str, Any]:
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


# Serve web frontend
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
