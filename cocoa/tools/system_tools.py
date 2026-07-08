"""System-graph MCP tools. Each returns compact JSON sized for agent context."""
from __future__ import annotations

import json

from fastmcp import Context

from cocoa.system.blast import GraphIndex, blast_radius
from cocoa.system.models import EdgeKind, NodeKind


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
    })


async def blast_radius_tool(ctx: Context, target: str, kind: str, depth: int = 25) -> str:
    """Blast radius for a target. kind: proto-field|rpc|function|table|redis-key."""
    result = blast_radius(_state(ctx).graph(), target, kind, max_depth=depth)
    return result.model_dump_json()


async def service_graph_tool(ctx: Context, service: str | None = None) -> str:
    """Cross-service topology: RPC and data edges rolled up to service level."""
    graph = _state(ctx).graph()
    idx = GraphIndex(graph)
    hosts = {e.target: e.source.removeprefix("svc:")
             for e in graph.edges if e.kind == EdgeKind.HOSTS}
    fn_svc = {n.id: n.service for n in graph.nodes if n.kind == NodeKind.FUNCTION}
    rollup = []
    for e in graph.edges:
        if e.kind == EdgeKind.RPC_CALLS:
            c, h = fn_svc.get(e.source), hosts.get(e.target)
            if c and h and (service is None or service in (c, h)):
                rollup.append({"client": c, "server": h, "rpc": e.target,
                               "provenance": e.provenance.value})
    return json.dumps({"service": service, "rpc_edges": rollup})


async def data_access_tool(ctx: Context, service: str | None = None) -> str:
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
    return json.dumps({"service": service, "access": rows})


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
    ][:limit]
    edges = [
        e.model_dump() for e in graph.edges
        if (edge_kind is None or e.kind.value == edge_kind)
        and (id_contains is None or id_contains in e.source or id_contains in e.target)
    ][:limit]
    return json.dumps({"nodes": nodes, "edges": edges})
