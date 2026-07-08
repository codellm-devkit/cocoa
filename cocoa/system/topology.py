"""Shared service-level RPC topology rollup — the single source of truth for
report, html map, and MCP surfaces (kept in one place so they cannot diverge)."""
from __future__ import annotations

from pydantic import BaseModel

from cocoa.system.models import EdgeKind, NodeKind, Provenance, SystemGraph


class RpcTopologyEdge(BaseModel):
    client: str          # bare service name
    server: str          # bare service name
    rpc: str             # rpc:<...> node id
    provenance: Provenance


def service_rpc_edges(graph: SystemGraph) -> list[RpcTopologyEdge]:
    """Roll RPC_CALLS up to service level. Host = HOSTS edge, else HANDLES fallback
    (handler fn's service). Provenance = INFERRED if ANY contributing edge
    (RPC_CALLS, HOSTS, HANDLES) is INFERRED. Self-loops (client == server) excluded."""
    fn_svc = {n.id: n.service for n in graph.nodes if n.kind == NodeKind.FUNCTION}
    hosts: dict[str, tuple[str, Provenance]] = {
        e.target: (e.source.removeprefix("svc:"), e.provenance)
        for e in graph.edges if e.kind == EdgeKind.HOSTS
    }
    handler_svc: dict[str, tuple[str, Provenance]] = {}
    for e in graph.edges:
        if e.kind == EdgeKind.HANDLES:
            svc = fn_svc.get(e.target)
            if svc:
                handler_svc.setdefault(e.source, (svc, e.provenance))

    out: list[RpcTopologyEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for e in graph.edges:
        if e.kind != EdgeKind.RPC_CALLS:
            continue
        client = fn_svc.get(e.source)
        host, host_prov = hosts.get(e.target) or handler_svc.get(e.target) or (None, None)
        if not client or not host or client == host:
            continue
        prov = (Provenance.INFERRED
                if Provenance.INFERRED in (e.provenance, host_prov)
                else Provenance.DERIVED_STATIC)
        key = (client, host, e.target)
        if key in seen:
            # keep the weakest-marked duplicate honest: upgrade never, downgrade once
            for existing in out:
                if (existing.client, existing.server, existing.rpc) == key and prov == Provenance.INFERRED:
                    existing.provenance = Provenance.INFERRED
            continue
        seen.add(key)
        out.append(RpcTopologyEdge(client=client, server=host, rpc=e.target, provenance=prov))
    return out
