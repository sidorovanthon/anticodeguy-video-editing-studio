"""preflight_canon node — v1 passthrough stub.

Spec §4.1 places `preflight_canon` between `isolate_audio` and `skip_phase3?`.
Its real responsibility (memory-staleness checks, bare-repros for known-blocked
patterns) is deferred to v3 (spec §8). v1 ships a passthrough so the topology
matches the long-term graph — Studio shows the node, conditional edges hang off
it, and v3 can drop the real implementation in without rewiring.
"""


def preflight_canon_node(state):
    return {}
