"""
Client tests — unit tests for the shared API client module.
These tests mock HTTP calls so no server needs to be running.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def make_mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    return mock


# ── Unit Tests ────────────────────────────────────────────────────────────────

class TestSearchClient:
    """Unit tests for client.api.search"""

    def test_search_returns_list(self):
        from client.api import search
        mock_resp = make_mock_response(["Black hole", "Black Holes (film)"])
        with patch("httpx.get", return_value=mock_resp):
            result = search("black hole")
        assert isinstance(result, list)
        assert "Black hole" in result

    def test_search_empty_query(self):
        from client.api import search
        mock_resp = make_mock_response([])
        with patch("httpx.get", return_value=mock_resp):
            result = search("")
        assert result == []


class TestGraphClient:
    """Unit tests for client.api.get_graph"""

    def test_get_graph_returns_nodes_and_edges(self):
        from client.api import get_graph
        mock_data = {
            "nodes": [{"id": "Black hole", "depth": 0}],
            "edges": []
        }
        mock_resp = make_mock_response(mock_data)
        with patch("httpx.get", return_value=mock_resp):
            result = get_graph("Black hole", depth=1)
        assert "nodes" in result
        assert "edges" in result
        assert result["nodes"][0]["id"] == "Black hole"

    def test_get_graph_passes_correct_params(self):
        from client.api import get_graph
        mock_resp = make_mock_response({"nodes": [], "edges": []})
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            get_graph("Nikola Tesla", depth=2)
        call_kwargs = mock_get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {}
        assert "Nikola Tesla" in str(call_kwargs)
        assert "2" in str(call_kwargs)


class TestSaveLoadClient:
    """Unit tests for save/load graph client functions."""

    def test_save_graph_posts_correct_data(self):
        from client.api import save_graph
        mock_resp = make_mock_response({"ok": True})
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = save_graph("my graph", "Black hole", 1, {"nodes": [], "edges": []})
        assert result["ok"] is True
        posted = mock_post.call_args[1].get("json") or {}
        assert posted.get("name") == "my graph"
        assert posted.get("root") == "Black hole"

    def test_list_graphs_returns_list(self):
        from client.api import list_graphs
        mock_resp = make_mock_response([{"id": 1, "name": "test", "root": "Black hole", "depth": 1}])
        with patch("httpx.get", return_value=mock_resp):
            result = list_graphs()
        assert isinstance(result, list)
        assert result[0]["name"] == "test"

    def test_load_graph_returns_saved_data(self):
        from client.api import load_graph
        mock_data = {"id": 1, "name": "test", "root": "Black hole", "depth": 1,
                     "data": {"nodes": [], "edges": []}}
        mock_resp = make_mock_response(mock_data)
        with patch("httpx.get", return_value=mock_resp):
            result = load_graph(1)
        assert result["name"] == "test"
        assert result["root"] == "Black hole"
