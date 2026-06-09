"""
Wiki Explorer - GUI (Tkinter)
A desktop window that visualizes the Wikipedia graph.

Usage:
    python gui/main.py
"""

import math
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

sys.path.insert(0, ".")

from client.api import get_graph, list_graphs, load_graph, save_graph

COLORS = ["#7c9ef8", "#50c896", "#f5a623", "#e05c5c"]
BG = "#0f1117"
PANEL_BG = "#1a1d27"
BORDER = "#2a2d3e"
TEXT = "#e0e0e0"
DIM = "#888888"


class WikiExplorerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Wiki Rabbit Hole Explorer")
        self.root.geometry("1100x700")
        self.root.configure(bg=BG)

        self.graph_data = {"nodes": [], "edges": []}
        self.node_positions = {}
        self.node_items = {}
        self.dragging = None
        self.drag_offset = (0, 0)

        self._build_ui()

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=PANEL_BG, pady=10)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="Wiki Rabbit Hole",
            bg=PANEL_BG,
            fg="#7c9ef8",
            font=("Helvetica", 14, "bold"),
        ).pack(side=tk.LEFT, padx=16)

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(
            header,
            textvariable=self.search_var,
            bg="#0f1117",
            fg=TEXT,
            insertbackground=TEXT,
            relief=tk.FLAT,
            font=("Helvetica", 12),
            width=30,
        )
        search_entry.pack(side=tk.LEFT, padx=8, ipady=6, ipadx=6)
        search_entry.bind("<Return>", lambda e: self.do_explore())

        tk.Label(header, text="Depth:", bg=PANEL_BG, fg=DIM, font=("Helvetica", 10)).pack(
            side=tk.LEFT, padx=(8, 2)
        )
        self.depth_var = tk.IntVar(value=1)
        depth_spin = ttk.Spinbox(
            header, from_=1, to=3, textvariable=self.depth_var, width=3, font=("Helvetica", 11)
        )
        depth_spin.pack(side=tk.LEFT)

        explore_btn = tk.Button(
            header,
            text="Explore",
            command=self.do_explore,
            bg="#7c9ef8",
            fg=BG,
            font=("Helvetica", 11, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=4,
            cursor="hand2",
        )
        explore_btn.pack(side=tk.LEFT, padx=8)

        save_btn = tk.Button(
            header,
            text="Save Graph",
            command=self.do_save,
            bg=PANEL_BG,
            fg="#7c9ef8",
            font=("Helvetica", 10),
            relief=tk.FLAT,
            padx=8,
            pady=4,
            cursor="hand2",
        )
        save_btn.pack(side=tk.LEFT, padx=4)

        load_btn = tk.Button(
            header,
            text="Load Graph",
            command=self.do_load,
            bg=PANEL_BG,
            fg="#7c9ef8",
            font=("Helvetica", 10),
            relief=tk.FLAT,
            padx=8,
            pady=4,
            cursor="hand2",
        )
        load_btn.pack(side=tk.LEFT, padx=4)

        self.status_var = tk.StringVar(value="Search for a topic to begin")
        tk.Label(
            header, textvariable=self.status_var, bg=PANEL_BG, fg=DIM, font=("Helvetica", 10)
        ).pack(side=tk.RIGHT, padx=16)

        # ── Main area ─────────────────────────────────────────────────────────
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill=tk.BOTH, expand=True)

        # Canvas
        self.canvas = tk.Canvas(main, bg=BG, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)

        # Tooltip
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.withdraw()
        self.tooltip.overrideredirect(True)
        self.tooltip.configure(bg=PANEL_BG)
        self.tooltip_label = tk.Label(
            self.tooltip,
            bg=PANEL_BG,
            fg=TEXT,
            font=("Helvetica", 10),
            wraplength=250,
            justify=tk.LEFT,
            padx=10,
            pady=8,
        )
        self.tooltip_label.pack()

    def set_status(self, msg):
        self.status_var.set(msg)
        self.root.update_idletasks()

    def do_explore(self):
        title = self.search_var.get().strip()
        if not title:
            messagebox.showwarning("Input needed", "Enter a topic to explore.")
            return
        depth = self.depth_var.get()
        self.set_status(f"Fetching '{title}'...")
        try:
            data = get_graph(title, depth)
        except Exception as e:
            messagebox.showerror("Error", f"Could not fetch graph.\n{e}\n\nIs the server running?")
            self.set_status("Error fetching graph")
            return
        self.graph_data = data
        self.set_status(f"{len(data['nodes'])} nodes, {len(data['edges'])} edges")
        self._layout_and_draw()

    def _layout_and_draw(self):
        nodes = self.graph_data["nodes"]
        edges = self.graph_data["edges"]
        self.canvas.delete("all")
        self.node_positions = {}
        self.node_items = {}

        if not nodes:
            self.canvas.create_text(
                550, 350, text="No nodes found", fill=DIM, font=("Helvetica", 14)
            )
            return

        W = self.canvas.winfo_width() or 800
        H = self.canvas.winfo_height() or 600
        cx, cy = W / 2, H / 2

        # Place root at center, others in rings by depth
        by_depth = {}
        for n in nodes:
            d = n.get("depth", 0)
            by_depth.setdefault(d, []).append(n)

        for depth, dnodes in by_depth.items():
            if depth == 0:
                for n in dnodes:
                    self.node_positions[n["id"]] = (cx, cy)
            else:
                radius = depth * 160
                count = len(dnodes)
                for i, n in enumerate(dnodes):
                    angle = (2 * math.pi * i / count) - math.pi / 2
                    x = cx + radius * math.cos(angle)
                    y = cy + radius * math.sin(angle)
                    self.node_positions[n["id"]] = (x, y)

        # Draw edges
        for e in edges:
            src = (
                e.get("source")
                if isinstance(e.get("source"), str)
                else e.get("source", {}).get("id", "")
            )
            tgt = (
                e.get("target")
                if isinstance(e.get("target"), str)
                else e.get("target", {}).get("id", "")
            )
            if src in self.node_positions and tgt in self.node_positions:
                x1, y1 = self.node_positions[src]
                x2, y2 = self.node_positions[tgt]
                self.canvas.create_line(x1, y1, x2, y2, fill=BORDER, width=1.5, tags="edge")

        # Draw nodes
        for n in nodes:
            nid = n["id"]
            if nid not in self.node_positions:
                continue
            x, y = self.node_positions[nid]
            depth = n.get("depth", 0)
            r = 18 if depth == 0 else 10
            color = COLORS[min(depth, 3)]

            circle = self.canvas.create_oval(
                x - r,
                y - r,
                x + r,
                y + r,
                fill=color,
                outline="white",
                width=1.5,
                tags=("node", nid),
            )
            label = nid if len(nid) <= 18 else nid[:16] + "..."
            text = self.canvas.create_text(
                x, y + r + 10, text=label, fill=TEXT, font=("Helvetica", 9), tags=("label", nid)
            )
            self.node_items[nid] = (circle, text, n)

            self.canvas.tag_bind(circle, "<Enter>", lambda e, node=n: self.show_tooltip(e, node))
            self.canvas.tag_bind(circle, "<Leave>", lambda e: self.hide_tooltip())
            self.canvas.tag_bind(text, "<Enter>", lambda e, node=n: self.show_tooltip(e, node))
            self.canvas.tag_bind(text, "<Leave>", lambda e: self.hide_tooltip())

    def show_tooltip(self, event, node):
        summary = node.get("summary", "")
        summary = summary[:150] + "..." if len(summary) > 150 else summary
        cats = ", ".join(node.get("categories", [])[:3])
        text = node["id"]
        if summary:
            text += "\n\n" + summary
        if cats:
            text += "\n\n[" + cats + "]"
        self.tooltip_label.config(text=text)
        x = self.root.winfo_rootx() + event.x + 20
        y = self.root.winfo_rooty() + event.y + 20
        self.tooltip.geometry(f"+{x}+{y}")
        self.tooltip.deiconify()
        self.tooltip.lift()

    def hide_tooltip(self):
        self.tooltip.withdraw()

    def on_mouse_press(self, event):
        self.hide_tooltip()
        items = self.canvas.find_closest(event.x, event.y)
        for item in items:
            tags = self.canvas.gettags(item)
            if "node" in tags:
                nid = [t for t in tags if t not in ("node", "current")]
                if nid:
                    self.dragging = nid[0]
                    x, y = self.node_positions[self.dragging]
                    self.drag_offset = (event.x - x, event.y - y)
                    return

    def on_mouse_drag(self, event):
        if self.dragging:
            x = event.x - self.drag_offset[0]
            y = event.y - self.drag_offset[1]
            self.node_positions[self.dragging] = (x, y)
            self._redraw_node(self.dragging)
            self._redraw_edges()

    def on_mouse_release(self, event):
        self.dragging = None

    def _redraw_node(self, nid):
        if nid not in self.node_items:
            return
        circle, text, node = self.node_items[nid]
        x, y = self.node_positions[nid]
        depth = node.get("depth", 0)
        r = 18 if depth == 0 else 10
        self.canvas.coords(circle, x - r, y - r, x + r, y + r)
        self.canvas.coords(text, x, y + r + 10)

    def _redraw_edges(self):
        self.canvas.delete("edge")
        for e in self.graph_data["edges"]:
            src = (
                e.get("source")
                if isinstance(e.get("source"), str)
                else e.get("source", {}).get("id", "")
            )
            tgt = (
                e.get("target")
                if isinstance(e.get("target"), str)
                else e.get("target", {}).get("id", "")
            )
            if src in self.node_positions and tgt in self.node_positions:
                x1, y1 = self.node_positions[src]
                x2, y2 = self.node_positions[tgt]
                self.canvas.create_line(x1, y1, x2, y2, fill=BORDER, width=1.5, tags="edge")
        self.canvas.tag_raise("node")
        self.canvas.tag_raise("label")

    def do_save(self):
        if not self.graph_data["nodes"]:
            messagebox.showinfo("Nothing to save", "Explore a topic first.")
            return
        name = simpledialog.askstring("Save Graph", "Enter a name for this graph:")
        if not name:
            return
        root = self.search_var.get().strip()
        depth = self.depth_var.get()
        try:
            save_graph(name, root, depth, self.graph_data)
            self.set_status(f"Saved as '{name}'")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def do_load(self):
        try:
            graphs = list_graphs()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if not graphs:
            messagebox.showinfo("No saved graphs", "Save a graph first.")
            return

        options = [f"{g['id']}: {g['name']} ({g['root']}, depth {g['depth']})" for g in graphs]
        choice = simpledialog.askstring(
            "Load Graph", "Saved graphs:\n" + "\n".join(options) + "\n\nEnter ID:"
        )
        if not choice:
            return
        try:
            saved = load_graph(int(choice.strip()))
            self.graph_data = saved["data"]
            self.search_var.set(saved["root"])
            self.depth_var.set(saved["depth"])
            self.set_status(f"Loaded '{saved['name']}'")
            self._layout_and_draw()
        except Exception as e:
            messagebox.showerror("Error", str(e))


def main():
    root = tk.Tk()
    _app = WikiExplorerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
