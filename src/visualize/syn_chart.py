"""
Synthesis Coverage Chart
=========================
Produces a two-panel matplotlib figure:
  Left  — Bar chart: gate count by cell type
  Right — Pie chart: area contribution by cell type

This is analogous to the area/power breakdown view in Synopsys Design Compiler's
GUI and is the kind of plot you'd include in a signoff presentation.

Usage (standalone):
  from visualize.syn_chart import plot_synthesis_summary
  plot_synthesis_summary(netlist, out_path="reports/syn_chart.png")
"""

import os
from typing import Optional

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# Consistent color palette (one per common cell type)
_PALETTE = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2",
    "#59a14f", "#edc948", "#b07aa1", "#ff9da7",
]


def plot_synthesis_summary(netlist, out_path: str,
                           design_name: str = "design") -> Optional[str]:
    """
    Two-panel chart: gate-count bar + area pie.

    Args:
        netlist     : MappedNetlist (from tech_mapper)
        out_path    : PNG output file path
        design_name : Label shown in the title

    Returns:
        out_path on success, None if matplotlib unavailable or no gates.
    """
    if not HAS_MPL:
        print("  [viz] matplotlib not available — skipping synthesis chart")
        return None

    gate_counts = netlist.gate_type_counts
    gate_areas  = netlist.gate_area_by_type

    if not gate_counts:
        print("  [viz] No gates in netlist — skipping synthesis chart")
        return None

    cell_types = sorted(gate_counts.keys())
    counts     = [gate_counts[c] for c in cell_types]
    areas      = [gate_areas.get(c, 0.0) for c in cell_types]
    colors     = [_PALETTE[i % len(_PALETTE)] for i in range(len(cell_types))]

    fig, (ax_bar, ax_pie) = plt.subplots(1, 2, figsize=(11, 4.5))
    fig.suptitle(
        f"Synthesis Summary — {design_name}\n"
        f"Total gates: {sum(counts)}  |  Total area: {sum(areas):.2f} arb. units",
        fontsize=11, fontweight="bold", y=1.02,
    )

    # ── Left: gate count bar chart ───────────────────────────────────────────
    x = range(len(cell_types))
    bars = ax_bar.bar(x, counts, color=colors, edgecolor="white", linewidth=0.8, width=0.6)
    ax_bar.set_xticks(list(x))
    ax_bar.set_xticklabels(cell_types, fontsize=9)
    ax_bar.set_ylabel("Gate count", fontsize=9)
    ax_bar.set_title("Gate Count by Cell Type", fontsize=10)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.set_facecolor("#fafafa")

    # Annotate bars with count
    for bar, cnt in zip(bars, counts):
        ax_bar.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.05,
            str(cnt),
            ha="center", va="bottom", fontsize=8, fontweight="bold",
        )

    # ── Right: area pie chart ────────────────────────────────────────────────
    wedge_props = {"edgecolor": "white", "linewidth": 1.5}
    wedges, texts, autotexts = ax_pie.pie(
        areas,
        labels=cell_types,
        colors=colors,
        autopct="%1.1f%%",
        startangle=140,
        wedgeprops=wedge_props,
        textprops={"fontsize": 8.5},
    )
    for at in autotexts:
        at.set_fontsize(7.5)
        at.set_color("white")
        at.set_fontweight("bold")
    ax_pie.set_title("Area Contribution by Cell Type", fontsize=10)

    plt.tight_layout()
    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Plot → {out_path}")
    return out_path
