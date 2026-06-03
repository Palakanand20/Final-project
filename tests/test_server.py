"""
Server tests — unit, contract, and integration tests for the REST API.

Unit tests:    test the server functions in isolation (no real Wikipedia calls)
Contract tests: test the API response shapes match what clients expect
Integration tests: test the full stack with a real running server
"""

import json
import os
import sys
import sqlite3
import tempfile
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Use a temporary database for every test."""
    db_path = str(tmp_path / "test_wiki.db")
    monkeypatch.setattr("server.app.DB_PATH", db_path)
    import server.app as app_module
    app_module.DB_PATH = db_path
    app_module.init_db()
    yield db_path


@pytest.fixture
def client(temp_db):
    from fastapi.testclient import TestClient
    from server.app import app
    return TestClient(app)


MOCK_ARTICLE = {
    "title": "Black hole",
    "summary": "A black hole is a region of spacetime.",
    "categories": ["Astrophysics", "General relativity"],
    "links": ["Albert Einstein", "General relativity", "Gravitational collapse"],
}


# ── Unit Tests ────────────────────────────────────────────────────────────────

class TestFetchArticle:
    """Unit tests for the Wikipedia fetch helper."""

    def test_fetch_article_returns_dict(self):
        """fetch_article returns a dict with expected keys."""
        from server.app import fetch_article
        mock_response = {
            "query": {
                "pages": {
                    "123": {
                        "title": "Black hole",
                        "extract": "A black hole is a region of spacetime.",
                        "categories": [{"title": "Category:Astrophysics"}],
                        "links": [{"title": "Albert Einstein"}, {"title": "Wikipedia:Test"}],
                    }
                }
            }
        }
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.raise_for_status = MagicMock()
            result = fetch_article("Black hole")

        assert result["title"] == "Black hole"
        assert "Albert Einstein" in result["links"]
        assert "Wikipedia:Test" not in result["links"]  # filtered out
        assert "Astrophysics" in result["categories"]

    def test_fetch_article_missing_page(self):
        """fetch_article returns None for missing pages."""
        from server.app import fetch_article
        mock_response = {
            "query": {"pages": {"-1": {"missing": True, "title": "Nonexistent"}}}
        }
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.raise_for_status = MagicMock()
            result = fetch_article("Nonexistent")
        assert result is None


class TestDatabase:
    """Unit tests for database caching."""

    def test_get_or_fetch_caches_article(self, temp_db):
        """get_or_fetch stores article in DB and returns from cache on second call."""
        from server.app import get_or_fetch
        with patch("server.app.fetch_article", return_value=MOCK_ARTICLE):
            result1 = get_or_fetch("Black hole")
            result2 = get_or_fetch("Black hole")

        assert result1["title"] == "Black hole"
        assert result2["title"] == "Black hole"

    def test_get_or_fetch_returns_none_for_missing(self, temp_db):
        """get_or_fetch returns None when article not found."""
        from server.app import get_or_fetch
        with patch("server.app.fetch_article", return_value=None):
            result = get_or_fetch("Totally Fake Article 99999")
        assert result is None


class TestBuildGraph:
    """Unit tests for graph construction."""

    def test_build_graph_returns_nodes_and_edges(self, temp_db):
        """build_graph returns dict with nodes and edges lists."""
        from server.app import build_graph
        with patch("server.app.get_or_fetch", return_value=MOCK_ARTICLE):
            result = build_graph("Black hole", depth=1)
        assert "nodes" in result
        assert "edges" in result
        assert isinstance(result["nodes"], list)
        assert isinstance(result["edges"], list)

    def test_build_graph_root_has_depth_zero(self, temp_db):
        """The root node should have depth=0."""
        from server.app import build_graph
        article = {**MOCK_ARTICLE, "title": "Black hole", "links": []}
        with patch("server.app.get_or_fetch", return_value=article):
            result = build_graph("Black hole", depth=1)
        root_nodes = [n for n in result["nodes"] if n["depth"] == 0]
        assert len(root_nodes) == 1
        assert root_nodes[0]["id"] == "Black hole"


# ── Contract Tests ────────────────────────────────────────────────────────────

class TestAPIContracts:
    """Contract tests — verify API response shapes match client expectations."""

    def test_search_returns_list(self, client):
        """GET /api/search returns a JSON list."""
        with patch("requests.get") as mock_get:
            mock_get.return_value.ok = True
            mock_get.return_value.json.return_value = ["Black hole", ["Black hole", "Black Holes"]]
            response = client.get("/api/search?q=black+hole")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_graph_response_shape(self, client):
        """GET /api/graph returns {nodes: [...], edges: [...]}."""
        with patch("server.app.build_graph", return_value={"nodes": [], "edges": []}):
            response = client.get("/api/graph?title=Black+hole&depth=1")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

    def test_graphs_list_returns_list(self, client):
        """GET /api/graphs returns a JSON list."""
        response = client.get("/api/graphs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_save_graph_returns_ok(self, client):
        """POST /api/graphs returns {ok: True}."""
        response = client.post("/api/graphs", json={
            "name": "test", "root": "Black hole", "depth": 1,
            "data": {"nodes": [], "edges": []}
        })
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_load_graph_returns_correct_shape(self, client):
        """GET /api/graphs/{id} returns saved graph with data field."""
        client.post("/api/graphs", json={
            "name": "test", "root": "Black hole", "depth": 1,
            "data": {"nodes": [], "edges": []}
        })
        graphs = client.get("/api/graphs").json()
        gid = graphs[0]["id"]
        response = client.get(f"/api/graphs/{gid}")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "root" in data
        assert "depth" in data

    def test_load_nonexistent_graph_returns_404(self, client):
        """GET /api/graphs/99999 returns 404."""
        response = client.get("/api/graphs/99999")
        assert response.status_code == 404


# ── Integration Tests ─────────────────────────────────────────────────────────

class TestIntegration:
    """Integration tests — full save/load cycle."""

    def test_save_and_load_graph(self, client):
        """Save a graph then load it back — data should match."""
        graph_data = {"nodes": [{"id": "Black hole", "depth": 0}], "edges": []}
        client.post("/api/graphs", json={
            "name": "integration-test", "root": "Black hole",
            "depth": 1, "data": graph_data
        })
        graphs = client.get("/api/graphs").json()
        saved = next(g for g in graphs if g["name"] == "integration-test")
        loaded = client.get(f"/api/graphs/{saved['id']}").json()
        assert loaded["root"] == "Black hole"
        assert loaded["data"]["nodes"][0]["id"] == "Black hole"

    def test_duplicate_graph_name_overwrites(self, client):
        """Saving with the same name overwrites the previous graph."""
        client.post("/api/graphs", json={"name": "dup", "root": "A", "depth": 1, "data": {}})
        client.post("/api/graphs", json={"name": "dup", "root": "B", "depth": 2, "data": {}})
        graphs = client.get("/api/graphs").json()
        dups = [g for g in graphs if g["name"] == "dup"]
        assert len(dups) == 1
        assert dups[0]["root"] == "B"
