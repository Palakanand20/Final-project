"""
Shared API client used by CLI, TUI, and GUI.
"""

from __future__ import annotations

import httpx

from config import CLIENT_BASE_URL, CLIENT_TIMEOUT_SECONDS

BASE_URL = CLIENT_BASE_URL  # alias kept for test compatibility


def search(q: str) -> list[str]:
    r = httpx.get(f"{BASE_URL}/api/search", params={"q": q}, timeout=CLIENT_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()  # type: ignore[no-any-return]


def get_graph(title: str, depth: int = 1) -> dict[str, object]:
    r = httpx.get(
        f"{BASE_URL}/api/graph",
        params={"title": title, "depth": depth},
        timeout=CLIENT_TIMEOUT_SECONDS,
    )
    r.raise_for_status()
    return r.json()  # type: ignore[no-any-return]


def expand_node(title: str) -> dict[str, object]:
    r = httpx.get(f"{BASE_URL}/api/expand", params={"title": title}, timeout=CLIENT_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()  # type: ignore[no-any-return]


def list_graphs() -> list[dict[str, object]]:
    r = httpx.get(f"{BASE_URL}/api/graphs", timeout=CLIENT_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()  # type: ignore[no-any-return]


def save_graph(name: str, root: str, depth: int, data: dict[str, object]) -> dict[str, object]:
    r = httpx.post(
        f"{BASE_URL}/api/graphs",
        json={"name": name, "root": root, "depth": depth, "data": data},
        timeout=CLIENT_TIMEOUT_SECONDS,
    )
    r.raise_for_status()
    return r.json()  # type: ignore[no-any-return]


def load_graph(gid: int) -> dict[str, object]:
    r = httpx.get(f"{BASE_URL}/api/graphs/{gid}", timeout=CLIENT_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()  # type: ignore[no-any-return]
