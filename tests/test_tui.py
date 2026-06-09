"""
TUI tests — unit tests for tui/main.py.

Tests verify: display functions don't raise, menu routing calls the correct
              API functions, error paths continue the loop, and quit exits cleanly.
All API calls and Rich console output are mocked.
"""

import os
import sys
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


SAMPLE_GRAPH = {
    "nodes": [
        {
            "id": "Black hole",
            "depth": 0,
            "summary": "A black hole is...",
            "categories": ["Physics"],
        },
        {
            "id": "Albert Einstein",
            "depth": 1,
            "summary": "German physicist.",
            "categories": ["Science"],
        },
    ],
    "edges": [{"source": "Black hole", "target": "Albert Einstein"}],
}

SAMPLE_SAVED_GRAPHS = [
    {"id": 1, "name": "My Graph", "root": "Black hole", "depth": 1},
    {"id": 2, "name": "Second Graph", "root": "Einstein", "depth": 2},
]

FULL_SAVED = {
    "id": 1,
    "name": "My Graph",
    "root": "Black hole",
    "depth": 1,
    "data": SAMPLE_GRAPH,
}


def _run_tui_main(prompt_inputs, api_mocks=None):
    """
    Run tui.main.main() with pre-set Prompt.ask return values.

    prompt_inputs: list of strings returned by successive Prompt.ask calls.
    api_mocks: dict mapping patch target → return value.
    """
    api_mocks = api_mocks or {}
    from tui.main import main

    patches = [
        patch("tui.main.Prompt"),
        patch("tui.main.console"),
    ]
    for target, retval in api_mocks.items():
        patches.append(patch(target, return_value=retval))

    with patch("tui.main.Prompt") as mock_prompt, patch("tui.main.console"):
        mock_prompt.ask.side_effect = list(prompt_inputs)

        ctx_patches = {}
        for target, retval in api_mocks.items():
            p = patch(target, return_value=retval)
            mock_obj = p.start()
            ctx_patches[target] = (p, mock_obj)

        try:
            main()
        finally:
            for p, _ in ctx_patches.values():
                p.stop()

        return mock_prompt, {k: v for k, (_, v) in ctx_patches.items()}


# ── Tests: show_graph ─────────────────────────────────────────────────────────


class TestShowGraph:
    """Unit tests for the show_graph display function."""

    def test_show_graph_does_not_raise_with_normal_data(self):
        """show_graph runs without error for a typical graph dict."""
        from tui.main import show_graph

        with patch("tui.main.console"):
            show_graph(SAMPLE_GRAPH, "Black hole")

    def test_show_graph_does_not_raise_with_empty_data(self):
        """show_graph handles an empty nodes/edges graph gracefully."""
        from tui.main import show_graph

        with patch("tui.main.console"):
            show_graph({"nodes": [], "edges": []}, "Empty")

    def test_show_graph_handles_multiple_depth_levels(self):
        """show_graph handles nodes at various depth levels without error."""
        from tui.main import show_graph

        deep_graph = {
            "nodes": [
                {"id": "Root", "depth": 0, "summary": "Root.", "categories": []},
                {"id": "L1", "depth": 1, "summary": "Level 1.", "categories": []},
                {"id": "L2", "depth": 2, "summary": "Level 2.", "categories": []},
            ],
            "edges": [],
        }
        with patch("tui.main.console"):
            show_graph(deep_graph, "Root")


# ── Tests: show_search_results ────────────────────────────────────────────────


class TestShowSearchResults:
    """Unit tests for the show_search_results display function."""

    def test_show_search_results_returns_the_list(self):
        """show_search_results returns the results list when non-empty."""
        from tui.main import show_search_results

        results = ["Black hole", "Black Holes (film)"]
        with patch("tui.main.console"):
            returned = show_search_results(results)
        assert returned == results

    def test_show_search_results_returns_none_for_empty_list(self):
        """show_search_results returns None when the list is empty."""
        from tui.main import show_search_results

        with patch("tui.main.console"):
            returned = show_search_results([])
        assert returned is None

    def test_show_search_results_does_not_raise(self):
        """show_search_results completes without error for any input."""
        from tui.main import show_search_results

        with patch("tui.main.console"):
            show_search_results(["Result 1", "Result 2", "Result 3"])


# ── Tests: show_saved_graphs ──────────────────────────────────────────────────


class TestShowSavedGraphs:
    """Unit tests for the show_saved_graphs display function."""

    def test_show_saved_graphs_does_not_raise_with_data(self):
        """show_saved_graphs displays a table without error."""
        from tui.main import show_saved_graphs

        with patch("tui.main.console"):
            show_saved_graphs(SAMPLE_SAVED_GRAPHS)

    def test_show_saved_graphs_does_not_raise_when_empty(self):
        """show_saved_graphs handles an empty list without error."""
        from tui.main import show_saved_graphs

        with patch("tui.main.console"):
            show_saved_graphs([])


# ── Tests: main() — choice "1" (Explore) ─────────────────────────────────────


class TestMainMenuExplore:
    """Tests for main() menu choice 1: Explore a topic."""

    def test_choice_1_calls_get_graph(self):
        """Choosing '1' calls get_graph with the entered topic and depth."""
        _, mocks = _run_tui_main(
            prompt_inputs=["1", "Black hole", "1", "n", "q"],
            api_mocks={"tui.main.get_graph": SAMPLE_GRAPH},
        )
        mock_get_graph = mocks["tui.main.get_graph"]
        mock_get_graph.assert_called_once()
        args, _ = mock_get_graph.call_args
        assert args[0] == "Black hole"

    def test_choice_1_server_down_shows_error_and_continues(self):
        """Choosing '1' with a server error prints an error and loops back."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.get_graph", side_effect=Exception("Server down")),
        ):
            mock_prompt.ask.side_effect = ["1", "Black hole", "1", "q"]
            main()  # should not raise — error is caught and loop continues

    def test_choice_1_saves_graph_when_prompted_y(self):
        """Choosing '1' then 'y' at the save prompt calls save_graph."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.get_graph", return_value=SAMPLE_GRAPH),
            patch("tui.main.save_graph", return_value={"ok": True}) as mock_save,
        ):
            mock_prompt.ask.side_effect = ["1", "Black hole", "1", "y", "My saved graph", "q"]
            main()
        mock_save.assert_called_once()
        args, _ = mock_save.call_args
        assert args[0] == "My saved graph"  # name is the first positional arg


# ── Tests: main() — choice "2" (Search) ──────────────────────────────────────


class TestMainMenuSearch:
    """Tests for main() menu choice 2: Search Wikipedia."""

    def test_choice_2_calls_search(self):
        """Choosing '2' calls search with the entered query."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.search", return_value=["Black hole"]) as mock_search,
        ):
            mock_prompt.ask.side_effect = ["2", "black hole", "", "q"]
            main()
        mock_search.assert_called_once_with("black hole")

    def test_choice_2_explores_result_when_number_entered(self):
        """Choosing '2' then entering a result number calls get_graph."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.search", return_value=["Black hole", "Neutron star"]),
            patch("tui.main.get_graph", return_value=SAMPLE_GRAPH) as mock_get,
        ):
            mock_prompt.ask.side_effect = ["2", "stars", "1", "1", "q"]
            main()
        mock_get.assert_called_once()

    def test_choice_2_skips_explore_on_empty_pick(self):
        """Choosing '2' then pressing Enter (empty pick) skips exploration."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.search", return_value=["Black hole"]),
            patch("tui.main.get_graph") as mock_get,
        ):
            mock_prompt.ask.side_effect = ["2", "test", "", "q"]
            main()
        mock_get.assert_not_called()


# ── Tests: main() — choice "3" (View saved) ──────────────────────────────────


class TestMainMenuViewSaved:
    """Tests for main() menu choice 3: View saved graphs."""

    def test_choice_3_calls_list_graphs(self):
        """Choosing '3' calls list_graphs and shows the saved graphs table."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.list_graphs", return_value=SAMPLE_SAVED_GRAPHS) as mock_list,
        ):
            mock_prompt.ask.side_effect = ["3", "q"]
            main()
        mock_list.assert_called_once()


# ── Tests: main() — choice "4" (Load saved) ──────────────────────────────────


class TestMainMenuLoad:
    """Tests for main() menu choice 4: Load a saved graph."""

    def test_choice_4_calls_load_graph(self):
        """Choosing '4' and entering an ID calls load_graph with that ID."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.list_graphs", return_value=SAMPLE_SAVED_GRAPHS),
            patch("tui.main.load_graph", return_value=FULL_SAVED) as mock_load,
        ):
            mock_prompt.ask.side_effect = ["4", "1", "q"]
            main()
        mock_load.assert_called_once_with(1)

    def test_choice_4_skips_load_prompt_when_no_graphs(self):
        """Choosing '4' when no graphs are saved skips the ID prompt and loops."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.list_graphs", return_value=[]),
            patch("tui.main.load_graph") as mock_load,
        ):
            mock_prompt.ask.side_effect = ["4", "q"]
            main()
        mock_load.assert_not_called()


# ── Tests: main() — quit and invalid input ────────────────────────────────────


class TestMainMenuQuitAndInvalid:
    """Tests for main() quit ('q') and invalid choice handling."""

    def test_quit_exits_cleanly(self):
        """Entering 'q' breaks the loop and main() returns without error."""
        from tui.main import main

        with patch("tui.main.Prompt") as mock_prompt, patch("tui.main.console"):
            mock_prompt.ask.side_effect = ["q"]
            main()  # should return normally

    def test_invalid_choice_does_not_crash(self):
        """An invalid menu choice prints an error and loops back gracefully."""
        from tui.main import main

        with patch("tui.main.Prompt") as mock_prompt, patch("tui.main.console"):
            mock_prompt.ask.side_effect = ["z", "q"]
            main()  # should not raise


# ── Tests: main() — error/exception branches ─────────────────────────────────


class TestMainMenuErrorBranches:
    """Tests for exception-handling branches inside main()."""

    def test_choice_1_invalid_depth_string_defaults_to_one(self):
        """Entering a non-numeric depth in choice '1' silently defaults to 1."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.get_graph", return_value=SAMPLE_GRAPH) as mock_get,
        ):
            mock_prompt.ask.side_effect = ["1", "Black hole", "notanumber", "n", "q"]
            main()
        args, _ = mock_get.call_args
        assert args[1] == 1  # depth defaulted to 1

    def test_choice_1_save_graph_error_does_not_crash(self):
        """A save_graph failure in choice '1' shows an error and continues."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.get_graph", return_value=SAMPLE_GRAPH),
            patch("tui.main.save_graph", side_effect=Exception("Server error")),
        ):
            mock_prompt.ask.side_effect = ["1", "Black hole", "1", "y", "My Graph", "q"]
            main()  # should not raise

    def test_choice_2_search_error_shows_error_and_continues(self):
        """A search() failure in choice '2' shows an error and loops back."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.search", side_effect=Exception("Network error")),
        ):
            mock_prompt.ask.side_effect = ["2", "black hole", "q"]
            main()  # should not raise

    def test_choice_2_invalid_depth_in_explore_defaults_to_one(self):
        """Non-numeric depth when exploring a search result defaults to 1."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.search", return_value=["Black hole"]),
            patch("tui.main.get_graph", return_value=SAMPLE_GRAPH) as mock_get,
        ):
            mock_prompt.ask.side_effect = ["2", "black hole", "1", "bad_depth", "q"]
            main()
        args, _ = mock_get.call_args
        assert args[1] == 1  # depth defaulted to 1

    def test_choice_2_get_graph_error_after_pick_does_not_crash(self):
        """A get_graph failure after picking a search result shows error and continues."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.search", return_value=["Black hole"]),
            patch("tui.main.get_graph", side_effect=Exception("Server error")),
        ):
            mock_prompt.ask.side_effect = ["2", "black hole", "1", "1", "q"]
            main()  # should not raise

    def test_choice_3_list_graphs_error_does_not_crash(self):
        """A list_graphs() failure in choice '3' shows an error and continues."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.list_graphs", side_effect=Exception("Network error")),
        ):
            mock_prompt.ask.side_effect = ["3", "q"]
            main()  # should not raise

    def test_choice_4_list_graphs_error_shows_error_and_continues(self):
        """A list_graphs() failure in choice '4' shows an error and loops back."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.list_graphs", side_effect=Exception("Network error")),
        ):
            mock_prompt.ask.side_effect = ["4", "q"]
            main()  # should not raise

    def test_choice_4_load_graph_error_does_not_crash(self):
        """A load_graph() failure in choice '4' shows an error and continues."""
        from tui.main import main

        with (
            patch("tui.main.Prompt") as mock_prompt,
            patch("tui.main.console"),
            patch("tui.main.list_graphs", return_value=SAMPLE_SAVED_GRAPHS),
            patch("tui.main.load_graph", side_effect=Exception("Not found")),
        ):
            mock_prompt.ask.side_effect = ["4", "99", "q"]
            main()  # should not raise
