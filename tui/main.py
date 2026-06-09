"""
Wiki Explorer - TUI (Terminal User Interface)
Uses the Rich library for a nice terminal display.

Usage:
    python tui/main.py
"""

import sys

sys.path.insert(0, ".")

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.tree import Tree

from client.api import get_graph, list_graphs, load_graph, save_graph, search

console = Console()


def show_graph(data, title):
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    console.print(
        Panel(
            f"[bold cyan]{title}[/bold cyan]\n"
            f"[green]{len(nodes)} nodes[/green]  [yellow]{len(edges)} edges[/yellow]",
            title="Graph",
            border_style="blue",
        )
    )

    # Build tree by depth
    by_depth = {}
    for n in nodes:
        d = n.get("depth", 0)
        by_depth.setdefault(d, []).append(n)

    depth_colors = ["bold blue", "bold green", "bold yellow", "bold red"]

    tree = Tree(f"[bold blue]{title}[/bold blue]")

    for depth in sorted(by_depth):
        color = depth_colors[min(depth, 3)]
        for n in sorted(by_depth[depth], key=lambda x: x["id"]):
            if depth == 0:
                continue
            label = f"[{color}]{n['id']}[/{color}]"
            if n.get("summary"):
                label += f"\n  [dim]{n['summary'][:100]}...[/dim]"
            tree.add(label)

    console.print(tree)
    console.print()


def show_search_results(results):
    if not results:
        console.print("[red]No results found.[/red]")
        return None

    table = Table(title="Search Results", border_style="blue")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Title", style="white")

    for i, r in enumerate(results, 1):
        table.add_row(str(i), r)

    console.print(table)
    return results


def show_saved_graphs(graphs):
    if not graphs:
        console.print("[dim]No saved graphs.[/dim]")
        return

    table = Table(title="Saved Graphs", border_style="blue")
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Name", style="bold white")
    table.add_column("Root", style="green")
    table.add_column("Depth", style="yellow", width=6)

    for g in graphs:
        table.add_row(str(g["id"]), g["name"], g["root"], str(g["depth"]))

    console.print(table)


def main():
    console.print(
        Panel(
            "[bold cyan]Wikipedia Rabbit Hole Explorer[/bold cyan]\n"
            "[dim]Explore how Wikipedia articles connect[/dim]",
            border_style="cyan",
        )
    )

    while True:
        console.print("\n[bold]What would you like to do?[/bold]")
        console.print("  [cyan]1[/cyan]. Explore a topic")
        console.print("  [cyan]2[/cyan]. Search Wikipedia")
        console.print("  [cyan]3[/cyan]. View saved graphs")
        console.print("  [cyan]4[/cyan]. Load a saved graph")
        console.print("  [cyan]q[/cyan]. Quit")

        choice = Prompt.ask("\nChoice").strip().lower()

        if choice == "q":
            console.print("[dim]Goodbye![/dim]")
            break

        elif choice == "1":
            topic = Prompt.ask("Enter a topic")
            depth = Prompt.ask("Depth (1-3)", default="1")
            try:
                depth = max(1, min(3, int(depth)))
            except ValueError:
                depth = 1

            console.print(f"\n[dim]Fetching graph for '{topic}' at depth {depth}...[/dim]")
            try:
                data = get_graph(topic, depth)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                console.print(
                    "[dim]Is the server running? python -m uvicorn server.app:app --reload --port 8001[/dim]"
                )
                continue

            show_graph(data, topic)

            save = Prompt.ask("Save this graph? (y/n)", default="n")
            if save.lower() == "y":
                name = Prompt.ask("Graph name")
                try:
                    save_graph(name, topic, depth, data)
                    console.print(f"[green]Saved as '{name}'[/green]")
                except Exception as e:
                    console.print(f"[red]Error saving: {e}[/red]")

        elif choice == "2":
            query = Prompt.ask("Search query")
            try:
                results = search(query)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                continue

            results = show_search_results(results)
            if results:
                pick = Prompt.ask("Explore a result? Enter number (or Enter to skip)", default="")
                if pick.strip().isdigit():
                    idx = int(pick) - 1
                    if 0 <= idx < len(results):
                        depth = Prompt.ask("Depth (1-3)", default="1")
                        try:
                            depth = max(1, min(3, int(depth)))
                        except ValueError:
                            depth = 1
                        try:
                            data = get_graph(results[idx], depth)
                            show_graph(data, results[idx])
                        except Exception as e:
                            console.print(f"[red]Error: {e}[/red]")

        elif choice == "3":
            try:
                graphs = list_graphs()
                show_saved_graphs(graphs)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

        elif choice == "4":
            try:
                graphs = list_graphs()
                show_saved_graphs(graphs)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                continue

            if not graphs:
                continue

            gid = Prompt.ask("Enter graph ID to load")
            try:
                saved = load_graph(int(gid))
                show_graph(saved["data"], saved["root"])
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

        else:
            console.print("[red]Invalid choice.[/red]")


if __name__ == "__main__":
    main()
