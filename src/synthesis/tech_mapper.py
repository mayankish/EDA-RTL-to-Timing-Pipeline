"""
Technology Mapper
=================
Maps a minimized SOP expression to gates from a standard cell library.
Computes estimated area and critical path delay.

This mirrors Synopsys Design Compiler's technology mapping step.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class Cell:
    name:       str
    function:   str
    num_inputs: int
    area:       float
    delay:      float   # ps


@dataclass
class GateInstance:
    instance_name: str
    cell:          Cell
    inputs:        List[str]
    output:        str


@dataclass
class MappedNetlist:
    gates:           List[GateInstance] = field(default_factory=list)
    primary_inputs:  List[str]          = field(default_factory=list)
    primary_output:  str                = "Z"

    @property
    def total_area(self) -> float:
        return sum(g.cell.area for g in self.gates)

    @property
    def critical_path_delay(self) -> float:
        return _compute_critical_path(self)

    @property
    def gate_type_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for g in self.gates:
            counts[g.cell.name] = counts.get(g.cell.name, 0) + 1
        return counts

    @property
    def gate_area_by_type(self) -> Dict[str, float]:
        areas: Dict[str, float] = {}
        for g in self.gates:
            areas[g.cell.name] = areas.get(g.cell.name, 0.0) + g.cell.area
        return areas

    def to_verilog(self, module_name: str = "mapped") -> str:
        """Emit a structural Verilog gate-level netlist (suitable for STA input)."""
        lines = [
            f"// Technology-mapped netlist — module: {module_name}",
            f"// CLOCK: CLK period=200",
            f"module {module_name} ({', '.join(self.primary_inputs + [self.primary_output])});",
        ]
        for pi in self.primary_inputs:
            lines.append(f"  input  {pi};")
        lines.append(f"  output {self.primary_output};")

        wires = set()
        for g in self.gates:
            wires.update(g.inputs)
            wires.add(g.output)
        internal = wires - set(self.primary_inputs) - {self.primary_output}
        if internal:
            lines.append(f"  wire   {', '.join(sorted(internal))};")

        for g in self.gates:
            ports = ", ".join([g.output] + g.inputs)
            lines.append(f"  {g.cell.name} {g.instance_name} ({ports});")

        lines.append("endmodule")
        return "\n".join(lines)


# ── Library loading ──────────────────────────────────────────────────────────

def load_library(lib_path: str) -> Dict[str, Cell]:
    """Load standard cell library from JSON file."""
    with open(lib_path) as f:
        data = json.load(f)
    cells = {}
    for entry in data["cells"]:
        c = Cell(
            name       = entry["name"],
            function   = entry["function"],
            num_inputs = entry["num_inputs"],
            area       = entry["area"],
            delay      = entry["delay_ps"],
        )
        cells[c.function] = c
    return cells


# ── Mapping logic ────────────────────────────────────────────────────────────

def map_sop_to_gates(sop_terms: list, var_names: list,
                     num_vars: int, library: Dict[str, Cell],
                     output_name: str = "Z") -> MappedNetlist:
    """Map a SOP expression to standard cells. Returns MappedNetlist."""
    netlist = MappedNetlist(primary_inputs=list(var_names),
                            primary_output=output_name)
    wire_counter = [0]

    def new_wire(prefix="w"):
        wire_counter[0] += 1
        return f"{prefix}{wire_counter[0]}"

    inv_cell  = _get_cell(library, "INV")
    and2_cell = _get_cell(library, "AND2")
    or2_cell  = _get_cell(library, "OR2")

    product_wires = []
    for idx, impl in enumerate(sop_terms):
        literals = _get_literals(impl, num_vars, var_names, netlist, library, new_wire)
        if len(literals) == 1:
            product_wires.append(literals[0])
        else:
            and_out = _build_tree(literals, and2_cell, netlist, new_wire, f"AND_t{idx}")
            product_wires.append(and_out)

    if len(product_wires) == 0:
        pass
    elif len(product_wires) == 1:
        _add_buffer_or_rename(netlist, product_wires[0], output_name, and2_cell, new_wire)
    else:
        _build_tree(product_wires, or2_cell, netlist, new_wire, "OR_final",
                    final_output=output_name)

    return netlist


def _get_literals(impl, num_vars, var_names, netlist, library, new_wire):
    inv_cell = _get_cell(library, "INV")
    literals = []
    for i in range(num_vars - 1, -1, -1):
        bit  = 1 << i
        name = var_names[num_vars - 1 - i]
        if impl.mask & bit:
            continue
        elif impl.value & bit:
            literals.append(name)
        else:
            inv_out = new_wire("inv")
            netlist.gates.append(GateInstance(
                instance_name=f"INV_{name}_{inv_out}",
                cell=inv_cell,
                inputs=[name],
                output=inv_out,
            ))
            literals.append(inv_out)
    return literals


def _build_tree(signals, cell, netlist, new_wire, prefix, final_output=None):
    if len(signals) == 1:
        return signals[0]
    level = list(signals)
    gate_idx = [0]
    while len(level) > 1:
        next_level = []
        for i in range(0, len(level) - 1, 2):
            gate_idx[0] += 1
            is_last = (len(level) <= 2) and (i == 0)
            out = final_output if (is_last and final_output) else new_wire(prefix)
            netlist.gates.append(GateInstance(
                instance_name=f"{prefix}_g{gate_idx[0]}",
                cell=cell,
                inputs=[level[i], level[i + 1]],
                output=out,
            ))
            next_level.append(out)
        if len(level) % 2 == 1:
            next_level.append(level[-1])
        level = next_level
    return level[0]


def _add_buffer_or_rename(netlist, src, dst, buf_cell, new_wire):
    netlist.gates.append(GateInstance(
        instance_name="BUF_out",
        cell=buf_cell,
        inputs=[src, src],
        output=dst,
    ))


def _get_cell(library: dict, func: str) -> Cell:
    if func not in library:
        raise KeyError(f"Cell '{func}' not in library. Available: {list(library.keys())}")
    return library[func]


def _compute_critical_path(netlist: MappedNetlist) -> float:
    arrival = {pi: 0.0 for pi in netlist.primary_inputs}
    changed = True
    iterations = 0
    while changed and iterations < 100:
        changed = False
        for gate in netlist.gates:
            if all(w in arrival for w in gate.inputs):
                new_at = max(arrival[w] for w in gate.inputs) + gate.cell.delay
                if gate.output not in arrival or arrival[gate.output] < new_at:
                    arrival[gate.output] = new_at
                    changed = True
        iterations += 1
    return arrival.get(netlist.primary_output, 0.0)
