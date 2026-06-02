"""
Synthesis Report Generator
===========================
Produces a clean synthesis report: SOP expression, mapped netlist,
area estimate, and critical path delay. Flags timing violations when a
target clock period is provided.
"""

import os
import datetime


def generate_report(spec, sop_terms: list, netlist,
                    target_period_ps: float = None) -> str:
    lines = []
    sep  = "=" * 66
    sep2 = "-" * 66
    now  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines += [
        sep,
        "  MINI LOGIC SYNTHESIS  —  Synthesis Report",
        sep,
        f"  Generated : {now}",
        f"  Function  : {spec.output_name}({', '.join(spec.var_names)})",
        f"  Variables : {spec.num_vars}",
        f"  Minterms  : {sorted(spec.minterms)}",
        f"  Don't-care: {sorted(spec.dont_cares)}",
        sep2,
    ]

    # ── Minimized SOP ────────────────────────────────────────────────────────
    lines += ["", "  [1] MINIMIZED SOP EXPRESSION", ""]
    if not sop_terms:
        lines.append("      f = 0   (always FALSE)")
    else:
        terms_str = [t.to_sop_term(spec.num_vars, spec.var_names) for t in sop_terms]
        lines.append(f"      {spec.output_name} = {' + '.join(terms_str)}")
        lines.append(f"      Product terms  : {len(sop_terms)}")
        total_lits = sum(
            sum(1 for i in range(spec.num_vars) if not (t.mask & (1 << i)))
            for t in sop_terms
        )
        lines.append(f"      Total literals : {total_lits}")

    # ── Mapped Netlist ───────────────────────────────────────────────────────
    lines += ["", sep2, "", "  [2] TECHNOLOGY-MAPPED NETLIST", ""]
    if not netlist.gates:
        lines.append("      No gates (constant function)")
    else:
        lines.append(f"      {'Instance':<24} {'Cell':<8} {'Inputs':<28} {'Output'}")
        lines.append(f"      {'-'*24} {'-'*8} {'-'*28} {'-'*8}")
        for g in netlist.gates:
            inp_str = ", ".join(g.inputs)
            lines.append(f"      {g.instance_name:<24} {g.cell.name:<8} {inp_str:<28} {g.output}")

    # ── Area & Timing ────────────────────────────────────────────────────────
    lines += ["", sep2, "", "  [3] AREA & TIMING SUMMARY", ""]
    area  = netlist.total_area
    delay = netlist.critical_path_delay
    lines.append(f"      Gate count          : {len(netlist.gates)}")
    lines.append(f"      Total cell area     : {area:.2f}  (arb. units)")
    lines.append(f"      Critical path delay : {delay:.1f} ps")

    if target_period_ps is not None:
        slack = target_period_ps - delay
        lines.append(f"      Target clock period : {target_period_ps:.1f} ps")
        lines.append(f"      Slack               : {slack:+.1f} ps")
        lines.append("")
        lines.append("      ✓  TIMING MET" if slack >= 0
                     else f"      ✗  TIMING VIOLATION  (WNS = {slack:.1f} ps)")

    lines += ["", sep, ""]
    return "\n".join(lines)


def save_report(report_str: str, output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report_str)
    print(f"  Report → {output_path}")
