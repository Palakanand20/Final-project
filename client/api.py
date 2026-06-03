"""
Shared API client used by CLI, TUI, and GUI.
"""

import httpx

BASE_URL = "http://localhost:8001"


def search(q: str) -> list:
    r = httpx.get(f"{BASE_URL}/api/search", params={"q": q}, timeout=10)
    r.raise_for_status()
    return r.json()


def get_graph(title: str, depth: int = 1) -> dict:
    r = httpx.get(f"{BASE_URL}/api/graph", params={"title": title, "depth": depth}, timeout=30)
    r.raise_for_status()
    return r.json()


def expand_node(title: str) -> dict:
    r = httpx.get(f"{BASE_URL}/api/expand", params={"title": title}, timeout=10)
    r.raise_for_status()
    return r.json()


def list_graphs() -> list:
    r = httpx.get(f"{BASE_URL}/api/graphs", timeout=10)
    r.raise_for_status()
    return r.json()


def save_graph(name: str, root: str, depth: int, data: dict) -> dict:
    r = httpx.post(f"{BASE_URL}/api/graphs",
                   json={"name": name, "root": root, "depth": depth, "data": data},
                   timeout=10)
    r.raise_for_status()
    return r.json()


def load_graph(gid: int) -> dict:
    r = httpx.get(f"{BASE_URL}/api/graphs/{gid}", timeout=10)
    r.raise_for_status()
    return r.json()
