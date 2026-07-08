"""SYSTEM_REPORT.md renderer: honest, complete, includes every skip."""
from __future__ import annotations

from cocoa.system.blast import GraphIndex
from cocoa.system.models import EdgeKind, NodeKind, SystemGraph


def _service_topology(graph: SystemGraph, idx: GraphIndex) -> list[str]:
    """'client → host' lines derived from RPC_CALLS + HANDLES edges."""
    hosts = {e.target: e.source.removeprefix("svc:")
             for e in graph.edges if e.kind == EdgeKind.HOSTS}
    lines = set()
    for e in graph.edges:
        if e.kind != EdgeKind.RPC_CALLS:
            continue
        client = idx.nodes[e.source].service if e.source in idx.nodes else None
        # Try HOSTS edges first, then fall back to HANDLES edges
        host = hosts.get(e.target)
        if not host:
            # Look for HANDLES edge to find the handler, and get its service
            for handle_e in graph.edges:
                if handle_e.kind == EdgeKind.HANDLES and handle_e.source == e.target:
                    handler_node = idx.nodes.get(handle_e.target)
                    if handler_node:
                        host = handler_node.service
                    break
        if client and host and client != host:
            lines.add(f"- {client} → {host}  (`{e.target}`, {e.provenance.value})")
    return sorted(lines)


def render_report(graph: SystemGraph) -> str:
    idx = GraphIndex(graph)
    services = [n for n in graph.nodes if n.kind == NodeKind.SERVICE]
    rpcs = [n for n in graph.nodes if n.kind == NodeKind.RPC_ENDPOINT]
    unused = [n.id for n in rpcs if n.attrs.get("annotation") == "DECLARED-UNUSED"]
    data_edges = [e for e in graph.edges if e.kind in (EdgeKind.READS, EdgeKind.WRITES)]

    out = ["# System Report", "", f"Root: `{graph.root}`", ""]
    out += ["## Services", ""]
    for s in services:
        fns = sum(1 for n in graph.nodes
                  if n.kind == NodeKind.FUNCTION and n.service == s.service)
        out.append(f"- **{s.service}** ({s.attrs.get('language', '?')}) — {fns} functions")
    out += ["", "## Cross-service topology", ""]
    out += _service_topology(graph, idx) or ["- (no RPC edges derived)"]
    out += ["", "## Data access", ""]
    for e in sorted(data_edges, key=lambda e: (e.target, e.source))[:200]:
        svc = idx.nodes[e.source].service if e.source in idx.nodes else "?"
        out.append(f"- {svc}: `{e.source}` {e.kind.value} `{e.target}`")
    if not data_edges:
        out.append("- (none derived)")
    out += ["", "## Dead-RPC candidates (DECLARED-UNUSED)", ""]
    out += [f"- `{u}`" for u in unused] or ["- None detected"]
    out += ["", "## Skipped services", ""]
    out += [f"- **{s.service}** ({s.language}): {s.reason}" for s in graph.skipped] \
        or ["- none — all detected services analyzed"]
    return "\n".join(out) + "\n"
