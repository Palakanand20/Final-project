"""
Client tests — unit tests for the shared API client (client/api.py).

All HTTP calls are mocked; no server needs to be running.
Tests verify: correct URLs/params used, return types, and error propagation.
"""

import os
import sys
from unittest.mock import MagicMock, call, patch

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _mock_response(json_data, status_code=200):
    """Return a MagicMock that behaves like an httpx Response (success)."""
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    return mock


def _error_response(status_code=500):
    """Return a MagicMock whose raise_for_status() raises HTTPStatusError."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.raise_for_status.side_effect = httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=MagicMock(),
        response=MagicMock(status_code=status_code),
    )
    return mock


# ── Tests: client.api.search ──────────────────────────────────────────────────


class TestClientSearch:
    """Unit tests for client.api.search."""

    def test_search_returns_list(self):
        """search() returns a Python list of strings."""
        from client.api import search

        mock_resp = _mock_response(["Black hole", "Black Holes (film)"])
        with patch("httpx.get", return_value=mock_resp):
            result = search("black hole")
        assert isinstance(result, list)

    def test_search_returns_expected_titles(self):
        """search() returns exactly the list from the response body."""
        from client.api import search

        titles = ["Black hole", "Black Holes (film)", "Stellar black hole"]
        with patch("httpx.get", return_value=_mock_response(titles)):
            result = search("black hole")
        assert result == titles

    def test_search_passes_q_param(self):
        """search() sends the query string as the 'q' param."""
        from client.api import search

        with patch("httpx.get", return_value=_mock_response([])) as mock_get:
            search("nikola tesla")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["q"] == "nikola tesla"

    def test_search_raises_on_http_error(self):
        """search() propagates HTTP errors from raise_for_status."""
        from client.api import search

        with patch("httpx.get", return_value=_error_response(500)):
            with pytest.raises(httpx.HTTPStatusError):
                search("test")

    def test_search_allows_empty_query_string(self):
        """search() accepts an empty string without raising."""
        from client.api import search

        with patch("httpx.get", return_value=_mock_response([])):
            result = search("")
        assert result == []

    def test_search_handles_unicode_query(self):
        """search() handles unicode characters in the query."""
        from client.api import search

        with patch("httpx.get", return_value=_mock_response(["Résumé"])):
            result = search("résumé")
        assert isinstance(result, list)


# ── Tests: client.api.get_graph ───────────────────────────────────────────────


class TestClientGetGraph:
    """Unit tests for client.api.get_graph."""

    def test_get_graph_returns_dict(self):
        """get_graph() returns a dict."""
        from client.api import get_graph

        mock_data = {"nodes": [], "edges": []}
        with patch("httpx.get", return_value=_mock_response(mock_data)):
            result = get_graph("Black hole")
        assert isinstance(result, dict)

    def test_get_graph_passes_title_param(self):
        """get_graph() sends 'title' in the query params."""
        from client.api import get_graph

        with patch(
            "httpx.get", return_value=_mock_response({"nodes": [], "edges": []})
        ) as mock_get:
            get_graph("Nikola Tesla", depth=1)
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["title"] == "Nikola Tesla"

    def test_get_graph_passes_depth_param(self):
        """get_graph() sends 'depth' in the query params."""
        from client.api import get_graph

        with patch(
            "httpx.get", return_value=_mock_response({"nodes": [], "edges": []})
        ) as mock_get:
            get_graph("Test", depth=2)
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["depth"] == 2

    def test_get_graph_default_depth_is_one(self):
        """get_graph() defaults to depth=1 when no depth is specified."""
        from client.api import get_graph

        with patch(
            "httpx.get", return_value=_mock_response({"nodes": [], "edges": []})
        ) as mock_get:
            get_graph("Test")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["depth"] == 1

    def test_get_graph_raises_on_404(self):
        """get_graph() raises on 404 response."""
        from client.api import get_graph

        with patch("httpx.get", return_value=_error_response(404)):
            with pytest.raises(httpx.HTTPStatusError):
                get_graph("Nonexistent")

    def test_get_graph_raises_on_500(self):
        """get_graph() raises on 500 response."""
        from client.api import get_graph

        with patch("httpx.get", return_value=_error_response(500)):
            with pytest.raises(httpx.HTTPStatusError):
                get_graph("Test")


# ── Tests: client.api.expand_node ─────────────────────────────────────────────


class TestClientExpandNode:
    """Unit tests for client.api.expand_node."""

    def test_expand_node_returns_dict(self):
        """expand_node() returns a dict."""
        from client.api import expand_node

        mock_data = {"node": {"id": "Black hole"}, "links": []}
        with patch("httpx.get", return_value=_mock_response(mock_data)):
            result = expand_node("Black hole")
        assert isinstance(result, dict)

    def test_expand_node_passes_title_param(self):
        """expand_node() sends 'title' in the query params."""
        from client.api import expand_node

        mock_data = {"node": {}, "links": []}
        with patch("httpx.get", return_value=_mock_response(mock_data)) as mock_get:
            expand_node("Albert Einstein")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["title"] == "Albert Einstein"

    def test_expand_node_raises_on_404(self):
        """expand_node() raises on 404 (article not found)."""
        from client.api import expand_node

        with patch("httpx.get", return_value=_error_response(404)):
            with pytest.raises(httpx.HTTPStatusError):
                expand_node("Ghost Page")

    def test_expand_node_handles_special_chars_in_title(self):
        """expand_node() handles article titles with special characters."""
        from client.api import expand_node

        mock_data = {"node": {"id": "AC/DC"}, "links": []}
        with patch("httpx.get", return_value=_mock_response(mock_data)):
            result = expand_node("AC/DC")
        assert isinstance(result, dict)

    def test_expand_node_raises_on_500(self):
        """expand_node() raises on server errors."""
        from client.api import expand_node

        with patch("httpx.get", return_value=_error_response(500)):
            with pytest.raises(httpx.HTTPStatusError):
                expand_node("Test")


# ── Tests: client.api.list_graphs ─────────────────────────────────────────────


class TestClientListGraphs:
    """Unit tests for client.api.list_graphs."""

    def test_list_graphs_returns_list(self):
        """list_graphs() returns a Python list."""
        from client.api import list_graphs

        mock_data = [{"id": 1, "name": "test", "root": "A", "depth": 1}]
        with patch("httpx.get", return_value=_mock_response(mock_data)):
            result = list_graphs()
        assert isinstance(result, list)

    def test_list_graphs_returns_empty_list_when_none_saved(self):
        """list_graphs() returns [] when there are no saved graphs."""
        from client.api import list_graphs

        with patch("httpx.get", return_value=_mock_response([])):
            result = list_graphs()
        assert result == []

    def test_list_graphs_raises_on_connection_error(self):
        """list_graphs() propagates connection errors."""
        from client.api import list_graphs

        with patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")):
            with pytest.raises(httpx.ConnectError):
                list_graphs()

    def test_list_graphs_calls_correct_url(self):
        """list_graphs() requests the /api/graphs endpoint."""
        from client.api import BASE_URL, list_graphs

        with patch("httpx.get", return_value=_mock_response([])) as mock_get:
            list_graphs()
        args, _ = mock_get.call_args
        assert args[0] == f"{BASE_URL}/api/graphs"


# ── Tests: client.api.save_graph ──────────────────────────────────────────────


class TestClientSaveGraph:
    """Unit tests for client.api.save_graph."""

    def test_save_graph_returns_dict(self):
        """save_graph() returns a dict."""
        from client.api import save_graph

        with patch("httpx.post", return_value=_mock_response({"ok": True})):
            result = save_graph("My Graph", "Black hole", 1, {})
        assert isinstance(result, dict)

    def test_save_graph_posts_correct_body(self):
        """save_graph() sends name, root, depth, and data in the POST body."""
        from client.api import save_graph

        with patch("httpx.post", return_value=_mock_response({"ok": True})) as mock_post:
            save_graph("My Graph", "Black hole", 2, {"nodes": []})
        _, kwargs = mock_post.call_args
        body = kwargs["json"]
        assert body["name"] == "My Graph"
        assert body["root"] == "Black hole"
        assert body["depth"] == 2
        assert "data" in body

    def test_save_graph_raises_on_400(self):
        """save_graph() raises on 400 Bad Request."""
        from client.api import save_graph

        with patch("httpx.post", return_value=_error_response(400)):
            with pytest.raises(httpx.HTTPStatusError):
                save_graph("", "", 1, {})

    def test_save_graph_handles_complex_nested_data(self):
        """save_graph() correctly passes complex nested graph data."""
        from client.api import save_graph

        complex_data = {
            "nodes": [{"id": "A", "depth": 0, "categories": ["X"]}],
            "edges": [{"source": "A", "target": "B"}],
        }
        with patch("httpx.post", return_value=_mock_response({"ok": True})) as mock_post:
            save_graph("complex", "A", 1, complex_data)
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["data"] == complex_data

    def test_save_graph_raises_on_500(self):
        """save_graph() raises on server errors."""
        from client.api import save_graph

        with patch("httpx.post", return_value=_error_response(500)):
            with pytest.raises(httpx.HTTPStatusError):
                save_graph("test", "root", 1, {})


# ── Tests: client.api.load_graph ──────────────────────────────────────────────


class TestClientLoadGraph:
    """Unit tests for client.api.load_graph."""

    def test_load_graph_returns_dict(self):
        """load_graph() returns a dict."""
        from client.api import load_graph

        mock_data = {"id": 1, "name": "test", "root": "A", "depth": 1, "data": {}}
        with patch("httpx.get", return_value=_mock_response(mock_data)):
            result = load_graph(1)
        assert isinstance(result, dict)

    def test_load_graph_uses_correct_url_with_id(self):
        """load_graph() requests /api/graphs/{gid} with the given ID."""
        from client.api import BASE_URL, load_graph

        mock_data = {"id": 42, "name": "g", "root": "A", "depth": 1, "data": {}}
        with patch("httpx.get", return_value=_mock_response(mock_data)) as mock_get:
            load_graph(42)
        args, _ = mock_get.call_args
        assert args[0] == f"{BASE_URL}/api/graphs/42"

    def test_load_graph_raises_on_404(self):
        """load_graph() raises on 404 (graph not found)."""
        from client.api import load_graph

        with patch("httpx.get", return_value=_error_response(404)):
            with pytest.raises(httpx.HTTPStatusError):
                load_graph(99999)

    def test_load_graph_raises_on_500(self):
        """load_graph() raises on server errors."""
        from client.api import load_graph

        with patch("httpx.get", return_value=_error_response(500)):
            with pytest.raises(httpx.HTTPStatusError):
                load_graph(1)

    def test_load_graph_returns_data_field(self):
        """load_graph() returns a dict that includes the 'data' field."""
        from client.api import load_graph

        mock_data = {"id": 1, "name": "test", "root": "A", "depth": 1, "data": {"nodes": []}}
        with patch("httpx.get", return_value=_mock_response(mock_data)):
            result = load_graph(1)
        assert "data" in result
        assert isinstance(result["data"], dict)
