"""
Wiki Explorer - CLI client
Usage:
    python cli/main.py explore "Black Holes" --depth 2
    python cli/main.py search "Nikola Tesla"
    python cli/main.py list
    python cli/main.py load 1
"""

import argparse
import sys
import textwrap

sys.path.insert(0, ".")
from client.api import search, get_graph, list_graphs, load_graph


def bold(t):   return "\033[1m" + t + "\033[0m"
def blue(t):   return "\033[34m" + t + "\033[0m"
def green(t):  return "\033[32m" + t + "\033[0m"
def dim(t):    return "\033[2m" + t + "\033[0m"

DEPTH_COLORS = [blue, green,
                lambda t: "\033[33m" + t + "\033[0m",
                lambda t: "\033[31m" + t + "\033[0m"]


def print_graph(data):
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    print("\n" + bold("Nodes: ") + str(len(nodes)) + "   " + bold("Edges: ") + str(len(edges)) + "\n")

    by_depth = {}
    for n in nodes:
        d = n.get("depth", 0)
        by_depth.setdefault(d, []).append(n)

    for depth in sorted(by_depth):
        col = DEPTH_COLORS[min(depth, 3)]
        label = "Root" if depth == 0 else "Depth " + str(depth)
        print(col("-- " + label + " " + "-" * 40))
        for n in sorted(by_depth[depth], key=lambda x: x["id"]):
            print("  " + col("*") + " " + bold(n["id"]))
            if n.get("summary"):
                wrapped = textwrap.fill(n["summary"][:200], width=70,
                                        initial_indent="      ", subsequent_indent="      ")
                print(dim(wrapped))
        print()

    print(bold("Edges (first 20):"))
    for e in edges[:20]:
        print("  " + blue(e["source"]) + "  ->  " + e["target"])
    if len(edges) > 20:
        print(dim("  ... and " + str(len(edges) - 20) + " more"))
    print()


def cmd_search(args):
    results = search(args.query)
    if not results:
        print("No results found.")
        return
    print("\n" + bold("Results:"))
    for i, r in enumerate(results, 1):
        print("  " + blue(str(i)) + ". " + r)
    print()


def cmd_explore(args):
    print("\n" + bold("Exploring: ") + args.title + "  (depth=" + str(args.depth) + ")\n")
    try:
        data = get_graph(args.title, args.depth)
    except Exception as e:
        print("Error: " + str(e), file=sys.stderr)
        print("Is the server running?  python -m uvicorn server.app:app --reload", file=sys.stderr)
        sys.exit(1)
    print_graph(data)


def cmd_list(args):
    try:
        graphs = list_graphs()
    except Exception as e:
        print("Error: " + str(e), file=sys.stderr)
        sys.exit(1)
    if not graphs:
        print("No saved graphs.")
        return
    print(bold("\nSaved Graphs:"))
    for g in graphs:
        print("  " + blue(str(g["id"])) + ". " + bold(g["name"]) + "  --  " + g["root"] + " (depth " + str(g["depth"]) + ")")
    print()


def cmd_load(args):
    try:
        saved = load_graph(args.id)
    except Exception as e:
        print("Error: " + str(e), file=sys.stderr)
        sys.exit(1)
    print("\n" + bold("Loaded: ") + saved["name"] + "  (" + saved["root"] + ", depth " + str(saved["depth"]) + ")\n")
    print_graph(saved["data"])


def main():
    parser = argparse.ArgumentParser(description="Wiki Explorer CLI")
    sub = parser.add_subparsers(dest="command")

    p_search = sub.add_parser("search", help="Search Wikipedia")
    p_search.add_argument("query")

    p_explore = sub.add_parser("explore", help="Build and display a graph")
    p_explore.add_argument("title")
    p_explore.add_argument("--depth", type=int, default=1, choices=[1, 2, 3])

    sub.add_parser("list", help="List saved graphs")

    p_load = sub.add_parser("load", help="Load a saved graph by ID")
    p_load.add_argument("id", type=int)

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "explore":
        cmd_explore(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "load":
        cmd_load(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
