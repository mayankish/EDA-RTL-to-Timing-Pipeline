#!/usr/bin/env tclsh
# =============================================================================
#  run_flow.tcl  —  RTL-to-Timing Pipeline Driver
#  Synopsys_Projects_v2 / 01_rtl_to_timing
# =============================================================================
#
#  Mirrors the dc_shell → pt_shell flow used in real Synopsys design flows:
#    1. Set design variables (library, clock period, design name)
#    2. Run logic synthesis (QM minimization + tech mapping)
#    3. Run static timing analysis on the mapped netlist
#    4. Generate plots + HTML signoff report
#
#  Usage:
#    tclsh run_flow.tcl                         # full flow, default example
#    tclsh run_flow.tcl full examples/full_adder_sum.txt 200
#    tclsh run_flow.tcl syn  examples/full_adder_carry.txt 150
#    tclsh run_flow.tcl sta  reports/full_adder_sum_mapped.v 200
#
#  Arguments (all optional — defaults shown below):
#    argv[0]  mode       : syn | sta | full   (default: full)
#    argv[1]  design     : path to .txt spec OR .v netlist for sta mode
#    argv[2]  period_ps  : clock period in ps  (default: 200)
#
# =============================================================================

# ── Configuration variables (edit these to run different designs) ─────────────

set MODE      "full"
set DESIGN    "examples/full_adder_sum.txt"
set LIB_JSON  "lib/cells.json"
set LIB       "lib/cells.lib"
set PERIOD    200
set OUT_DIR   "reports"

# ── Override from command-line arguments ──────────────────────────────────────

if {[llength $argv] >= 1} { set MODE   [lindex $argv 0] }
if {[llength $argv] >= 2} { set DESIGN [lindex $argv 1] }
if {[llength $argv] >= 3} { set PERIOD [lindex $argv 2] }

# ── Validate mode ─────────────────────────────────────────────────────────────

if {$MODE ni {syn sta full}} {
    puts stderr "\[ERROR\] Unknown mode '$MODE'. Valid: syn | sta | full"
    exit 1
}

# ── Print header ──────────────────────────────────────────────────────────────

puts ""
puts "╔══════════════════════════════════════════════════════════════════╗"
puts "║         RTL-to-Timing Pipeline  —  run_flow.tcl                  ║"
puts "╚══════════════════════════════════════════════════════════════════╝"
puts ""
puts "  Mode        : $MODE"
puts "  Design/Input: $DESIGN"
puts "  Liberty JSON: $LIB_JSON"
puts "  Liberty     : $LIB"
puts "  Clock period: ${PERIOD} ps"
puts "  Output dir  : $OUT_DIR"
puts ""

# ── Build the Python command ──────────────────────────────────────────────────

set python "python3"

# Detect Windows python.exe if tclsh is running on Windows
if {$tcl_platform(os) eq "Windows NT"} {
    set python "python"
}

# Build base argument list
set cmd_args [list $python flow.py \
    --mode    $MODE    \
    --lib-json $LIB_JSON \
    --lib     $LIB     \
    --period  $PERIOD  \
    --out-dir $OUT_DIR]

# sta mode uses --netlist; syn/full modes use --design
if {$MODE eq "sta"} {
    lappend cmd_args --netlist $DESIGN
} else {
    lappend cmd_args --design $DESIGN
}

puts "\[TCL\] Executing: $cmd_args"
puts ""

# ── Execute and stream output ─────────────────────────────────────────────────

if {[catch {exec {*}$cmd_args} output options]} {
    # exec raises on non-zero exit code
    set errinfo [dict get $options -errorinfo]
    # Print any stdout captured before the error
    if {[string length $output] > 0} {
        puts $output
    }
    puts stderr ""
    puts stderr "\[ERROR\] Flow failed. Details:"
    puts stderr $errinfo
    exit 1
}

puts $output

# ── Print completion banner ───────────────────────────────────────────────────

puts ""
puts "╔══════════════════════════════════════════════════════════════════╗"
puts "║  DONE — Check ${OUT_DIR}/ for reports, netlist, and plots       ║"
puts "╚══════════════════════════════════════════════════════════════════╝"
puts ""
