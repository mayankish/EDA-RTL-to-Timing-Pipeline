"""
Gate-Level Netlist Parser
==========================
Parses a simple structural Verilog gate-level netlist.

Supported syntax:
  module <name> (<ports>);
    input  <wire>, ...;
    output <wire>, ...;
    wire   <wire>, ...;
    <CELL_TYPE> <instance_name> (<out>, <in1>, <in2>, ...);
  endmodule

Clock and input arrival time annotations (comments) are also supported:
  // CLOCK: CLK period=200
  // INPUT_DELAY: A=10 B=10 Cin=10
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


@dataclass
class GateInst:
    """One gate instantiation in the netlist."""
    cell_type     : str
    instance_name : str
    output_pin    : str          # first port = output (structural Verilog convention)
    input_pins    : List[str]    # remaining ports = inputs


@dataclass
class ParsedNetlist:
    module_name   : str
    primary_inputs  : List[str]
    primary_outputs : List[str]
    wires           : List[str]
    gates           : List[GateInst]
    clock_net       : Optional[str]      = None
    clock_period_ps : float              = 0.0
    input_delays    : Dict[str, float]   = field(default_factory=dict)


def parse_verilog(filepath: str) -> ParsedNetlist:
    """Parse a gate-level Verilog file and return a ParsedNetlist."""
    with open(filepath) as f:
        lines = f.readlines()

    module_name  = "unknown"
    inputs       : List[str] = []
    outputs      : List[str] = []
    wires        : List[str] = []
    gates        : List[GateInst] = []
    clock_net    : Optional[str] = None
    clock_period : float = 0.0
    input_delays : Dict[str, float] = {}

    full_text = "".join(lines)

    # ── Strip // comments but capture annotations first ──────────────────
    for line in lines:
        m = re.search(r"//\s*CLOCK:\s*(\w+)\s+period=([0-9.]+)", line)
        if m:
            clock_net    = m.group(1)
            clock_period = float(m.group(2))
        m = re.search(r"//\s*INPUT_DELAY:(.*)", line)
        if m:
            for pair in re.findall(r"(\w+)=([0-9.]+)", m.group(1)):
                input_delays[pair[0]] = float(pair[1])

    # Remove comments for parsing
    clean = re.sub(r"//[^\n]*", "", full_text)
    clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.DOTALL)

    # ── Module name ──────────────────────────────────────────────────────
    m = re.search(r"module\s+(\w+)", clean)
    if m:
        module_name = m.group(1)

    # ── Port declarations ────────────────────────────────────────────────
    for m in re.finditer(r"input\s+(.*?);", clean, re.DOTALL):
        inputs += _split_ports(m.group(1))
    for m in re.finditer(r"output\s+(.*?);", clean, re.DOTALL):
        outputs += _split_ports(m.group(1))
    for m in re.finditer(r"wire\s+(.*?);", clean, re.DOTALL):
        wires += _split_ports(m.group(1))

    # ── Gate instantiations ───────────────────────────────────────────────
    # Pattern: CELL_TYPE instance_name (port, port, ...);
    known_keywords = {"module", "endmodule", "input", "output", "wire",
                      "assign", "always", "if", "else", "begin", "end"}
    gate_pattern = re.compile(
        r"(\w+)\s+(\w+)\s*\(([^)]*)\)\s*;", re.DOTALL
    )
    for m in gate_pattern.finditer(clean):
        cell_type = m.group(1)
        inst_name = m.group(2)
        port_str  = m.group(3)
        if cell_type.lower() in known_keywords:
            continue
        ports = [p.strip() for p in port_str.split(",") if p.strip()]
        if len(ports) < 2:
            continue
        gate = GateInst(
            cell_type=cell_type,
            instance_name=inst_name,
            output_pin=ports[0],
            input_pins=ports[1:]
        )
        gates.append(gate)

    return ParsedNetlist(
        module_name=module_name,
        primary_inputs=inputs,
        primary_outputs=outputs,
        wires=wires,
        gates=gates,
        clock_net=clock_net,
        clock_period_ps=clock_period,
        input_delays=input_delays
    )


def _split_ports(s: str) -> List[str]:
    """Split comma/newline separated port names."""
    return [p.strip() for p in re.split(r"[\s,]+", s.strip()) if p.strip()]
