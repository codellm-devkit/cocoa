"""System-graph MCP tools. Each returns compact JSON sized for agent context."""
from __future__ import annotations

import json

from fastmcp import Context

from cocoa.system.blast import blast_radius
from cocoa.system.models import EdgeKind, NodeKind, Provenance


def _state(ctx: Context):
    return ctx.request_context.lifespan_context


async def build_graph_tool(ctx: Context, rebuild: bool = False) -> str:
    """Build (or load) the system graph; returns a summary with artifact paths."""
    state = _state(ctx)
    graph = state.graph(rebuild=rebuild)
    return json.dumps({
        "root": graph.root,
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "services": sorted({n.service for n in graph.nodes if n.service}),
        "skipped": [s.model_dump() for s in graph.skipped],
        "artifacts": {k: str(p) for k, p in state.artifact_paths().items()},
        "truncated": False,
    })


async def blast_radius_tool(
    ctx: Context, target: str, kind: str, depth: int = 25, limit: int = 200,
) -> str:
    """Blast radius for a target. kind: proto-field|rpc|function|table|redis-key.

    An invalid kind raises and surfaces to the caller as an MCP isError result.
    """
    result = blast_radius(_state(ctx).graph(), target, kind, max_depth=depth)
    payload = result.model_dump(mode="json")
    truncated = len(result.seeds) > limit or len(result.impacted) > limit
    payload["seeds"] = payload["seeds"][:limit]
    payload["impacted"] = payload["impacted"][:limit]
    payload["total_impacted"] = len(result.impacted)
    payload["truncated"] = truncated  # by_service stays complete: it's small
    return json.dumps(payload)


async def service_graph_tool(
    ctx: Context, service: str | None = None, limit: int = 200,
) -> str:
    """Cross-service RPC topology rolled up to service level (data edges: data_access_tool)."""
    graph = _state(ctx).graph()
    hosts = {e.target: e.source.removeprefix("svc:")
             for e in graph.edges if e.kind == EdgeKind.HOSTS}
    fn_svc = {n.id: n.service for n in graph.nodes if n.kind == NodeKind.FUNCTION}
    handler_svc: dict[str, tuple[str | None, Provenance]] = {}
    for e in graph.edges:
        if e.kind == EdgeKind.HANDLES:
            handler_svc[e.source] = (fn_svc.get(e.target), e.provenance)
    rollup = []
    for e in graph.edges:
        if e.kind != EdgeKind.RPC_CALLS:
            continue
        c, prov = fn_svc.get(e.source), e.provenance
        h = hosts.get(e.target)
        if not h:  # HANDLES fallback, as in report.py/htmlmap.py
            h, h_prov = handler_svc.get(e.target, (None, None))
            if h and Provenance.INFERRED in (prov, h_prov):
                prov = Provenance.INFERRED  # compound across the fallback hop
        if c and h and (service is None or service in (c, h)):
            rollup.append({"client": c, "server": h, "rpc": e.target,
                           "provenance": prov.value})
    return json.dumps({"service": service, "rpc_edges": rollup[:limit],
                       "total_edges": len(rollup), "truncated": len(rollup) > limit})


async def data_access_tool(
    ctx: Context, service: str | None = None, limit: int = 200,
) -> str:
    """Who reads/writes which datastore/table/key."""
    graph = _state(ctx).graph()
    fn_svc = {n.id: n.service for n in graph.nodes if n.kind == NodeKind.FUNCTION}
    rows = [
        {"service": fn_svc.get(e.source), "function": e.source, "op": e.kind.value,
         "target": e.target, "provenance": e.provenance.value}
        for e in graph.edges
        if e.kind in (EdgeKind.READS, EdgeKind.WRITES)
        and (service is None or fn_svc.get(e.source) == service)
    ]
    return json.dumps({"service": service, "access": rows[:limit],
                       "total_access": len(rows), "truncated": len(rows) > limit})


async def query_subgraph_tool(
    ctx: Context, node_kind: str | None = None, edge_kind: str | None = None,
    id_contains: str | None = None, limit: int = 200,
) -> str:
    """Filtered subgraph: nodes by kind/substring, edges by kind."""
    graph = _state(ctx).graph()
    nodes = [
        n.model_dump() for n in graph.nodes
        if (node_kind is None or n.kind.value == node_kind)
        and (id_contains is None or id_contains in n.id)
    ]
    edges = [
        e.model_dump() for e in graph.edges
        if (edge_kind is None or e.kind.value == edge_kind)
        and (id_contains is None or id_contains in e.source or id_contains in e.target)
    ]
    return json.dumps({"nodes": nodes[:limit], "edges": edges[:limit],
                       "total_nodes": len(nodes), "total_edges": len(edges),
                       "truncated": len(nodes) > limit or len(edges) > limit})
