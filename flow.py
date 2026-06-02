#!/usr/bin/env python3
"""
RTL-to-Timing Pipeline — Python Orchestrator
=============================================
Single entry point called by run_flow.tcl (or directly from the CLI).

Modes:
  --mode syn   : Run logic synthesis only
                 Input  : Boolean function spec (.txt)
                 Output : mapped netlist (.v) + synthesis report (.txt) + charts
  --mode sta   : Run STA only
                 Input  : Gate-level Verilog (.v) + Liberty (.lib)
                 Output : STA report (.txt) + timing path plot
  --mode full  : Run synthesis → STA end-to-end
                 Input  : Boolean function spec (.txt)
                 Output : all of the above + combined HTML report

This chain mirrors:
  Design Compiler (synthesis) → PrimeTime (STA) → Liberty NCX (lib gen)

Usage:
  python flow.py --mode full --design examples/full_adder_sum.txt \\
                 --lib-json lib/cells.json --lib lib/cells.lib \\
                 --period 200 --out-dir reports

  python flow.py --mode sta  --netlist reports/full_adder_sum_mapped.v \\
                 --lib lib/cells.lib --period 200
"""

import sys
import os
import argparse

# ── Path setup: make src packages importable ─────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "src", "synthesis"))
sys.path.insert(0, os.path.join(_HERE, "src", "sta"))
sys.path.insert(0, os.path.join(_HERE, "src", "visualize"))
sys.path.insert(0, os.path.join(_HERE, "src"))

from synthesis.parser          import parse_file
from synthesis.quine_mccluskey import minimize
from synthesis.tech_mapper     import load_library, map_sop_to_gates
from synthesis.reporter        import generate_report as syn_report, save_report as syn_save

from sta.liberty_parser import parse_lib_verbose
from sta.netlist_parser import parse_verilog
from sta.timing_graph   import build_timing_graph
from sta.sta            import run_sta
from sta.reporter       import generate_sta_report, save_report as sta_save

from visualize.timing_path_plot import plot_critical_path
from visualize.syn_chart        import plot_synthesis_summary
from visualize.html_report      import generate_html_report


# ─────────────────────────────────────────────────────────────────────────────
# Synthesis step
# ─────────────────────────────────────────────────────────────────────────────

def run_synthesis(design_path: str, lib_json_path: str,
                  period_ps: float, out_dir: str):
    """
    Run QM minimization + technology mapping.
    Returns (spec, sop_terms, netlist, netlist_verilog_path).
    """
    _banner("SYNTHESIS", f"Design: {design_path}")

    print(f"\n  [1/3] Parsing function spec: {design_path}")
    spec = parse_file(design_path)
    print(f"        Variables : {spec.var_names}")
    print(f"        Minterms  : {sorted(spec.minterms)}")
    print(f"        Don't-care: {sorted(spec.dont_cares)}")

    print(f"\n  [2/3] Quine-McCluskey minimization …")
    sop_terms = minimize(spec.minterms, spec.dont_cares, spec.num_vars)
    print(f"        Prime implicants in cover: {len(sop_terms)}")
    for t in sop_terms:
        print(f"          {t.to_sop_term(spec.num_vars, spec.var_names)}")

    print(f"\n  [3/3] Technology mapping: {lib_json_path}")
    library = load_library(lib_json_path)
    design_name = os.path.splitext(os.path.basename(design_path))[0]
    netlist = map_sop_to_gates(sop_terms, spec.var_names, spec.num_vars,
                               library, output_name=spec.output_name)

    os.makedirs(out_dir, exist_ok=True)

    # Save Verilog netlist
    netlist_path = os.path.join(out_dir, f"{design_name}_mapped.v")
    with open(netlist_path, "w") as f:
        f.write(netlist.to_verilog(module_name=design_name))
    print(f"\n  Verilog netlist → {netlist_path}")

    # Save synthesis text report
    report_str  = syn_report(spec, sop_terms, netlist, target_period_ps=period_ps)
    report_path = os.path.join(out_dir, f"{design_name}_syn.rpt")
    syn_save(report_str, report_path)
    print(report_str)

    return spec, sop_terms, netlist, netlist_path, design_name


# ─────────────────────────────────────────────────────────────────────────────
# STA step
# ─────────────────────────────────────────────────────────────────────────────

def run_sta_step(netlist_path: str, lib_path: str,
                 period_ps: float, out_dir: str,
                 design_name: str = None):
    """
    Run graph-based STA on a gate-level Verilog netlist.
    Returns (graph, sta_results).
    """
    if design_name is None:
        design_name = os.path.splitext(os.path.basename(netlist_path))[0]

    _banner("STA", f"Netlist: {netlist_path}  |  Period: {period_ps} ps")

    print(f"\n  [1/4] Loading Liberty library: {lib_path}")
    lib_cells = parse_lib_verbose(lib_path)

    print(f"\n  [2/4] Parsing netlist: {netlist_path}")
    nl = parse_verilog(netlist_path)
    print(f"        Module  : {nl.module_name}")
    print(f"        Inputs  : {nl.primary_inputs}")
    print(f"        Outputs : {nl.primary_outputs}")
    print(f"        Gates   : {len(nl.gates)}")
    if nl.clock_net:
        print(f"        Clock   : {nl.clock_net}")

    # Use period from netlist annotation if not overridden
    eff_period = period_ps if period_ps else (nl.clock_period_ps or 200.0)

    print(f"\n  [3/4] Building timing graph …")
    graph = build_timing_graph(nl, lib_cells)
    print(f"        Nodes : {len(graph.nodes)}")
    print(f"        Edges : {len(graph.edges)}")

    print(f"\n  [4/4] Running STA (period = {eff_period:.0f} ps) …")
    sta_results = run_sta(graph, eff_period, nl.input_delays)

    os.makedirs(out_dir, exist_ok=True)

    # Save STA text report
    report_str  = generate_sta_report(graph, sta_results, eff_period, design_name)
    report_path = os.path.join(out_dir, f"{design_name}_sta.rpt")
    sta_save(report_str, report_path)
    print(report_str)

    return graph, sta_results, eff_period


# ─────────────────────────────────────────────────────────────────────────────
# Visualization step
# ─────────────────────────────────────────────────────────────────────────────

def run_visualize(graph, sta_results: dict, netlist,
                  spec, sop_terms: list,
                  clock_period_ps: float, out_dir: str,
                  design_name: str = "design"):
    """
    Generate all plots and the combined HTML report.
    Returns dict of output paths.
    """
    _banner("VISUALIZE", "Generating plots and HTML report")

    paths = {}

    # Timing path plot
    paths["timing_path"] = plot_critical_path(
        graph, sta_results,
        out_path=os.path.join(out_dir, f"{design_name}_critical_path.png"),
        clock_period_ps=clock_period_ps,
    )

    # Synthesis chart (only if netlist provided)
    if netlist is not None:
        paths["syn_chart"] = plot_synthesis_summary(
            netlist,
            out_path=os.path.join(out_dir, f"{design_name}_syn_chart.png"),
            design_name=design_name,
        )
    else:
        paths["syn_chart"] = None

    # HTML report (only in full mode where we have both spec and graph)
    if spec is not None:
        paths["html"] = generate_html_report(
            design_name=design_name,
            spec=spec,
            sop_terms=sop_terms or [],
            netlist=netlist,
            graph=graph,
            sta_results=sta_results,
            clock_period_ps=clock_period_ps,
            syn_chart_path=paths.get("syn_chart"),
            timing_path_path=paths.get("timing_path"),
            out_path=os.path.join(out_dir, f"{design_name}_report.html"),
        )

    return paths


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = _parse_args()
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    mode = args.mode

    if mode == "syn":
        # ── Synthesis only ──────────────────────────────────────────────────
        spec, sop_terms, netlist, netlist_path, design_name = run_synthesis(
            args.design, args.lib_json, args.period, out_dir
        )
        # Still generate the synthesis chart
        run_visualize(
            graph=None, sta_results={}, netlist=netlist,
            spec=None, sop_terms=None,
            clock_period_ps=args.period, out_dir=out_dir,
            design_name=design_name,
        )

    elif mode == "sta":
        # ── STA only ────────────────────────────────────────────────────────
        netlist_path = args.netlist
        design_name  = os.path.splitext(os.path.basename(netlist_path))[0]
        graph, sta_results, eff_period = run_sta_step(
            netlist_path, args.lib, args.period, out_dir, design_name
        )
        run_visualize(
            graph=graph, sta_results=sta_results, netlist=None,
            spec=None, sop_terms=None,
            clock_period_ps=eff_period, out_dir=out_dir,
            design_name=design_name,
        )

    elif mode == "full":
        # ── Full flow: synthesis → STA → visualize ──────────────────────────
        spec, sop_terms, netlist, netlist_path, design_name = run_synthesis(
            args.design, args.lib_json, args.period, out_dir
        )
        graph, sta_results, eff_period = run_sta_step(
            netlist_path, args.lib, args.period, out_dir, design_name
        )
        paths = run_visualize(
            graph=graph, sta_results=sta_results, netlist=netlist,
            spec=spec, sop_terms=sop_terms,
            clock_period_ps=eff_period, out_dir=out_dir,
            design_name=design_name,
        )
        print(f"\n{'='*66}")
        print(f"  FLOW COMPLETE")
        print(f"{'='*66}")
        print(f"  Outputs in: {os.path.abspath(out_dir)}/")
        for label, path in paths.items():
            if path:
                print(f"    {label:<18} → {os.path.basename(path)}")
        print(f"{'='*66}\n")

    else:
        print(f"Unknown mode '{mode}'. Choose: syn | sta | full", file=sys.stderr)
        sys.exit(1)


def _banner(step: str, detail: str):
    print(f"\n{'='*66}")
    print(f"  [{step}]  {detail}")
    print(f"{'='*66}")


def _parse_args():
    p = argparse.ArgumentParser(
        description="RTL-to-Timing Pipeline — Synopsys_Projects_v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--mode",     choices=["syn", "sta", "full"], default="full",
                   help="Pipeline mode (default: full)")
    p.add_argument("--design",   default="examples/full_adder_sum.txt",
                   help="Boolean function spec (.txt) — used in syn/full modes")
    p.add_argument("--netlist",  default=None,
                   help="Gate-level Verilog (.v) — used in sta mode")
    p.add_argument("--lib-json", dest="lib_json", default="lib/cells.json",
                   help="Cell library JSON — used by synthesis tech mapper")
    p.add_argument("--lib",      default="lib/cells.lib",
                   help="Liberty file (.lib) — used by STA engine")
    p.add_argument("--period",   type=float, default=200.0,
                   help="Target clock period in ps (default: 200)")
    p.add_argument("--out-dir",  dest="out_dir", default="reports",
                   help="Output directory (default: reports)")
    return p.parse_args()


if __name__ == "__main__":
    main()
