"""
Server tests — unit, contract, and integration tests for the REST API.

Unit tests:      test server functions in isolation (no real Wikipedia calls).
Contract tests:  verify API response shapes match what clients expect.
Integration tests: verify multi-step workflows end-to-end with a real DB.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests as req_lib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a fresh temp database for every test."""
    db_path = str(tmp_path / "test_wiki.db")
    monkeypatch.setattr("server.app.DB_PATH", db_path)
    import server.app as app_module

    app_module.DB_PATH = db_path
    # Close and reset any thread-local connection so get_db() opens a fresh
    # connection to this test's DB_PATH rather than a previous test's path.
    if hasattr(app_module._local, "conn") and app_module._local.conn:
        app_module._local.conn.close()
    app_module._local.conn = None
    app_module.init_db()
    yield db_path
    # Clean up the connection after the test.
    if hasattr(app_module._local, "conn") and app_module._local.conn:
        app_module._local.conn.close()
    app_module._local.conn = None


@pytest.fixture
def client(temp_db):
    """Return a FastAPI TestClient backed by the temp database."""
    from fastapi.testclient import TestClient

    from server.app import app

    return TestClient(app)


MOCK_ARTICLE = {
    "title": "Black hole",
    "summary": "A black hole is a region of spacetime.",
    "categories": ["Astrophysics", "General relativity"],
    "links": ["Albert Einstein", "General relativity", "Gravitational collapse"],
}

LONG_SUMMARY = "X" * 600  # longer than the 500-char truncation limit


def _wiki_page_response(title, extract="", categories=None, links=None, page_id="123"):
    """Build a mock Wikipedia API response for a single page."""
    categories = categories or []
    links = links or []
    return {
        "query": {
            "pages": {
                page_id: {
                    "title": title,
                    "extract": extract,
                    "categories": [{"title": f"Category:{c}"} for c in categories],
                    "links": [{"title": lnk} for lnk in links],
                }
            }
        }
    }


def _wiki_missing_response(title):
    """Build a mock Wikipedia API response for a missing page."""
    return {"query": {"pages": {"-1": {"title": title, "missing": ""}}}}


# ── Unit Tests: fetch_article ─────────────────────────────────────────────────


class TestFetchArticle:
    """Unit tests for the Wikipedia fetch helper."""

    def test_fetch_article_returns_dict_with_expected_keys(self):
        """fetch_article returns a dict with title, summary, categories, links."""
        from server.app import fetch_article

        response_data = _wiki_page_response(
            "Black hole",
            "A black hole...",
            categories=["Astrophysics"],
            links=["Albert Einstein", "General relativity"],
        )
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = response_data
            mock_get.return_value.raise_for_status = MagicMock()
            result = fetch_article("Black hole")

        assert result is not None
        assert result["title"] == "Black hole"
        assert "summary" in result
        assert "categories" in result
        assert "links" in result

    def test_fetch_article_missing_page_returns_none(self):
        """fetch_article returns None when the Wikipedia page doesn't exist."""
        from server.app import fetch_article

        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = _wiki_missing_response("Nonexistent")
            mock_get.return_value.raise_for_status = MagicMock()
            result = fetch_article("Nonexistent")
        assert result is None

    def test_fetch_article_filters_wikipedia_prefix_links(self):
        """fetch_article removes links starting with 'Wikipedia:'."""
        from server.app import fetch_article

        response_data = _wiki_page_response(
            "Test", "", links=["Real Article", "Wikipedia:Tutorial", "Another Article"]
        )
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = response_data
            mock_get.return_value.raise_for_status = MagicMock()
            result = fetch_article("Test")

        assert "Real Article" in result["links"]
        assert "Another Article" in result["links"]
        assert not any(lnk.startswith("Wikipedia:") for lnk in result["links"])

    def test_fetch_article_filters_help_prefix_links(self):
        """fetch_article removes links starting with 'Help:'."""
        from server.app import fetch_article

        response_data = _wiki_page_response("Test", "", links=["Good Article", "Help:Contents"])
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = response_data
            mock_get.return_value.raise_for_status = MagicMock()
            result = fetch_article("Test")

        assert "Good Article" in result["links"]
        assert not any(lnk.startswith("Help:") for lnk in result["links"])

    def test_fetch_article_filters_template_prefix_links(self):
        """fetch_article removes links starting with 'Template:'."""
        from server.app import fetch_article

        response_data = _wiki_page_response(
            "Test", "", links=["Real Link", "Template:Infobox person"]
        )
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = response_data
            mock_get.return_value.raise_for_status = MagicMock()
            result = fetch_article("Test")

        assert "Real Link" in result["links"]
        assert not any(lnk.startswith("Template:") for lnk in result["links"])

    def test_fetch_article_filters_portal_prefix_links(self):
        """fetch_article removes links starting with 'Portal:'."""
        from server.app import fetch_article

        response_data = _wiki_page_response("Test", "", links=["Normal Article", "Portal:Science"])
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = response_data
            mock_get.return_value.raise_for_status = MagicMock()
            result = fetch_article("Test")

        assert "Normal Article" in result["links"]
        assert not any(lnk.startswith("Portal:") for lnk in result["links"])

    def test_fetch_article_truncates_summary_at_500_chars(self):
        """fetch_article truncates extract to 500 characters maximum."""
        from server.app import fetch_article

        response_data = _wiki_page_response("Test", LONG_SUMMARY)
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = response_data
            mock_get.return_value.raise_for_status = MagicMock()
            result = fetch_article("Test")

        assert len(result["summary"]) == 500

    def test_fetch_article_parses_categories_removes_category_prefix(self):
        """fetch_article strips the 'Category:' prefix from category titles."""
        from server.app import fetch_article

        response_data = _wiki_page_response(
            "Test", "", categories=["Astrophysics", "General relativity"]
        )
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = response_data
            mock_get.return_value.raise_for_status = MagicMock()
            result = fetch_article("Test")

        assert "Astrophysics" in result["categories"]
        assert "General relativity" in result["categories"]
        assert not any(c.startswith("Category:") for c in result["categories"])

    def test_fetch_article_network_timeout_raises(self):
        """fetch_article propagates network timeout exceptions."""
        from server.app import fetch_article

        with patch("requests.get", side_effect=req_lib.exceptions.Timeout("Timeout")):
            with pytest.raises(req_lib.exceptions.Timeout):
                fetch_article("Black hole")

    def test_fetch_article_http_403_raises(self):
        """fetch_article propagates HTTP errors from raise_for_status."""
        from server.app import fetch_article

        with patch("requests.get") as mock_get:
            mock_get.return_value.raise_for_status.side_effect = req_lib.exceptions.HTTPError("403")
            with pytest.raises(req_lib.exceptions.HTTPError):
                fetch_article("Black hole")

    def test_fetch_article_passes_correct_params_to_api(self):
        """fetch_article sends the right query parameters to the Wikipedia API."""
        from server.app import WIKI_API, fetch_article

        response_data = _wiki_page_response("Black hole", "...")
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = response_data
            mock_get.return_value.raise_for_status = MagicMock()
            fetch_article("Black hole")

        args, kwargs = mock_get.call_args
        assert args[0] == WIKI_API
        params = kwargs["params"]
        assert params["action"] == "query"
        assert params["titles"] == "Black hole"
        assert params["format"] == "json"

    def test_fetch_article_uses_page_title_not_input_title(self):
        """fetch_article uses the page title from the response (supports redirects)."""
        from server.app import fetch_article

        response_data = _wiki_page_response("Black Hole (canonical)")
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = response_data
            mock_get.return_value.raise_for_status = MagicMock()
            result = fetch_article("black hole redirect")

        assert result["title"] == "Black Hole (canonical)"

    def test_fetch_article_returns_all_unfiltered_links(self):
        """fetch_article returns all non-namespaced links."""
        from server.app import fetch_article

        good_links = ["Alpha", "Beta", "Gamma"]
        bad_links = ["Wikipedia:X", "Help:Y", "Template:Z", "Portal:W"]
        response_data = _wiki_page_response("Test", "", links=good_links + bad_links)
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = response_data
            mock_get.return_value.raise_for_status = MagicMock()
            result = fetch_article("Test")

        assert result["links"] == good_links


# ── Unit Tests: get_or_fetch ──────────────────────────────────────────────────


class TestGetOrFetch:
    """Unit tests for the SQLite caching layer."""

    def test_get_or_fetch_calls_fetch_on_cache_miss(self):
        """get_or_fetch calls fetch_article when article is not in the DB."""
        from server.app import get_or_fetch

        with patch("server.app.fetch_article", return_value=MOCK_ARTICLE) as mock_fetch:
            result = get_or_fetch("Black hole")
        mock_fetch.assert_called_once_with("Black hole")
        assert result["title"] == "Black hole"

    def test_get_or_fetch_does_not_call_fetch_on_cache_hit(self):
        """get_or_fetch uses the cached DB value and skips fetch_article."""
        from server.app import get_or_fetch

        with patch("server.app.fetch_article", return_value=MOCK_ARTICLE):
            get_or_fetch("Black hole")  # prime the cache
        with patch("server.app.fetch_article") as mock_fetch:
            get_or_fetch("Black hole")  # should hit cache
        mock_fetch.assert_not_called()

    def test_get_or_fetch_returns_none_for_missing_article(self):
        """get_or_fetch returns None when fetch_article returns None."""
        from server.app import get_or_fetch

        with patch("server.app.fetch_article", return_value=None):
            result = get_or_fetch("Totally Fake Page 12345")
        assert result is None

    def test_get_or_fetch_stores_article_in_db(self):
        """get_or_fetch persists the fetched article to the articles table."""
        import sqlite3

        import server.app as app_module
        from server.app import get_or_fetch

        with patch("server.app.fetch_article", return_value=MOCK_ARTICLE):
            get_or_fetch("Black hole")

        with sqlite3.connect(app_module.DB_PATH) as conn:
            row = conn.execute(
                "SELECT title FROM articles WHERE title=?", ("Black hole",)
            ).fetchone()
        assert row is not None
        assert row[0] == "Black hole"

    def test_get_or_fetch_stores_links_in_db(self):
        """get_or_fetch persists article links to the links table."""
        import sqlite3

        import server.app as app_module
        from server.app import get_or_fetch

        with patch("server.app.fetch_article", return_value=MOCK_ARTICLE):
            get_or_fetch("Black hole")

        with sqlite3.connect(app_module.DB_PATH) as conn:
            links = conn.execute(
                "SELECT target FROM links WHERE source=?", ("Black hole",)
            ).fetchall()
        stored_targets = {r[0] for r in links}
        for link in MOCK_ARTICLE["links"]:
            assert link in stored_targets

    def test_get_or_fetch_stores_categories_as_json_string(self):
        """get_or_fetch stores categories as a JSON string in the DB."""
        import sqlite3

        import server.app as app_module
        from server.app import get_or_fetch

        with patch("server.app.fetch_article", return_value=MOCK_ARTICLE):
            get_or_fetch("Black hole")

        with sqlite3.connect(app_module.DB_PATH) as conn:
            row = conn.execute(
                "SELECT categories FROM articles WHERE title=?", ("Black hole",)
            ).fetchone()
        parsed = json.loads(row[0])
        assert isinstance(parsed, list)
        assert "Astrophysics" in parsed

    def test_get_or_fetch_returns_correct_dict_structure(self):
        """get_or_fetch returns a dict with title, summary, categories, links."""
        from server.app import get_or_fetch

        with patch("server.app.fetch_article", return_value=MOCK_ARTICLE):
            result = get_or_fetch("Black hole")
        assert "title" in result
        assert "summary" in result
        assert "categories" in result
        assert "links" in result

    def test_get_or_fetch_does_not_write_to_db_when_fetch_returns_none(self):
        """get_or_fetch skips DB writes when fetch_article returns None."""
        import sqlite3

        import server.app as app_module
        from server.app import get_or_fetch

        with patch("server.app.fetch_article", return_value=None):
            get_or_fetch("Ghost Article")

        with sqlite3.connect(app_module.DB_PATH) as conn:
            row = conn.execute(
                "SELECT title FROM articles WHERE title=?", ("Ghost Article",)
            ).fetchone()
        assert row is None


# ── Unit Tests: build_graph ───────────────────────────────────────────────────


class TestBuildGraph:
    """Unit tests for BFS graph construction."""

    def test_build_graph_depth_zero_returns_only_root(self):
        """build_graph(depth=0) includes only the root node, no neighbors."""
        from server.app import build_graph

        with patch("server.app.get_or_fetch", return_value=MOCK_ARTICLE):
            result = build_graph("Black hole", depth=0)
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["id"] == "Black hole"
        assert result["edges"] == []

    def test_build_graph_depth_one_includes_direct_neighbors(self):
        """build_graph(depth=1) adds the root's linked articles."""
        from server.app import build_graph

        articles = {
            "Root": {
                "title": "Root",
                "summary": "",
                "categories": [],
                "links": ["Child1", "Child2"],
            },
            "Child1": {"title": "Child1", "summary": "", "categories": [], "links": []},
            "Child2": {"title": "Child2", "summary": "", "categories": [], "links": []},
        }
        with patch("server.app.get_or_fetch", side_effect=lambda t: articles.get(t)):
            result = build_graph("Root", depth=1)
        node_ids = {n["id"] for n in result["nodes"]}
        assert "Root" in node_ids
        assert "Child1" in node_ids
        assert "Child2" in node_ids

    def test_build_graph_depth_two_expands_two_levels(self):
        """build_graph(depth=2) fetches articles two hops from root."""
        from server.app import build_graph

        articles = {
            "Root": {"title": "Root", "summary": "", "categories": [], "links": ["Level1"]},
            "Level1": {"title": "Level1", "summary": "", "categories": [], "links": ["Level2"]},
            "Level2": {"title": "Level2", "summary": "", "categories": [], "links": []},
        }
        with patch("server.app.get_or_fetch", side_effect=lambda t: articles.get(t)):
            result = build_graph("Root", depth=2)
        node_ids = {n["id"] for n in result["nodes"]}
        assert "Root" in node_ids
        assert "Level1" in node_ids
        assert "Level2" in node_ids

    def test_build_graph_max_links_limits_edges_per_node(self):
        """build_graph respects max_links and does not expand beyond that limit."""
        from server.app import build_graph

        many_links = [f"Link{i}" for i in range(20)]
        articles = {"Root": {"title": "Root", "summary": "", "categories": [], "links": many_links}}
        for lnk in many_links:
            articles[lnk] = {"title": lnk, "summary": "", "categories": [], "links": []}

        with patch("server.app.get_or_fetch", side_effect=lambda t: articles.get(t)):
            result = build_graph("Root", depth=1, max_links=5)

        root_edges = [e for e in result["edges"] if e["source"] == "Root"]
        assert len(root_edges) <= 5

    def test_build_graph_circular_links_do_not_cause_infinite_loop(self):
        """build_graph terminates correctly even when articles link back to each other."""
        from server.app import build_graph

        articles = {
            "A": {"title": "A", "summary": "", "categories": [], "links": ["B"]},
            "B": {"title": "B", "summary": "", "categories": [], "links": ["A"]},
        }
        with patch("server.app.get_or_fetch", side_effect=lambda t: articles.get(t)):
            result = build_graph("A", depth=3)
        node_ids = {n["id"] for n in result["nodes"]}
        assert "A" in node_ids
        assert "B" in node_ids

    def test_build_graph_root_node_has_depth_zero(self):
        """The root node in the returned graph always has depth=0."""
        from server.app import build_graph

        article = {**MOCK_ARTICLE, "links": []}
        with patch("server.app.get_or_fetch", return_value=article):
            result = build_graph("Black hole", depth=1)
        root = next(n for n in result["nodes"] if n["id"] == "Black hole")
        assert root["depth"] == 0

    def test_build_graph_neighbor_nodes_have_depth_one(self):
        """Direct neighbors of the root have depth=1."""
        from server.app import build_graph

        articles = {
            "Root": {"title": "Root", "summary": "", "categories": [], "links": ["Child"]},
            "Child": {"title": "Child", "summary": "", "categories": [], "links": []},
        }
        with patch("server.app.get_or_fetch", side_effect=lambda t: articles.get(t)):
            result = build_graph("Root", depth=1)
        child = next(n for n in result["nodes"] if n["id"] == "Child")
        assert child["depth"] == 1

    def test_build_graph_edges_exclude_nodes_not_in_graph(self):
        """Edges whose target was never fetched are filtered from the result."""
        from server.app import build_graph

        articles = {
            "Root": {
                "title": "Root",
                "summary": "",
                "categories": [],
                "links": ["Exists", "Missing"],
            },
            "Exists": {"title": "Exists", "summary": "", "categories": [], "links": []},
            # "Missing" not in articles → get_or_fetch returns None
        }
        with patch("server.app.get_or_fetch", side_effect=lambda t: articles.get(t)):
            result = build_graph("Root", depth=1)

        edge_targets = {e["target"] for e in result["edges"]}
        assert "Exists" in edge_targets
        assert "Missing" not in edge_targets

    def test_build_graph_returns_nodes_and_edges_keys(self):
        """build_graph always returns a dict with 'nodes' and 'edges' keys."""
        from server.app import build_graph

        with patch("server.app.get_or_fetch", return_value=MOCK_ARTICLE):
            result = build_graph("Black hole", depth=1)
        assert "nodes" in result
        assert "edges" in result
        assert isinstance(result["nodes"], list)
        assert isinstance(result["edges"], list)

    def test_build_graph_root_not_found_returns_empty_graph(self):
        """build_graph returns empty nodes/edges when root article is not found."""
        from server.app import build_graph

        with patch("server.app.get_or_fetch", return_value=None):
            result = build_graph("Nonexistent", depth=1)
        assert result["nodes"] == []
        assert result["edges"] == []


# ── Contract Tests: /api/search ───────────────────────────────────────────────


class TestSearchEndpoint:
    """Contract tests for GET /api/search."""

    def test_search_empty_q_returns_empty_list(self, client):
        """GET /api/search?q= (empty) returns an empty JSON list."""
        response = client.get("/api/search?q=")
        assert response.status_code == 200
        assert response.json() == []

    def test_search_missing_q_param_returns_empty_list(self, client):
        """GET /api/search with no q param returns an empty JSON list."""
        response = client.get("/api/search")
        assert response.status_code == 200
        assert response.json() == []

    def test_search_valid_q_returns_list_of_strings(self, client):
        """GET /api/search?q=... returns a JSON list of title strings."""
        with patch("requests.get") as mock_get:
            mock_get.return_value.ok = True
            mock_get.return_value.json.return_value = [
                "black hole",
                ["Black hole", "Black Holes (film)"],
                [],
                [],
            ]
            response = client.get("/api/search?q=black+hole")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert "Black hole" in response.json()

    def test_search_api_failure_returns_empty_list(self, client):
        """GET /api/search returns [] when the Wikipedia API call fails."""
        with patch("requests.get") as mock_get:
            mock_get.return_value.ok = False
            response = client.get("/api/search?q=test")
        assert response.status_code == 200
        assert response.json() == []

    def test_search_endpoint_sends_opensearch_action(self, client):
        """GET /api/search passes action=opensearch to the Wikipedia API."""
        with patch("requests.get") as mock_get:
            mock_get.return_value.ok = True
            mock_get.return_value.json.return_value = ["q", []]
            client.get("/api/search?q=physics")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["action"] == "opensearch"
        assert kwargs["params"]["search"] == "physics"


# ── Contract Tests: /api/graph ────────────────────────────────────────────────


class TestGraphEndpoint:
    """Contract tests for GET /api/graph."""

    def test_graph_returns_nodes_and_edges(self, client):
        """GET /api/graph returns a dict with 'nodes' and 'edges' lists."""
        with patch("server.app.build_graph", return_value={"nodes": [], "edges": []}):
            response = client.get("/api/graph?title=Black+hole")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

    def test_graph_depth_capped_at_three(self, client):
        """GET /api/graph with depth>3 clamps depth to 3."""
        with patch("server.app.build_graph") as mock_bg:
            mock_bg.return_value = {"nodes": [], "edges": []}
            client.get("/api/graph?title=Black+hole&depth=99")
        _, kwargs = mock_bg.call_args
        assert kwargs["depth"] == 3

    def test_graph_missing_title_returns_422(self, client):
        """GET /api/graph without a title parameter returns 422 (validation error)."""
        response = client.get("/api/graph")
        assert response.status_code == 422

    def test_graph_nodes_have_correct_fields(self, client):
        """Each node in the graph response has id, summary, categories, depth."""
        mock_nodes = [{"id": "Black hole", "summary": "...", "categories": ["A"], "depth": 0}]
        with patch("server.app.build_graph", return_value={"nodes": mock_nodes, "edges": []}):
            response = client.get("/api/graph?title=Black+hole")
        node = response.json()["nodes"][0]
        assert "id" in node
        assert "summary" in node
        assert "categories" in node
        assert "depth" in node

    def test_graph_default_depth_is_one(self, client):
        """GET /api/graph without depth param defaults to depth=1."""
        with patch("server.app.build_graph") as mock_bg:
            mock_bg.return_value = {"nodes": [], "edges": []}
            client.get("/api/graph?title=Black+hole")
        _, kwargs = mock_bg.call_args
        assert kwargs["depth"] == 1

    def test_graph_passes_correct_depth_to_build_graph(self, client):
        """GET /api/graph?depth=2 calls build_graph with depth=2."""
        with patch("server.app.build_graph") as mock_bg:
            mock_bg.return_value = {"nodes": [], "edges": []}
            client.get("/api/graph?title=Black+hole&depth=2")
        _, kwargs = mock_bg.call_args
        assert kwargs["depth"] == 2


# ── Contract Tests: /api/expand ──────────────────────────────────────────────


class TestExpandEndpoint:
    """Contract tests for GET /api/expand."""

    def test_expand_returns_node_and_links(self, client):
        """GET /api/expand returns a dict with 'node' and 'links' keys."""
        with patch("server.app.get_or_fetch", return_value=MOCK_ARTICLE):
            response = client.get("/api/expand?title=Black+hole")
        assert response.status_code == 200
        data = response.json()
        assert "node" in data
        assert "links" in data

    def test_expand_node_has_id_summary_categories(self, client):
        """The 'node' in expand response has id, summary, categories fields."""
        with patch("server.app.get_or_fetch", return_value=MOCK_ARTICLE):
            response = client.get("/api/expand?title=Black+hole")
        node = response.json()["node"]
        assert "id" in node
        assert "summary" in node
        assert "categories" in node

    def test_expand_links_are_limited_to_twenty(self, client):
        """GET /api/expand returns at most 20 links."""
        article = {**MOCK_ARTICLE, "links": [f"Link{i}" for i in range(30)]}
        with patch("server.app.get_or_fetch", return_value=article):
            response = client.get("/api/expand?title=Black+hole")
        assert len(response.json()["links"]) == 20

    def test_expand_returns_404_for_unknown_title(self, client):
        """GET /api/expand returns 404 when the article doesn't exist."""
        with patch("server.app.get_or_fetch", return_value=None):
            response = client.get("/api/expand?title=Totally+Fake+Article")
        assert response.status_code == 404

    def test_expand_calls_get_or_fetch_with_title(self, client):
        """GET /api/expand passes the title to get_or_fetch."""
        with patch("server.app.get_or_fetch") as mock_gof:
            mock_gof.return_value = MOCK_ARTICLE
            client.get("/api/expand?title=Black+hole")
        mock_gof.assert_called_once_with("Black hole")


# ── Contract Tests: GET /api/graphs ──────────────────────────────────────────


class TestGraphsListEndpoint:
    """Contract tests for GET /api/graphs."""

    def test_graphs_list_returns_empty_list_when_none_saved(self, client):
        """GET /api/graphs returns [] when no graphs have been saved."""
        response = client.get("/api/graphs")
        assert response.status_code == 200
        assert response.json() == []

    def test_graphs_list_returns_list_after_save(self, client):
        """GET /api/graphs returns a non-empty list after saving a graph."""
        client.post(
            "/api/graphs", json={"name": "g1", "root": "Black hole", "depth": 1, "data": {}}
        )
        response = client.get("/api/graphs")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_graphs_list_items_have_id_name_root_depth(self, client):
        """Each item in /api/graphs list has id, name, root, depth fields."""
        client.post(
            "/api/graphs", json={"name": "g1", "root": "Black hole", "depth": 1, "data": {}}
        )
        item = client.get("/api/graphs").json()[0]
        assert "id" in item
        assert "name" in item
        assert "root" in item
        assert "depth" in item

    def test_graphs_list_does_not_include_data_field(self, client):
        """GET /api/graphs list items do not include the heavy 'data' field."""
        client.post(
            "/api/graphs", json={"name": "g1", "root": "Black hole", "depth": 1, "data": {"x": 1}}
        )
        item = client.get("/api/graphs").json()[0]
        assert "data" not in item


# ── Contract Tests: POST /api/graphs ─────────────────────────────────────────


class TestSaveGraphEndpoint:
    """Contract tests for POST /api/graphs."""

    def test_save_graph_returns_ok_true(self, client):
        """POST /api/graphs returns {ok: True} on success."""
        response = client.post(
            "/api/graphs", json={"name": "test", "root": "Black hole", "depth": 1, "data": {}}
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_save_graph_missing_name_returns_400(self, client):
        """POST /api/graphs without 'name' returns 400."""
        response = client.post("/api/graphs", json={"root": "Black hole", "depth": 1, "data": {}})
        assert response.status_code == 400

    def test_save_graph_missing_root_returns_400(self, client):
        """POST /api/graphs without 'root' returns 400."""
        response = client.post("/api/graphs", json={"name": "test", "depth": 1, "data": {}})
        assert response.status_code == 400

    def test_save_graph_empty_name_returns_400(self, client):
        """POST /api/graphs with empty-string name returns 400."""
        response = client.post(
            "/api/graphs", json={"name": "   ", "root": "Black hole", "depth": 1, "data": {}}
        )
        assert response.status_code == 400

    def test_save_graph_stores_in_database(self, client):
        """POST /api/graphs actually persists the graph to the DB."""
        client.post("/api/graphs", json={"name": "stored", "root": "A", "depth": 1, "data": {}})
        graphs = client.get("/api/graphs").json()
        assert any(g["name"] == "stored" for g in graphs)

    def test_save_graph_duplicate_name_overwrites_previous(self, client):
        """POST /api/graphs with a duplicate name replaces the previous entry."""
        client.post("/api/graphs", json={"name": "dup", "root": "A", "depth": 1, "data": {}})
        client.post("/api/graphs", json={"name": "dup", "root": "B", "depth": 2, "data": {}})
        graphs = client.get("/api/graphs").json()
        dups = [g for g in graphs if g["name"] == "dup"]
        assert len(dups) == 1
        assert dups[0]["root"] == "B"


# ── Contract Tests: GET /api/graphs/{id} ─────────────────────────────────────


class TestLoadGraphEndpoint:
    """Contract tests for GET /api/graphs/{gid}."""

    def _save_and_get_id(self, client, name="test", root="Black hole", depth=1, data=None):
        """Helper: save a graph and return its assigned ID."""
        client.post(
            "/api/graphs", json={"name": name, "root": root, "depth": depth, "data": data or {}}
        )
        return client.get("/api/graphs").json()[0]["id"]

    def test_load_graph_returns_200_with_data(self, client):
        """GET /api/graphs/{id} returns 200 for a valid saved graph."""
        gid = self._save_and_get_id(client)
        response = client.get(f"/api/graphs/{gid}")
        assert response.status_code == 200

    def test_load_graph_returns_404_for_nonexistent_id(self, client):
        """GET /api/graphs/99999 returns 404 when no such graph exists."""
        response = client.get("/api/graphs/99999")
        assert response.status_code == 404

    def test_load_graph_data_field_is_parsed_dict_not_string(self, client):
        """GET /api/graphs/{id} returns 'data' as a parsed dict, not a JSON string."""
        gid = self._save_and_get_id(client, data={"nodes": [], "edges": []})
        loaded = client.get(f"/api/graphs/{gid}").json()
        assert isinstance(loaded["data"], dict)

    def test_load_graph_has_all_expected_fields(self, client):
        """GET /api/graphs/{id} response includes id, name, root, depth, data."""
        gid = self._save_and_get_id(client)
        loaded = client.get(f"/api/graphs/{gid}").json()
        for field in ("id", "name", "root", "depth", "data"):
            assert field in loaded

    def test_load_graph_data_matches_what_was_saved(self, client):
        """GET /api/graphs/{id} returns exactly the data that was saved."""
        saved_data = {"nodes": [{"id": "Black hole", "depth": 0}], "edges": []}
        gid = self._save_and_get_id(client, data=saved_data)
        loaded = client.get(f"/api/graphs/{gid}").json()
        assert loaded["data"]["nodes"][0]["id"] == "Black hole"


# ── Integration Tests ─────────────────────────────────────────────────────────


class TestIntegration:
    """Integration tests — multi-step workflows with a real DB."""

    def test_full_save_list_load_cycle(self, client):
        """Saving, listing, and loading a graph should all succeed end-to-end."""
        graph_data = {"nodes": [{"id": "Black hole", "depth": 0}], "edges": []}
        client.post(
            "/api/graphs",
            json={"name": "cycle-test", "root": "Black hole", "depth": 1, "data": graph_data},
        )
        graphs = client.get("/api/graphs").json()
        saved = next(g for g in graphs if g["name"] == "cycle-test")
        loaded = client.get(f"/api/graphs/{saved['id']}").json()
        assert loaded["root"] == "Black hole"
        assert loaded["data"]["nodes"][0]["id"] == "Black hole"

    def test_multiple_independent_graphs_are_all_accessible(self, client):
        """Multiple saved graphs are listed and loadable independently."""
        for i in range(3):
            client.post(
                "/api/graphs",
                json={"name": f"graph{i}", "root": f"Root{i}", "depth": 1, "data": {}},
            )
        graphs = client.get("/api/graphs").json()
        assert len(graphs) == 3
        names = {g["name"] for g in graphs}
        assert names == {"graph0", "graph1", "graph2"}

    def test_duplicate_name_overwrites_previous_root(self, client):
        """Saving with an existing name replaces the old entry, keeping count at 1."""
        client.post("/api/graphs", json={"name": "dup", "root": "A", "depth": 1, "data": {"v": 1}})
        client.post("/api/graphs", json={"name": "dup", "root": "B", "depth": 2, "data": {"v": 2}})
        graphs = client.get("/api/graphs").json()
        dups = [g for g in graphs if g["name"] == "dup"]
        assert len(dups) == 1
        assert dups[0]["root"] == "B"

    def test_json_round_trip_preserves_complex_data(self, client):
        """Complex nested graph data survives a save/load cycle intact."""
        complex_data = {
            "nodes": [
                {"id": "Black hole", "depth": 0, "categories": ["Physics"], "summary": "..."},
                {
                    "id": "Albert Einstein",
                    "depth": 1,
                    "categories": ["Scientists"],
                    "summary": "...",
                },
            ],
            "edges": [{"source": "Black hole", "target": "Albert Einstein"}],
        }
        client.post(
            "/api/graphs",
            json={"name": "complex", "root": "Black hole", "depth": 1, "data": complex_data},
        )
        gid = client.get("/api/graphs").json()[0]["id"]
        loaded = client.get(f"/api/graphs/{gid}").json()
        assert len(loaded["data"]["nodes"]) == 2
        assert loaded["data"]["edges"][0]["source"] == "Black hole"

    def test_search_then_save_pipeline(self, client):
        """A search→graph→save pipeline returns correct status codes throughout."""
        with patch("requests.get") as mock_get:
            mock_get.return_value.ok = True
            mock_get.return_value.json.return_value = ["bh", ["Black hole"]]
            search_resp = client.get("/api/search?q=black+hole")
        assert search_resp.status_code == 200

        with patch("server.app.build_graph", return_value={"nodes": [], "edges": []}):
            graph_resp = client.get("/api/graph?title=Black+hole")
        assert graph_resp.status_code == 200

        save_resp = client.post(
            "/api/graphs",
            json={
                "name": "pipeline-test",
                "root": "Black hole",
                "depth": 1,
                "data": graph_resp.json(),
            },
        )
        assert save_resp.json()["ok"] is True

    def test_graphs_listed_most_recent_first(self, client):
        """GET /api/graphs returns graphs ordered newest-first (ORDER BY rowid DESC)."""
        client.post("/api/graphs", json={"name": "first", "root": "A", "depth": 1, "data": {}})
        client.post("/api/graphs", json={"name": "second", "root": "B", "depth": 1, "data": {}})
        graphs = client.get("/api/graphs").json()
        assert graphs[0]["name"] == "second"
        assert graphs[1]["name"] == "first"
