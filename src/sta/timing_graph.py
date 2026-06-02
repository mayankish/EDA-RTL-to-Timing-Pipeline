"""
Timing Graph Builder
=====================
Converts a parsed gate-level netlist into a Directed Acyclic Graph (DAG)
suitable for STA traversal.

Nodes = wires / ports
Edges = gate propagation arcs (from input pin → output pin, weighted by delay)

This is the exact data structure PrimeTime builds internally before
running forward/backward timing propagation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class TimingNode:
    """A node in the timing graph (a net/wire in the design)."""
    name          : str
    is_pi         : bool = False    # Primary Input
    is_po         : bool = False    # Primary Output
    is_clock      : bool = False

    # STA values (populated during analysis)
    arrival_time  : float = 0.0
    required_time : float = float("inf")

    @property
    def slack(self) -> float:
        return self.required_time - self.arrival_time


@dataclass
class TimingEdge:
    """A timing arc between two nodes (corresponds to a gate pin-to-pin delay)."""
    src_node    : str     # driving net
    dst_node    : str     # driven net (gate output)
    delay       : float   # propagation delay in ps
    cell_type   : str
    instance    : str


@dataclass
class TimingGraph:
    nodes : Dict[str, TimingNode] = field(default_factory=dict)
    edges : List[TimingEdge]      = field(default_factory=list)

    def add_node(self, name: str, **kwargs) -> TimingNode:
        if name not in self.nodes:
            self.nodes[name] = TimingNode(name=name, **kwargs)
        return self.nodes[name]

    def add_edge(self, edge: TimingEdge):
        self.edges.append(edge)

    def fanin(self, node_name: str) -> List[TimingEdge]:
        """Return all edges driving this node."""
        return [e for e in self.edges if e.dst_node == node_name]

    def fanout(self, node_name: str) -> List[TimingEdge]:
        """Return all edges leaving this node."""
        return [e for e in self.edges if e.src_node == node_name]

    def topological_order(self) -> List[str]:
        """
        Kahn's algorithm: returns nodes in topological order.
        Required for correct forward (arrival) and backward (required) traversal.
        """
        in_degree = {n: 0 for n in self.nodes}
        for e in self.edges:
            if e.dst_node in in_degree:
                in_degree[e.dst_node] += 1

        queue = [n for n, d in in_degree.items() if d == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for e in self.fanout(node):
                if e.dst_node in in_degree:
                    in_degree[e.dst_node] -= 1
                    if in_degree[e.dst_node] == 0:
                        queue.append(e.dst_node)

        return order


def build_timing_graph(netlist, lib_cells: dict) -> TimingGraph:
    """
    Build a TimingGraph from a ParsedNetlist + liberty cell library.

    Args:
        netlist   : ParsedNetlist (from netlist_parser)
        lib_cells : Dict[cell_name → LibCell] (from liberty_parser)

    Returns:
        TimingGraph ready for STA.
    """
    g = TimingGraph()

    # ── Add primary input/output nodes ───────────────────────────────────
    for pi in netlist.primary_inputs:
        g.add_node(pi, is_pi=True,
                   is_clock=(pi == netlist.clock_net))

    for po in netlist.primary_outputs:
        g.add_node(po, is_po=True)

    # ── Add nodes for all internal wires ─────────────────────────────────
    for w in netlist.wires:
        g.add_node(w)

    # ── Add timing arcs for each gate ────────────────────────────────────
    for gate in netlist.gates:
        out_net = gate.output_pin
        g.add_node(out_net)

        cell = lib_cells.get(gate.cell_type)

        for in_net in gate.input_pins:
            if in_net == netlist.clock_net:
                continue    # Don't trace through clock net combinationally
            g.add_node(in_net)

            # Look up delay from liberty
            if cell:
                delay = cell.delay_to(
                    _guess_output_pin(cell),
                    _guess_input_pin(cell, in_net, gate.input_pins)
                )
                if delay == 0.0:
                    delay = cell.max_delay()
            else:
                delay = 20.0   # Default fallback if cell not in library

            g.add_edge(TimingEdge(
                src_node=in_net,
                dst_node=out_net,
                delay=delay,
                cell_type=gate.cell_type,
                instance=gate.instance_name
            ))

    return g


def _guess_output_pin(cell) -> str:
    """Return the first output pin name."""
    for name, pin in cell.pins.items():
        if pin.direction == "output":
            return name
    return "Y"


def _guess_input_pin(cell, net_name: str, all_inputs: list) -> str:
    """Map net position to a liberty pin name (A, B, C, ...)."""
    input_pins = [name for name, pin in cell.pins.items()
                  if pin.direction == "input" and not pin.is_clock]
    idx = all_inputs.index(net_name) if net_name in all_inputs else 0
    if idx < len(input_pins):
        return input_pins[idx]
    return input_pins[0] if input_pins else "A"
