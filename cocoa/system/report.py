"""SYSTEM_REPORT.md renderer: honest, complete, includes every skip."""
from __future__ import annotations

from cocoa.system.blast import GraphIndex
from cocoa.system.models import EdgeKind, NodeKind, SystemGraph
from cocoa.system.topology import service_rpc_edges


def _service_topology(graph: SystemGraph) -> list[str]:
    """'client → host' lines derived from the shared service-level RPC rollup."""
    lines = {f"- {t.client} → {t.server}  (`{t.rpc}`, {t.provenance.value})"
              for t in service_rpc_edges(graph)}
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
        name = s.id.removeprefix("svc:")
        fns = sum(1 for n in graph.nodes
                  if n.kind == NodeKind.FUNCTION and n.service == name)
        out.append(f"- **{name}** ({s.attrs.get('language', '?')}) — {fns} functions")
    out += ["", "## Cross-service topology", ""]
    out += _service_topology(graph) or ["- (no RPC edges derived)"]
    out += ["", "## Data access", ""]
    for e in sorted(data_edges, key=lambda e: (e.target, e.source))[:200]:
        svc = idx.nodes[e.source].service if e.source in idx.nodes else "?"
        out.append(f"- {svc}: `{e.source}` {e.kind.value} `{e.target}`")
    if len(data_edges) > 200:
        out.append(f"- … (showing first 200 of {len(data_edges)} data-access edges)")
    if not data_edges:
        out.append("- (none derived)")
    out += ["", "## Dead-RPC candidates (DECLARED-UNUSED)", ""]
    out += [f"- `{u}`" for u in unused] or ["- None detected"]
    out += ["", "## Skipped services", ""]
    out += [f"- **{s.service}** ({s.language}): {s.reason}" for s in graph.skipped] \
        or ["- none — all detected services analyzed"]
    return "\n".join(out) + "\n"
