"""
Timing Path Visualizer
=======================
Draws the critical timing path as a DAG using matplotlib.

Each node is a labelled box showing arrival time and slack.
Critical path edges are highlighted in red; non-critical in grey.
The layout is strictly left-to-right (topological order) to match
how engineers read path reports in PrimeTime.

Usage (standalone):
  from visualize.timing_path_plot import plot_critical_path
  plot_critical_path(graph, sta_results, out_path="reports/critical_path.png")
"""

import os
import math
from typing import List, Dict, Optional

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyArrowPatch
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def plot_critical_path(graph, sta_results: dict, out_path: str,
                       clock_period_ps: float = None) -> Optional[str]:
    """
    Plot the critical timing path as a node-edge diagram.

    Args:
        graph          : TimingGraph with arrival/required times populated
        sta_results    : dict from run_sta (keys: critical_path, wns, tns)
        out_path       : PNG output file path
        clock_period_ps: Used for title annotation

    Returns:
        out_path on success, None if matplotlib unavailable.
    """
    if not HAS_MPL:
        print("  [viz] matplotlib not available — skipping critical path plot")
        return None

    critical_path: List[str] = sta_results.get("critical_path", [])
    if not critical_path:
        print("  [viz] No critical path found — skipping plot")
        return None

    wns = sta_results.get("wns", 0.0)

    # ── Layout: evenly space nodes left-to-right ────────────────────────────
    n = len(critical_path)
    fig_w = max(10, n * 2.2)
    fig, ax = plt.subplots(figsize=(fig_w, 4.5))
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(-0.5, 1.5)
    ax.axis("off")

    NODE_W, NODE_H = 1.6, 0.7
    y_center = 0.5

    pos = {name: (i, y_center) for i, name in enumerate(critical_path)}

    # ── Draw edges (arrows) ─────────────────────────────────────────────────
    for i in range(len(critical_path) - 1):
        src = critical_path[i]
        dst = critical_path[i + 1]
        x0, y0 = pos[src]
        x1, y1 = pos[dst]
        ax.annotate(
            "",
            xy   =(x1 - NODE_W / 2 + 0.05, y1),
            xytext=(x0 + NODE_W / 2 - 0.05, y0),
            arrowprops=dict(
                arrowstyle="-|>",
                color="#cc2222",
                lw=2.0,
                connectionstyle="arc3,rad=0.0",
            ),
        )

    # ── Draw nodes (rounded rectangles + text) ──────────────────────────────
    for i, name in enumerate(critical_path):
        if name not in graph.nodes:
            continue
        node = graph.nodes[name]
        x, y = pos[name]

        slack = node.slack if node.required_time < float("inf") else float("inf")
        is_violated = slack < 0

        # Box color: red tint if slack < 0, blue if PI, else light grey
        if node.is_pi:
            facecolor = "#ddeeff"
            edgecolor = "#2255aa"
        elif is_violated:
            facecolor = "#ffe5e5"
            edgecolor = "#cc2222"
        else:
            facecolor = "#f0f4f0"
            edgecolor = "#447744"

        rect = mpatches.FancyBboxPatch(
            (x - NODE_W / 2, y - NODE_H / 2),
            NODE_W, NODE_H,
            boxstyle="round,pad=0.05",
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=1.8,
            zorder=2,
        )
        ax.add_patch(rect)

        # Node name
        label = name if len(name) <= 12 else name[:11] + "…"
        ax.text(x, y + 0.15, label,
                ha="center", va="center", fontsize=8.5, fontweight="bold",
                color="#111111", zorder=3)

        # Arrival time
        ax.text(x, y - 0.05, f"AT={node.arrival_time:.1f}ps",
                ha="center", va="center", fontsize=7, color="#333333", zorder=3)

        # Slack
        if node.required_time < float("inf"):
            slack_color = "#cc0000" if is_violated else "#227722"
            ax.text(x, y - 0.22, f"slk={slack:+.1f}ps",
                    ha="center", va="center", fontsize=6.5,
                    color=slack_color, zorder=3)

    # ── Title ────────────────────────────────────────────────────────────────
    period_str = f"  |  period={clock_period_ps:.0f}ps" if clock_period_ps else ""
    status_str = f"WNS={wns:+.1f}ps  ({'VIOLATION' if wns < 0 else 'MET'})"
    ax.set_title(
        f"Critical Timing Path  —  {status_str}{period_str}",
        fontsize=11, fontweight="bold",
        color="#cc2222" if wns < 0 else "#225522",
        pad=10,
    )

    # Legend
    legend_items = [
        mpatches.Patch(facecolor="#ddeeff", edgecolor="#2255aa", label="Primary Input"),
        mpatches.Patch(facecolor="#f0f4f0", edgecolor="#447744", label="Gate Output (MET)"),
        mpatches.Patch(facecolor="#ffe5e5", edgecolor="#cc2222", label="Gate Output (VIOLATED)"),
    ]
    ax.legend(handles=legend_items, loc="upper left", fontsize=7,
              framealpha=0.85, ncol=3)

    plt.tight_layout()
    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Plot → {out_path}")
    return out_path
