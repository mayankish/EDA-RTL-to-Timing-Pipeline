# RTL-to-Timing Pipeline

> **Transistor to signoff, end-to-end — in Python and TCL.**

A from-scratch implementation of the core EDA flow that Synopsys Design Compiler and PrimeTime execute commercially. Given a Boolean function as input, the pipeline minimizes its logic, maps it to standard cells, emits a gate-level Verilog netlist, builds a timing graph, runs full static timing analysis, and produces publication-quality plots and a self-contained HTML signoff report — all driven by a TCL script that mirrors real `dc_shell` / `pt_shell` usage.

```
Boolean Function (.txt)
        │
        ▼
┌───────────────────┐
│  Quine-McCluskey  │  ← Logic minimization  (mirrors DC's  compile_ultra)
│   Minimization    │
└────────┬──────────┘
         │  Minimized SOP
         ▼
┌───────────────────┐
│  Technology       │  ← Cell mapping        (mirrors DC's  map_to_library)
│  Mapping          │
└────────┬──────────┘
         │  Gate-level Verilog (.v)
         ▼
┌───────────────────┐
│  Liberty Parser   │  ← Delay lookup        (mirrors PT's  read_lib)
│  + Timing Graph   │
└────────┬──────────┘
         │  Weighted DAG
         ▼
┌───────────────────┐
│  Static Timing    │  ← AT/RT propagation   (mirrors PT's  report_timing)
│  Analysis (STA)   │
└────────┬──────────┘
         │
         ▼
  Plots + HTML Report
```

---

## Why This Project Exists

Every Synopsys EDA tool — Design Compiler, PrimeTime, Liberty NCX — implements one step of this chain. Most engineers use these tools as black boxes. This project breaks each step open and implements it from first principles:

| This project | Synopsys commercial equivalent |
|---|---|
| Quine-McCluskey minimizer | DC `compile_ultra` (logic optimization kernel) |
| Technology mapper | DC `map_to_technology` / `compile` |
| Liberty `.lib` parser | PrimeTime `read_lib`, Liberty NCX |
| Timing graph builder | PrimeTime internal DAG construction |
| Forward/backward STA | PrimeTime `report_timing`, `report_timing -path full` |
| TCL driver script | `dc_shell -f run.tcl` / `pt_shell -f run.tcl` |
| HTML signoff report | StarRC / Fusion Compiler signoff summary |

The pipeline is intentionally self-contained — no SPICE, no commercial license, no Cadence or Synopsys install required. The algorithms are real; only the technology node and cell library are simplified.

---

## Table of Contents

- [Features](#features)
- [Repository Structure](#repository-structure)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Detailed Usage](#detailed-usage)
  - [TCL Driver (recommended)](#tcl-driver-recommended)
  - [Direct Python](#direct-python)
  - [Standalone STA on any netlist](#standalone-sta-on-any-netlist)
- [Algorithm Deep-Dive](#algorithm-deep-dive)
  - [Quine-McCluskey Minimization](#quine-mccluskey-minimization)
  - [Technology Mapping](#technology-mapping)
  - [Liberty Parsing](#liberty-parsing)
  - [Graph-Based STA](#graph-based-sta)
- [Outputs](#outputs)
- [Extending the Pipeline](#extending-the-pipeline)
- [Sample Results](#sample-results)

---

## Features

- **Logic minimization** via Quine-McCluskey: essential prime implicant extraction, greedy minimum cover selection, full don't-care support.
- **Technology mapping** to a JSON-format standard cell library: AND/OR/INV balanced gate trees, invertible literal handling, critical path delay estimation during mapping.
- **Liberty `.lib` parser**: brace-counting block extractor that correctly handles nested timing groups, `cell_rise` / `cell_fall` lookup, fallback defaults for unlisted cells.
- **Gate-level Verilog emitter**: produces a structural `.v` netlist from synthesis output, ready to feed directly into the STA engine or any external tool.
- **Timing graph construction**: Kahn's algorithm topological sort, per-arc delay from Liberty, primary input / primary output classification.
- **Full STA**: forward arrival-time propagation, backward required-time propagation, WNS / TNS computation, critical path backtracing.
- **TCL driver** (`run_flow.tcl`): set variables, invoke steps, handle errors — exactly like a real `dc_shell` or `pt_shell` run script.
- **Three visual outputs**:
  - Critical path DAG (matplotlib) with per-node arrival time and slack annotation
  - Synthesis coverage chart: gate-count bar + area-contribution pie
  - Self-contained HTML signoff report with embedded plots, netlist table, and endpoint slack table

---

## Repository Structure

```
01_rtl_to_timing/
│
├── run_flow.tcl            # TCL driver — the main entry point
├── flow.py                 # Python orchestrator (syn | sta | full modes)
│
├── src/
│   ├── synthesis/
│   │   ├── parser.py           # Boolean function spec parser
│   │   ├── quine_mccluskey.py  # QM minimization algorithm
│   │   ├── tech_mapper.py      # Standard cell technology mapper
│   │   └── reporter.py         # Synthesis text report generator
│   │
│   ├── sta/
│   │   ├── liberty_parser.py   # Liberty .lib file parser
│   │   ├── netlist_parser.py   # Structural Verilog parser
│   │   ├── timing_graph.py     # DAG builder (TimingNode / TimingEdge)
│   │   ├── sta.py              # Forward/backward STA, WNS/TNS, critical path
│   │   └── reporter.py         # PrimeTime-style timing report generator
│   │
│   └── visualize/
│       ├── timing_path_plot.py # Critical path DAG plot (matplotlib)
│       ├── syn_chart.py        # Gate count bar + area pie chart
│       └── html_report.py      # Self-contained HTML signoff report
│
├── lib/
│   ├── cells.json          # Cell library — used by synthesis (JSON)
│   └── cells.lib           # Cell library — used by STA (Liberty format)
│
├── examples/
│   ├── full_adder_sum.txt  # Boolean spec: SUM output of a full adder
│   ├── full_adder_carry.txt# Boolean spec: CARRY output of a full adder
│   └── ripple_adder.v      # Pre-written gate-level netlist for STA
│
└── reports/                # Generated on run (gitignored)
    ├── *_mapped.v          # Synthesized gate-level Verilog
    ├── *_syn.rpt           # Synthesis text report
    ├── *_sta.rpt           # STA timing report
    ├── *_critical_path.png # Critical path DAG plot
    ├── *_syn_chart.png     # Synthesis coverage chart
    └── *_report.html       # Combined HTML signoff report
```

---

## Requirements

- Python 3.8+
- matplotlib (for plots — `pip install matplotlib`)
- `tclsh` for the TCL driver (pre-installed on macOS and most Linux distributions; install `tcl` package on Windows via `winget install tclsh` or ActiveTcl)

No other dependencies. The STA engine, Liberty parser, and Verilog parser are all pure Python.

---

## Quick Start

```bash
git clone <repo>
cd 01_rtl_to_timing
pip install matplotlib

# Run the full pipeline on the full-adder SUM function at 200ps clock
tclsh run_flow.tcl

# Or directly via Python
python flow.py --mode full --design examples/full_adder_sum.txt --period 200
```

Open `reports/full_adder_sum_report.html` in any browser to see the signoff report.

---

## Detailed Usage

### TCL Driver (recommended)

`run_flow.tcl` is designed to feel like a real `dc_shell` run script. Edit the variable block at the top, then source it with `tclsh`:

```tcl
# run_flow.tcl — change these to target a different design
set MODE      "full"                           ;# syn | sta | full
set DESIGN    "examples/full_adder_sum.txt"
set LIB_JSON  "lib/cells.json"
set LIB       "lib/cells.lib"
set PERIOD    200                              ;# clock period in ps
set OUT_DIR   "reports"
```

```bash
# Full flow, default settings
tclsh run_flow.tcl

# Override mode and design via argv
tclsh run_flow.tcl full examples/full_adder_carry.txt 150

# STA only on a pre-existing netlist
tclsh run_flow.tcl sta reports/full_adder_sum_mapped.v 200
```

The script validates the mode, prints a configuration summary, invokes `flow.py`, streams its output, and exits non-zero on any failure — exactly the error-handling pattern used in real signoff automation.

### Direct Python

```bash
# Synthesis + STA + all plots
python flow.py --mode full \
    --design   examples/full_adder_sum.txt \
    --lib-json lib/cells.json \
    --lib      lib/cells.lib \
    --period   200 \
    --out-dir  reports

# Synthesis only (generates mapped .v + synthesis chart)
python flow.py --mode syn \
    --design   examples/full_adder_carry.txt \
    --lib-json lib/cells.json \
    --period   150

# STA only (on any structural Verilog netlist)
python flow.py --mode sta \
    --netlist  examples/ripple_adder.v \
    --lib      lib/cells.lib \
    --period   200
```

### Standalone STA on any netlist

The STA engine reads any structural Verilog netlist where gate instantiations follow the convention `CELL_TYPE instance_name (output, input1, input2, ...);`. Annotate timing constraints as comments:

```verilog
// CLOCK: CLK period=200
// INPUT_DELAY: A=10 B=10 Cin=10
module my_design (out, A, B, Cin);
  ...
  AND2 U1 (w1, A, B);
  OR2  U2 (out, w1, Cin);
endmodule
```

```bash
python flow.py --mode sta --netlist my_design.v --lib lib/cells.lib --period 200
```

### Adding a new design

Create a `.txt` file in `examples/`:

```
# 4-variable function with don't-cares
VARS:       A B C D
MINTERMS:   0 1 3 5 7 8 10 14 15
DONT_CARES: 2 6
OUTPUT:     F
```

Then run:

```bash
tclsh run_flow.tcl full examples/my_design.txt 300
```

---

## Algorithm Deep-Dive

### Quine-McCluskey Minimization

The minimizer in `src/synthesis/quine_mccluskey.py` implements the full two-phase Quine-McCluskey algorithm.

**Phase 1 — Prime implicant generation.** Every minterm and don't-care starts as a 1-literal implicant. In each round, pairs of implicants with equal masks (same merged bits) and values differing by exactly one bit are combined into a new implicant with that bit added to the mask (marked as a don't-care). Implicants that cannot be combined in a round are prime implicants. The process repeats until no new combinations are possible.

**Phase 2 — Minimum cover selection.** A coverage map is built: for each minterm, the list of prime implicants that cover it. Minterms covered by exactly one prime implicant yield essential PIs, which are added to the cover unconditionally. Remaining minterms are covered greedily: repeatedly pick the prime implicant that covers the most uncovered minterms.

This is equivalent to the essential prime implicant extraction step inside Synopsys Design Compiler's `compile_ultra`. DC adds multi-level optimization on top; the QM cover is the seed.

### Technology Mapping

`src/synthesis/tech_mapper.py` maps the SOP expression to a netlist of 2-input gates from `lib/cells.json`.

Each product term in the SOP is realized as an AND tree: the variables in the term are collected as literals (complemented variables first pass through INV gates), then paired into a balanced AND2 tree. The sum of all product terms is realized as a balanced OR2 tree. Single-literal terms pass through directly; single-product-term functions get a buffer (AND2 with both inputs tied together, a common structural trick when no BUF cell is in the library).

The resulting netlist is emitted as a structural Verilog module. The gate ordering in the `.v` is topological, so the STA engine can parse it without further sorting.

### Liberty Parsing

`src/sta/liberty_parser.py` uses a brace-counting block extractor rather than a grammar-based parser. This is deliberate: real Liberty files contain nested `timing()`, `table_template()`, and `lut_values()` blocks that are deeply nested and would require a full grammar to handle correctly with regex. The brace counter correctly tracks nesting depth and extracts `cell`, `pin`, and `timing` blocks at any depth.

For each `timing()` block, the parser reads `related_pin`, `cell_rise`, and `cell_fall`. The maximum of rise and fall is stored as the arc delay. When a specific arc (output pin ← related pin) is not found, the parser falls back to the largest delay found anywhere in that cell's pins, and then to a hard-coded per-cell-type table if the cell has no parsed timing data at all.

### Graph-Based STA

`src/sta/sta.py` implements the two-pass algorithm that PrimeTime's core uses.

**Forward pass (arrival times).** Nodes are visited in topological order (Kahn's algorithm on the timing graph). For each node, the arrival time is the maximum over all fanin arcs of `AT(driver) + arc_delay`. Primary inputs are seeded with their input delay values (defaulting to 0).

**Backward pass (required times).** Primary output nodes are given a required time equal to `clock_period − output_delay`. Nodes are visited in reverse topological order. For each node, the required time is the minimum over all fanout arcs of `RT(load) − arc_delay`.

**Slack** at each node is `RT − AT`. Nodes with negative slack are timing violations. WNS is the most-negative slack across all nodes with finite required times. TNS is the sum of all negative slacks.

**Critical path backtracing** starts at the endpoint with the maximum arrival time and follows, at each step, the fanin arc whose driver has the highest arrival time. This traces the longest path through the circuit, which is by definition the critical path.

---

## Outputs

Running `python flow.py --mode full` on `full_adder_sum.txt` at 200ps produces:

**Synthesis report (`*_syn.rpt`)**

```
SUM = ~A.~B.Cin + ~A.B.~Cin + A.~B.~Cin + A.B.Cin
Product terms  : 4
Total literals : 12
Gate count     : 17
Total area     : 28.00 arb. units
Critical path  : 121.0 ps
Slack          : +79.0 ps  ✓ TIMING MET
```

**STA report (`*_sta.rpt`)**

```
WNS : +79.0 ps
TNS :  +0.0 ps
Violating endpoints: 0 / 20

Critical path:
  A → inv1 → AND_t03 → AND_t04 → OR_final15 → SUM
  0ps → 15ps → 40ps → 65ps → 93ps → 121ps
```

**Critical path plot** — A left-to-right node diagram with arrival times and per-node slack overlaid. Nodes are colour-coded green (timing met) or red (violated). Arrows trace the path.

**Synthesis chart** — A two-panel figure: gate count by cell type (bar) and area contribution by cell type (pie). Useful for identifying which cell types dominate area and for checking the mapper's gate selection.

**HTML signoff report** — A single portable `.html` file with both plots embedded as base64, a configuration summary table, the full technology-mapped netlist table, the critical path trace table, and the complete endpoint slack table. Open in any browser, no server required.

---

## Extending the Pipeline

**Adding cells to the library.** Edit `lib/cells.json` (synthesis) and `lib/cells.lib` (STA). The JSON format is straightforward; the Liberty format follows the subset the parser already handles. Both files use the same cell names so delays are consistent.

**Adding a multi-output design.** Run the pipeline once per output function and feed the combined netlist into the STA engine. The Verilog parser handles multi-output modules natively; the STA engine will analyze all paths to all outputs simultaneously.

**Tighter clock constraints.** Change `PERIOD` in `run_flow.tcl` or pass `--period` to `flow.py`. The STA engine will report WNS/TNS for the new constraint. When WNS goes negative, the HTML report's status banner turns red and the violated endpoints are flagged in the slack table.

**Replacing the cell library with characterization data.** If you have Virtuoso + Spectre access, characterize your own cells (vary load capacitance, extract `tpHL`/`tpLH`), write a Python script to emit `cell_rise`/`cell_fall` in Liberty syntax, and drop the result into `lib/cells.lib`. The parser will pick up your measured delays automatically.

---

## Sample Results

| Design | Gates | Area | Crit. path | Period | WNS | Status |
|---|---|---|---|---|---|---|
| `full_adder_sum` | 17 | 28.0 | 121 ps | 200 ps | +79.0 ps | ✓ MET |
| `full_adder_carry` | 9 | 17.0 | 75 ps | 150 ps | +75.0 ps | ✓ MET |
| `ripple_adder.v` (STA) | 11 | — | 218 ps | 200 ps | −18.0 ps | ✗ VIOLATED |

---

## Acknowledgements

The algorithms implemented here are described in *Logic Synthesis and Verification* (Hassoun & Sasao, 2002) and *Static Timing Analysis for Nanometer Designs* (Bhasker & Chadha, 2009). The Liberty format is documented in the Synopsys Liberty User Guide. This project is independent coursework and has no affiliation with Synopsys, Inc.
