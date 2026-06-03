"""
Wiki Explorer - REST API Server
Fetches Wikipedia articles, stores them in SQLite, and serves a graph API.
"""

import json
import os
import sqlite3

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Wiki Explorer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "wiki.db")
WIKI_API = "https://en.wikipedia.org/w/api.php"
WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
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


init_db()


# ── Wikipedia helpers ─────────────────────────────────────────────────────────

def fetch_article(title: str):
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts|categories|links",
        "exintro": True,
        "explaintext": True,
        "cllimit": 10,
        "pllimit": 50,
        "redirects": True,
    }
    headers = {"User-Agent": "WikiExplorer/1.0 (educational project; palakanand912@gmail.com)"}
    r = requests.get(WIKI_API, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    page = next(iter(pages.values()))
    if "missing" in page:
        return None
    real_title = page.get("title", title)
    summary = page.get("extract", "")[:500]
    cats = [c["title"].replace("Category:", "") for c in page.get("categories", [])]
    links = [
        l["title"] for l in page.get("links", [])
        if not l["title"].startswith(("Wikipedia:", "Help:", "Template:", "Portal:"))
    ]
    return {"title": real_title, "summary": summary, "categories": cats, "links": links}


def get_or_fetch(title: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM articles WHERE title=?", (title,)).fetchone()
        if row:
            cached_links = [
                r["target"] for r in
                conn.execute("SELECT target FROM links WHERE source=?", (title,)).fetchall()
            ]
            return {
                "title": row["title"],
                "summary": row["summary"],
                "categories": json.loads(row["categories"]),
                "links": cached_links,
            }
    data = fetch_article(title)
    if not data:
        return None
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO articles (title, summary, categories) VALUES (?,?,?)",
            (data["title"], data["summary"], json.dumps(data["categories"]))
        )
        conn.executemany(
            "INSERT OR IGNORE INTO links (source, target) VALUES (?,?)",
            [(data["title"], t) for t in data["links"]]
        )
    return data


def build_graph(root: str, depth: int = 1, max_links: int = 15):
    nodes = {}
    edges = set()
    queue = [(root, 0)]
    visited = set()
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
    return {
        "nodes": list(nodes.values()),
        "edges": [{"source": s, "target": t} for s, t in edges if t in nodes],
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/search")
def search(q: str = ""):
    if not q:
        return []
    headers = {"User-Agent": "WikiExplorer/1.0 (educational project; palakanand912@gmail.com)"}
    r = requests.get(WIKI_API, params={
        "action": "opensearch", "search": q, "limit": 8, "format": "json"
    }, headers=headers, timeout=5)
    return r.json()[1] if r.ok else []


@app.get("/api/graph")
def graph(title: str, depth: int = 1):
    depth = min(depth, 3)
    return build_graph(title, depth=depth)


@app.get("/api/expand")
def expand(title: str):
    data = get_or_fetch(title)
    if not data:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "node": {"id": data["title"], "summary": data["summary"], "categories": data["categories"]},
        "links": data["links"][:20],
    }


@app.get("/api/graphs")
def list_graphs():
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, root, depth FROM saved_graphs ORDER BY rowid DESC").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/graphs")
def save_graph(body: dict):
    name = body.get("name", "").strip()
    root = body.get("root", "").strip()
    depth = body.get("depth", 1)
    data = body.get("data", {})
    if not name or not root:
        raise HTTPException(status_code=400, detail="name and root required")
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO saved_graphs (name, root, depth, data) VALUES (?,?,?,?)",
            (name, root, depth, json.dumps(data))
        )
    return {"ok": True}


@app.get("/api/graphs/{gid}")
def load_graph(gid: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM saved_graphs WHERE id=?", (gid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    result = dict(row)
    result["data"] = json.loads(result["data"])
    return result


# Serve web frontend
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
