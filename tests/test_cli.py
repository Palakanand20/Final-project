"""
CLI tests — unit tests for cli/main.py.

Tests verify: correct output printed, correct API functions called,
              error handling (sys.exit(1) on server down), and argparse routing.
All API calls are mocked; no server needs to be running.
"""

import argparse
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_args(**kwargs):
    """Create an argparse.Namespace with given attributes."""
    return argparse.Namespace(**kwargs)


SAMPLE_GRAPH = {
    "nodes": [
        {
            "id": "Black hole",
            "depth": 0,
            "summary": "A region of spacetime.",
            "categories": ["Physics"],
        },
        {
            "id": "Albert Einstein",
            "depth": 1,
            "summary": "German physicist.",
            "categories": ["Scientists"],
        },
    ],
    "edges": [{"source": "Black hole", "target": "Albert Einstein"}],
}

SAMPLE_SAVED = {
    "id": 1,
    "name": "My Graph",
    "root": "Black hole",
    "depth": 1,
    "data": SAMPLE_GRAPH,
}


# ── Tests: print_graph helper ─────────────────────────────────────────────────


class TestPrintGraph:
    """Unit tests for the print_graph display helper."""

    def test_print_graph_shows_node_count(self, capsys):
        """print_graph prints the number of nodes."""
        from cli.main import print_graph

        print_graph(SAMPLE_GRAPH)
        captured = capsys.readouterr()
        assert "2" in captured.out  # 2 nodes

    def test_print_graph_shows_edge_count(self, capsys):
        """print_graph prints the number of edges."""
        from cli.main import print_graph

        print_graph(SAMPLE_GRAPH)
        captured = capsys.readouterr()
        assert "1" in captured.out  # 1 edge

    def test_print_graph_shows_more_message_for_many_edges(self, capsys):
        """print_graph prints '... and N more' when edges exceed 20."""
        from cli.main import print_graph

        many_graph = {
            "nodes": [{"id": "Root", "depth": 0, "summary": "", "categories": []}],
            "edges": [{"source": "Root", "target": f"T{i}"} for i in range(25)],
        }
        print_graph(many_graph)
        captured = capsys.readouterr()
        assert "more" in captured.out

    def test_print_graph_prints_node_ids(self, capsys):
        """print_graph prints each node's ID."""
        from cli.main import print_graph

        print_graph(SAMPLE_GRAPH)
        captured = capsys.readouterr()
        assert "Black hole" in captured.out
        assert "Albert Einstein" in captured.out

    def test_print_graph_handles_empty_graph(self, capsys):
        """print_graph does not raise on an empty nodes/edges graph."""
        from cli.main import print_graph

        print_graph({"nodes": [], "edges": []})
        captured = capsys.readouterr()
        assert "0" in captured.out


# ── Tests: cmd_search ─────────────────────────────────────────────────────────


class TestCLISearch:
    """Unit tests for cmd_search."""

    def test_cmd_search_prints_numbered_results(self, capsys):
        """cmd_search prints each result with a number prefix."""
        from cli.main import cmd_search

        with patch("cli.main.search", return_value=["Black hole", "Black Holes (film)"]):
            cmd_search(_make_args(query="black hole"))
        captured = capsys.readouterr()
        assert "Black hole" in captured.out
        assert "1" in captured.out

    def test_cmd_search_prints_no_results_message_on_empty(self, capsys):
        """cmd_search prints 'No results found.' when the result list is empty."""
        from cli.main import cmd_search

        with patch("cli.main.search", return_value=[]):
            cmd_search(_make_args(query="xyzzy_nonexistent"))
        captured = capsys.readouterr()
        assert "No results" in captured.out

    def test_cmd_search_calls_api_with_query(self):
        """cmd_search passes args.query to the search API function."""
        from cli.main import cmd_search

        with patch("cli.main.search", return_value=[]) as mock_search:
            cmd_search(_make_args(query="quantum physics"))
        mock_search.assert_called_once_with("quantum physics")

    def test_cmd_search_propagates_connection_error(self):
        """cmd_search does not catch exceptions — they propagate to the caller."""
        from cli.main import cmd_search

        with patch("cli.main.search", side_effect=Exception("Connection refused")):
            with pytest.raises(Exception, match="Connection refused"):
                cmd_search(_make_args(query="test"))


# ── Tests: cmd_explore ────────────────────────────────────────────────────────


class TestCLIExplore:
    """Unit tests for cmd_explore."""

    def test_cmd_explore_prints_graph_output(self, capsys):
        """cmd_explore calls print_graph and prints node/edge info."""
        from cli.main import cmd_explore

        with patch("cli.main.get_graph", return_value=SAMPLE_GRAPH):
            cmd_explore(_make_args(title="Black hole", depth=1))
        captured = capsys.readouterr()
        assert "Black hole" in captured.out

    def test_cmd_explore_calls_get_graph_with_correct_args(self):
        """cmd_explore passes title and depth to get_graph."""
        from cli.main import cmd_explore

        with patch("cli.main.get_graph", return_value=SAMPLE_GRAPH) as mock_get:
            cmd_explore(_make_args(title="Nikola Tesla", depth=2))
        mock_get.assert_called_once_with("Nikola Tesla", 2)

    def test_cmd_explore_server_down_exits_1(self):
        """cmd_explore exits with code 1 when the server is unreachable."""
        from cli.main import cmd_explore

        with patch("cli.main.get_graph", side_effect=Exception("Connection refused")):
            with pytest.raises(SystemExit) as exc_info:
                cmd_explore(_make_args(title="Test", depth=1))
        assert exc_info.value.code == 1

    def test_cmd_explore_server_down_shows_uvicorn_hint(self, capsys):
        """cmd_explore prints a uvicorn hint when the server is unreachable."""
        from cli.main import cmd_explore

        with patch("cli.main.get_graph", side_effect=Exception("Connection refused")):
            with pytest.raises(SystemExit):
                cmd_explore(_make_args(title="Test", depth=1))
        captured = capsys.readouterr()
        assert "uvicorn" in captured.err.lower()

    def test_cmd_explore_prints_title_and_depth_header(self, capsys):
        """cmd_explore prints the topic title and depth in the header."""
        from cli.main import cmd_explore

        with patch("cli.main.get_graph", return_value={"nodes": [], "edges": []}):
            cmd_explore(_make_args(title="Quantum mechanics", depth=2))
        captured = capsys.readouterr()
        assert "Quantum mechanics" in captured.out
        assert "2" in captured.out


# ── Tests: cmd_list ───────────────────────────────────────────────────────────


class TestCLIList:
    """Unit tests for cmd_list."""

    def test_cmd_list_prints_saved_graph_names(self, capsys):
        """cmd_list prints names of saved graphs."""
        from cli.main import cmd_list

        graphs = [{"id": 1, "name": "My Graph", "root": "Black hole", "depth": 1}]
        with patch("cli.main.list_graphs", return_value=graphs):
            cmd_list(_make_args())
        captured = capsys.readouterr()
        assert "My Graph" in captured.out

    def test_cmd_list_prints_no_saved_graphs_message(self, capsys):
        """cmd_list prints 'No saved graphs.' when the list is empty."""
        from cli.main import cmd_list

        with patch("cli.main.list_graphs", return_value=[]):
            cmd_list(_make_args())
        captured = capsys.readouterr()
        assert "No saved" in captured.out

    def test_cmd_list_server_down_exits_1(self):
        """cmd_list exits with code 1 when the server is unreachable."""
        from cli.main import cmd_list

        with patch("cli.main.list_graphs", side_effect=Exception("Connection refused")):
            with pytest.raises(SystemExit) as exc_info:
                cmd_list(_make_args())
        assert exc_info.value.code == 1

    def test_cmd_list_calls_list_graphs_api(self):
        """cmd_list calls list_graphs() exactly once."""
        from cli.main import cmd_list

        with patch("cli.main.list_graphs", return_value=[]) as mock_list:
            cmd_list(_make_args())
        mock_list.assert_called_once()

    def test_cmd_list_shows_root_and_depth_for_each_graph(self, capsys):
        """cmd_list prints root and depth alongside the graph name."""
        from cli.main import cmd_list

        graphs = [{"id": 1, "name": "My Graph", "root": "Einstein", "depth": 2}]
        with patch("cli.main.list_graphs", return_value=graphs):
            cmd_list(_make_args())
        captured = capsys.readouterr()
        assert "Einstein" in captured.out
        assert "2" in captured.out


# ── Tests: cmd_load ───────────────────────────────────────────────────────────


class TestCLILoad:
    """Unit tests for cmd_load."""

    def test_cmd_load_prints_loaded_graph(self, capsys):
        """cmd_load prints the graph's node and edge info after loading."""
        from cli.main import cmd_load

        with patch("cli.main.load_graph", return_value=SAMPLE_SAVED):
            cmd_load(_make_args(id=1))
        captured = capsys.readouterr()
        assert "Black hole" in captured.out

    def test_cmd_load_prints_name_root_depth_header(self, capsys):
        """cmd_load prints the graph name, root, and depth in a header."""
        from cli.main import cmd_load

        with patch("cli.main.load_graph", return_value=SAMPLE_SAVED):
            cmd_load(_make_args(id=1))
        captured = capsys.readouterr()
        assert "My Graph" in captured.out
        assert "Black hole" in captured.out

    def test_cmd_load_server_down_exits_1(self):
        """cmd_load exits with code 1 when the server is unreachable."""
        from cli.main import cmd_load

        with patch("cli.main.load_graph", side_effect=Exception("Connection refused")):
            with pytest.raises(SystemExit) as exc_info:
                cmd_load(_make_args(id=99))
        assert exc_info.value.code == 1

    def test_cmd_load_calls_load_graph_with_correct_id(self):
        """cmd_load passes the exact ID to load_graph."""
        from cli.main import cmd_load

        with patch("cli.main.load_graph", return_value=SAMPLE_SAVED) as mock_load:
            cmd_load(_make_args(id=7))
        mock_load.assert_called_once_with(7)


# ── Tests: main() argparse routing ───────────────────────────────────────────


class TestCLIMain:
    """Unit tests for the main() argparse entry point."""

    def test_main_routes_search_command(self):
        """main() dispatches 'search' subcommand to cmd_search."""
        from cli import main as cli_module

        with patch("sys.argv", ["cli", "search", "Black hole"]):
            with patch.object(cli_module, "cmd_search") as mock_cmd:
                cli_module.main()
        mock_cmd.assert_called_once()

    def test_main_routes_explore_command(self):
        """main() dispatches 'explore' subcommand to cmd_explore."""
        from cli import main as cli_module

        with patch("sys.argv", ["cli", "explore", "Black hole", "--depth", "1"]):
            with patch.object(cli_module, "cmd_explore") as mock_cmd:
                cli_module.main()
        mock_cmd.assert_called_once()

    def test_main_routes_list_command(self):
        """main() dispatches 'list' subcommand to cmd_list."""
        from cli import main as cli_module

        with patch("sys.argv", ["cli", "list"]):
            with patch.object(cli_module, "cmd_list") as mock_cmd:
                cli_module.main()
        mock_cmd.assert_called_once()

    def test_main_routes_load_command(self):
        """main() dispatches 'load' subcommand to cmd_load."""
        from cli import main as cli_module

        with patch("sys.argv", ["cli", "load", "1"]):
            with patch.object(cli_module, "cmd_load") as mock_cmd:
                cli_module.main()
        mock_cmd.assert_called_once()

    def test_main_no_command_does_not_raise(self, capsys):
        """main() with no subcommand prints help and exits cleanly."""
        from cli import main as cli_module

        with patch("sys.argv", ["cli"]):
            cli_module.main()  # should not raise, just print help
