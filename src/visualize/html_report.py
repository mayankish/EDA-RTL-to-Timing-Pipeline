"""
HTML Report Generator
======================
Produces a self-contained, single-file HTML report that summarises both the
synthesis step and the STA step. Plots are embedded as base64 PNGs so the
file is fully portable — no external dependencies.

Mirrors the kind of signoff summary report you'd hand to a design team.

Usage (standalone):
  from visualize.html_report import generate_html_report
  generate_html_report(
      design_name="full_adder",
      spec=spec,
      sop_terms=sop_terms,
      netlist=netlist,
      graph=graph,
      sta_results=sta_results,
      clock_period_ps=200,
      syn_chart_path="reports/syn_chart.png",
      timing_path_path="reports/critical_path.png",
      out_path="reports/report.html",
  )
"""

import os
import base64
import datetime
from typing import Optional


def _embed_image(path: Optional[str]) -> str:
    """Return an <img> tag with base64-encoded PNG, or a placeholder."""
    if not path or not os.path.exists(path):
        return '<p style="color:#999;font-style:italic;">Plot not available</p>'
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'<img src="data:image/png;base64,{b64}" style="max-width:100%;border-radius:6px;">'


def generate_html_report(
    design_name: str,
    spec,                      # FunctionSpec (synthesis input)
    sop_terms: list,
    netlist,                   # MappedNetlist
    graph,                     # TimingGraph
    sta_results: dict,
    clock_period_ps: float,
    syn_chart_path:   Optional[str] = None,
    timing_path_path: Optional[str] = None,
    out_path: str = "reports/report.html",
) -> str:
    """Build and write the HTML report. Returns out_path."""

    now  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wns  = sta_results.get("wns", 0.0)
    tns  = sta_results.get("tns", 0.0)
    crit = sta_results.get("critical_path", [])

    status_color = "#c0392b" if wns < 0 else "#27ae60"
    status_text  = f"TIMING VIOLATION  (WNS = {wns:+.1f} ps)" if wns < 0 \
                   else f"TIMING MET  (WNS = {wns:+.1f} ps)"

    # ── Netlist table rows ───────────────────────────────────────────────────
    gate_rows = ""
    for g in netlist.gates:
        gate_rows += (
            f"<tr><td>{g.instance_name}</td><td>{g.cell.name}</td>"
            f"<td>{', '.join(g.inputs)}</td><td>{g.output}</td>"
            f"<td>{g.cell.area:.1f}</td><td>{g.cell.delay:.1f}</td></tr>\n"
        )

    # ── Critical path table rows ─────────────────────────────────────────────
    path_rows = ""
    for node_name in crit:
        if node_name not in graph.nodes:
            continue
        node = graph.nodes[node_name]
        slack = node.slack if node.required_time < float("inf") else float("inf")
        sl_color = "#c0392b" if slack < 0 else "#27ae60"
        rt_str   = f"{node.required_time:.1f}" if node.required_time < float("inf") else "∞"
        sl_str   = f"{slack:+.1f}" if node.required_time < float("inf") else "∞"
        path_rows += (
            f"<tr><td>{node_name}</td>"
            f"<td>{node.arrival_time:.1f}</td>"
            f"<td>{rt_str}</td>"
            f"<td style='color:{sl_color};font-weight:bold'>{sl_str}</td></tr>\n"
        )

    # ── SOP expression ───────────────────────────────────────────────────────
    if sop_terms:
        sop_str = " + ".join(t.to_sop_term(spec.num_vars, spec.var_names) for t in sop_terms)
    else:
        sop_str = "0"

    # ── Endpoint slack table ─────────────────────────────────────────────────
    node_slacks = sta_results.get("node_slacks", {})
    endpoint_rows = ""
    for name in sorted(node_slacks, key=lambda n: node_slacks[n]):
        node  = graph.nodes[name]
        slack = node_slacks[name]
        sl_c  = "#c0392b" if slack < 0 else "#27ae60"
        rt_s  = f"{node.required_time:.1f}" if node.required_time < float("inf") else "∞"
        endpoint_rows += (
            f"<tr><td>{name}</td>"
            f"<td>{node.arrival_time:.1f}</td>"
            f"<td>{rt_s}</td>"
            f"<td style='color:{sl_c};font-weight:bold'>{slack:+.1f}</td></tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>RTL-to-Timing Report — {design_name}</title>
<style>
  :root {{
    --bg: #f5f6fa; --card: #ffffff; --accent: #2c3e50;
    --green: #27ae60; --red: #c0392b; --blue: #2980b9;
    --border: #dde1e7; --muted: #7f8c8d;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: var(--bg);
          color: #2c3e50; font-size: 14px; line-height: 1.5; }}
  header {{ background: var(--accent); color: white; padding: 22px 32px; }}
  header h1 {{ font-size: 22px; font-weight: 700; }}
  header .sub {{ font-size: 12px; opacity: 0.7; margin-top: 4px; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px; }}
  .status-banner {{
    padding: 14px 20px; border-radius: 8px; margin-bottom: 24px;
    font-size: 16px; font-weight: 700; color: white;
    background: {status_color};
  }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }}
  .card {{ background: var(--card); border: 1px solid var(--border);
           border-radius: 8px; padding: 20px; }}
  .card h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: .05em;
              color: var(--muted); margin-bottom: 12px; border-bottom: 1px solid var(--border);
              padding-bottom: 8px; }}
  .kv {{ display: flex; justify-content: space-between; padding: 4px 0;
         border-bottom: 1px dashed #eee; }}
  .kv:last-child {{ border-bottom: none; }}
  .kv .label {{ color: var(--muted); }}
  .kv .value {{ font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  th {{ background: var(--accent); color: white; padding: 7px 10px;
       text-align: left; font-weight: 600; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid var(--border); }}
  tr:nth-child(even) td {{ background: #f9fafb; }}
  .section {{ margin-bottom: 28px; }}
  .section h2 {{ font-size: 16px; font-weight: 700; margin-bottom: 12px;
                 padding-left: 10px; border-left: 4px solid var(--accent); }}
  .sop-box {{ background: #1e2a38; color: #a8d8a8; font-family: monospace;
              font-size: 13px; padding: 14px 18px; border-radius: 6px;
              overflow-x: auto; white-space: pre-wrap; }}
  .plot-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .plot-card {{ background: var(--card); border: 1px solid var(--border);
                border-radius: 8px; padding: 16px; }}
  .plot-card h3 {{ font-size: 13px; color: var(--muted); margin-bottom: 10px; }}
  footer {{ text-align: center; font-size: 11px; color: var(--muted);
            padding: 20px; border-top: 1px solid var(--border); margin-top: 8px; }}
  @media (max-width: 700px) {{
    .grid2, .plot-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<header>
  <h1>RTL-to-Timing Signoff Report</h1>
  <div class="sub">Design: {design_name} &nbsp;|&nbsp; Generated: {now}</div>
</header>

<div class="container">

  <!-- Status banner -->
  <div class="status-banner">&#9654; {status_text}</div>

  <!-- Key metrics -->
  <div class="grid2">
    <div class="card">
      <h2>Synthesis Summary</h2>
      <div class="kv"><span class="label">Output function</span>
        <span class="value">{spec.output_name}({', '.join(spec.var_names)})</span></div>
      <div class="kv"><span class="label">Variables</span>
        <span class="value">{spec.num_vars}</span></div>
      <div class="kv"><span class="label">Minterms</span>
        <span class="value">{len(spec.minterms)}</span></div>
      <div class="kv"><span class="label">Product terms (SOP)</span>
        <span class="value">{len(sop_terms)}</span></div>
      <div class="kv"><span class="label">Gate count</span>
        <span class="value">{len(netlist.gates)}</span></div>
      <div class="kv"><span class="label">Total area</span>
        <span class="value">{netlist.total_area:.2f} arb. units</span></div>
      <div class="kv"><span class="label">Comb. path delay</span>
        <span class="value">{netlist.critical_path_delay:.1f} ps</span></div>
    </div>
    <div class="card">
      <h2>STA Summary</h2>
      <div class="kv"><span class="label">Clock period</span>
        <span class="value">{clock_period_ps:.1f} ps</span></div>
      <div class="kv"><span class="label">WNS</span>
        <span class="value" style="color:{status_color}">{wns:+.1f} ps</span></div>
      <div class="kv"><span class="label">TNS</span>
        <span class="value" style="color:{status_color}">{tns:+.1f} ps</span></div>
      <div class="kv"><span class="label">Endpoints analyzed</span>
        <span class="value">{len(node_slacks)}</span></div>
      <div class="kv"><span class="label">Violating endpoints</span>
        <span class="value" style="color:{status_color}">
          {sum(1 for s in node_slacks.values() if s < 0)}
        </span></div>
      <div class="kv"><span class="label">Critical path nodes</span>
        <span class="value">{len(crit)}</span></div>
    </div>
  </div>

  <!-- SOP expression -->
  <div class="section">
    <h2>Minimized Boolean Expression</h2>
    <div class="sop-box">{spec.output_name} = {sop_str}</div>
  </div>

  <!-- Plots -->
  <div class="section">
    <h2>Visual Analysis</h2>
    <div class="plot-grid">
      <div class="plot-card">
        <h3>Critical Timing Path</h3>
        {_embed_image(timing_path_path)}
      </div>
      <div class="plot-card">
        <h3>Synthesis Coverage</h3>
        {_embed_image(syn_chart_path)}
      </div>
    </div>
  </div>

  <!-- Mapped netlist table -->
  <div class="section">
    <h2>Technology-Mapped Netlist</h2>
    <table>
      <tr><th>Instance</th><th>Cell</th><th>Inputs</th><th>Output</th>
          <th>Area</th><th>Delay (ps)</th></tr>
      {gate_rows}
    </table>
  </div>

  <!-- Critical path table -->
  <div class="section">
    <h2>Critical Path Trace</h2>
    <table>
      <tr><th>Node</th><th>Arrival (ps)</th><th>Required (ps)</th><th>Slack (ps)</th></tr>
      {path_rows}
    </table>
  </div>

  <!-- Endpoint slack table -->
  <div class="section">
    <h2>All Endpoint Slacks</h2>
    <table>
      <tr><th>Endpoint</th><th>Arrival (ps)</th><th>Required (ps)</th><th>Slack (ps)</th></tr>
      {endpoint_rows}
    </table>
  </div>

</div>
<footer>
  Generated by RTL-to-Timing Pipeline &nbsp;|&nbsp; Synopsys_Projects_v2/01_rtl_to_timing
</footer>
</body>
</html>
"""

    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  HTML report → {out_path}")
    return out_path
