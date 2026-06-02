"""
Static Timing Analyzer
========================
Performs graph-based STA on the timing graph.

Algorithm (mirrors PrimeTime's core):
  1. Forward pass  — compute Arrival Time  (AT) at every node
  2. Backward pass — compute Required Time (RT) from clock period constraint
  3. Slack = RT - AT  (negative = timing violation)
  4. Report WNS (Worst Negative Slack), TNS (Total Negative Slack),
     and the critical path.
"""

from typing import Dict, List, Optional, Tuple
from timing_graph import TimingGraph, TimingNode


# ---------------------------------------------------------------------------
# Forward pass — Arrival Time propagation
# ---------------------------------------------------------------------------

def compute_arrival_times(graph: TimingGraph,
                          input_delays: Dict[str, float]) -> None:
    """
    Forward traversal in topological order.
    AT(node) = max over all fanin edges of:  AT(src) + edge_delay
    """
    # Initialize primary inputs
    for name, node in graph.nodes.items():
        if node.is_pi:
            node.arrival_time = input_delays.get(name, 0.0)
        else:
            node.arrival_time = 0.0

    for node_name in graph.topological_order():
        node = graph.nodes[node_name]
        fanin_edges = graph.fanin(node_name)

        if not fanin_edges:
            continue  # PI — already initialized

        # Arrival = latest input arrival + gate delay
        max_at = max(
            graph.nodes[e.src_node].arrival_time + e.delay
            for e in fanin_edges
            if e.src_node in graph.nodes
        )
        node.arrival_time = max_at


# ---------------------------------------------------------------------------
# Backward pass — Required Time propagation
# ---------------------------------------------------------------------------

def compute_required_times(graph: TimingGraph,
                           clock_period_ps: float,
                           output_delay: float = 0.0) -> None:
    """
    Backward traversal in reverse topological order.
    RT(node) = min over all fanout edges of:  RT(dst) - edge_delay

    Primary outputs must meet: AT(PO) ≤ clock_period - output_delay
    """
    # Initialize primary outputs
    deadline = clock_period_ps - output_delay
    for name, node in graph.nodes.items():
        if node.is_po:
            node.required_time = deadline
        else:
            node.required_time = float("inf")

    topo = graph.topological_order()
    for node_name in reversed(topo):
        node = graph.nodes[node_name]
        fanout_edges = graph.fanout(node_name)

        if not fanout_edges:
            continue  # PO — already set

        # Required = tightest (min) required time at outputs minus delay
        min_rt = min(
            graph.nodes[e.dst_node].required_time - e.delay
            for e in fanout_edges
            if e.dst_node in graph.nodes
        )
        node.required_time = min(node.required_time, min_rt)


# ---------------------------------------------------------------------------
# Slack & path analysis
# ---------------------------------------------------------------------------

def compute_wns(graph: TimingGraph) -> float:
    """Worst Negative Slack — most violated timing endpoint."""
    slacks = [node.slack for node in graph.nodes.values()
              if node.required_time < float("inf")]
    return min(slacks) if slacks else 0.0


def compute_tns(graph: TimingGraph) -> float:
    """Total Negative Slack — sum of all negative slacks."""
    return sum(node.slack for node in graph.nodes.values()
               if node.slack < 0 and node.required_time < float("inf"))


def find_critical_path(graph: TimingGraph) -> List[str]:
    """
    Trace the critical path (highest arrival time chain).
    Starts at the endpoint with maximum arrival time and backtracks
    through fanin edges.
    """
    # Find endpoint: non-PI node with maximum arrival time
    candidates = [(name, node.arrival_time)
                  for name, node in graph.nodes.items()
                  if not node.is_pi and graph.fanin(name)]
    if not candidates:
        return []

    endpoint, _ = max(candidates, key=lambda x: x[1])
    path = [endpoint]

    # Backtrack: always follow the fanin edge with highest arrival time
    current = endpoint
    visited = set()
    while True:
        if current in visited:
            break
        visited.add(current)
        fanin_edges = graph.fanin(current)
        if not fanin_edges:
            break
        # Pick the fanin with the latest arrival time
        best_edge = max(fanin_edges,
                        key=lambda e: graph.nodes[e.src_node].arrival_time
                        if e.src_node in graph.nodes else 0.0)
        src = best_edge.src_node
        if src not in graph.nodes:
            break
        path.append(src)
        if graph.nodes[src].is_pi:
            break
        current = src

    return list(reversed(path))


# ---------------------------------------------------------------------------
# Main analysis entry point
# ---------------------------------------------------------------------------

def run_sta(graph: TimingGraph,
            clock_period_ps: float,
            input_delays: Dict[str, float] = None,
            output_delay: float = 0.0) -> dict:
    """
    Run full STA: forward pass → backward pass → compute metrics.

    Returns dict with keys:
      wns, tns, critical_path, node_slacks
    """
    if input_delays is None:
        input_delays = {}

    compute_arrival_times(graph, input_delays)
    compute_required_times(graph, clock_period_ps, output_delay)

    wns           = compute_wns(graph)
    tns           = compute_tns(graph)
    critical_path = find_critical_path(graph)

    node_slacks = {
        name: node.slack
        for name, node in graph.nodes.items()
        if node.required_time < float("inf")
    }

    return {
        "wns"           : wns,
        "tns"           : tns,
        "critical_path" : critical_path,
        "node_slacks"   : node_slacks
    }
