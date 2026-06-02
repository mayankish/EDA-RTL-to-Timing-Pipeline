"""
STA Report Generator
=====================
Produces a PrimeTime-style timing report:
  - Timing summary (WNS, TNS, endpoint count, status)
  - Critical path trace (node-by-node arrival / required / slack)
  - Full endpoint slack table
"""

import datetime
import os


def generate_sta_report(graph, sta_results: dict,
                        clock_period_ps: float,
                        netlist_name: str = "design") -> str:
    lines = []
    sep  = "=" * 66
    sep2 = "-" * 66
    now  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    wns           = sta_results["wns"]
    tns           = sta_results["tns"]
    critical_path = sta_results["critical_path"]
    node_slacks   = sta_results["node_slacks"]

    lines += [
        sep,
        "  MINI STA ENGINE  —  Timing Report",
        sep,
        f"  Generated   : {now}",
        f"  Design      : {netlist_name}",
        f"  Clock period: {clock_period_ps:.1f} ps",
        sep2,
    ]

    # ── Timing Summary ───────────────────────────────────────────────────────
    lines += ["", "  [1] TIMING SUMMARY", ""]
    violated = [n for n, s in node_slacks.items() if s < 0]
    lines += [
        f"      WNS (Worst Negative Slack) : {wns:+.1f} ps",
        f"      TNS (Total Negative Slack) : {tns:+.1f} ps",
        f"      Violating endpoints        : {len(violated)}",
        f"      Total endpoints analyzed   : {len(node_slacks)}",
        "",
        ("      ✓  ALL TIMING CONSTRAINTS MET" if wns >= 0
         else f"      ✗  TIMING VIOLATION — WNS = {wns:.1f} ps"),
    ]

    # ── Critical Path ────────────────────────────────────────────────────────
    lines += ["", sep2, "", "  [2] CRITICAL PATH TRACE", ""]
    if not critical_path:
        lines.append("      (No path found)")
    else:
        lines.append(
            f"      {'Node':<24} {'Arrival (ps)':>14}  {'Required (ps)':>14}  {'Slack':>10}"
        )
        lines.append(f"      {'-'*24} {'-'*14}  {'-'*14}  {'-'*10}")
        for node_name in critical_path:
            if node_name not in graph.nodes:
                continue
            node = graph.nodes[node_name]
            rt_s = f"{node.required_time:.1f}" if node.required_time < float("inf") else "∞"
            sl_s = f"{node.slack:+.1f}"        if node.required_time < float("inf") else "∞"
            lines.append(
                f"      {node_name:<24} {node.arrival_time:>14.1f}  "
                f"{rt_s:>14}  {sl_s:>10}"
            )
        if len(critical_path) >= 2:
            start_at = graph.nodes[critical_path[0]].arrival_time
            end_at   = graph.nodes[critical_path[-1]].arrival_time
            lines += ["", f"      Path delay : {end_at - start_at:.1f} ps"]

    # ── Endpoint Slack Table ─────────────────────────────────────────────────
    lines += ["", sep2, "", "  [3] ENDPOINT SLACK REPORT", ""]
    if node_slacks:
        lines.append(
            f"      {'Endpoint':<26} {'Arrival':>12}  {'Required':>12}  {'Slack':>10}"
        )
        lines.append(f"      {'-'*26} {'-'*12}  {'-'*12}  {'-'*10}")
        for name in sorted(node_slacks, key=lambda n: node_slacks[n]):
            node  = graph.nodes[name]
            rt_s  = f"{node.required_time:.1f}" if node.required_time < float("inf") else "∞"
            s     = node_slacks[name]
            flag  = "  ← VIOLATED" if s < 0 else ""
            lines.append(
                f"      {name:<26} {node.arrival_time:>12.1f}  "
                f"{rt_s:>12}  {s:>+10.1f}{flag}"
            )

    lines += ["", sep, ""]
    return "\n".join(lines)


def save_report(report_str: str, output_path: str):
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report_str)
    print(f"  Report → {output_path}")
