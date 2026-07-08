"""Reverse-reachability blast radius over the system graph."""
from __future__ import annotations

from collections import deque

from pydantic import BaseModel, Field

from cocoa.system.models import Edge, EdgeKind, Node, NodeKind, Provenance, SystemGraph


class ImpactItem(BaseModel):
    node_id: str
    service: str | None = None
    file: str | None = None
    line: int | None = None
    provenance: Provenance
    depth: int


class BlastResult(BaseModel):
    target: str
    kind: str
    seeds: list[str] = Field(default_factory=list)
    impacted: list[ImpactItem] = Field(default_factory=list)
    by_service: dict[str, int] = Field(default_factory=dict)


class GraphIndex:
    def __init__(self, graph: SystemGraph):
        self.nodes: dict[str, Node] = {n.id: n for n in graph.nodes}
        self._in: dict[str, list[Edge]] = {}
        self._out: dict[str, list[Edge]] = {}
        for e in graph.edges:
            self._out.setdefault(e.source, []).append(e)
            self._in.setdefault(e.target, []).append(e)

    def in_edges(self, node_id: str) -> list[Edge]:
        return self._in.get(node_id, [])

    def out_edges(self, node_id: str) -> list[Edge]:
        return self._out.get(node_id, [])

    def resolve(self, target: str) -> str | None:
        if target in self.nodes:
            return target
        matches = [nid for nid in self.nodes if nid.endswith(target)]
        return matches[0] if len(matches) == 1 else None


def _rpc_seeds_for_field(idx: GraphIndex, fld_id: str) -> set[str]:
    msgs = {e.source for e in idx.in_edges(fld_id) if e.kind == EdgeKind.HAS_FIELD}
    frontier = deque(msgs)
    while frontier:  # reverse CONTAINS closure
        cur = frontier.popleft()
        for e in idx.in_edges(cur):
            if e.kind == EdgeKind.CONTAINS and e.source not in msgs:
                msgs.add(e.source)
                frontier.append(e.source)
    return {
        e.source
        for m in msgs for e in idx.in_edges(m)
        if e.kind == EdgeKind.USES_TYPE
    }


def _seed_functions(idx: GraphIndex, resolved: str, kind: str) -> list[tuple[str, Provenance]]:
    seeds: list[tuple[str, Provenance]] = []
    if kind == "proto-field":
        rpcs = _rpc_seeds_for_field(idx, resolved)
    elif kind == "rpc":
        rpcs = {resolved}
    else:
        rpcs = set()
    for rpc in rpcs:
        for e in idx.out_edges(rpc):
            if e.kind == EdgeKind.HANDLES:
                seeds.append((e.target, e.provenance))
        for e in idx.in_edges(rpc):
            if e.kind == EdgeKind.RPC_CALLS:
                seeds.append((e.source, e.provenance))
    if kind in ("table", "redis-key", "function"):
        if idx.nodes[resolved].kind == NodeKind.FUNCTION:
            seeds.append((resolved, Provenance.DERIVED_STATIC))
        else:
            for e in idx.in_edges(resolved):
                if e.kind in (EdgeKind.READS, EdgeKind.WRITES):
                    seeds.append((e.source, e.provenance))
    return seeds


def _weaken(a: Provenance, b: Provenance) -> Provenance:
    return Provenance.INFERRED if Provenance.INFERRED in (a, b) else Provenance.DERIVED_STATIC


def blast_radius(graph: SystemGraph, target: str, kind: str, max_depth: int = 25) -> BlastResult:
    idx = GraphIndex(graph)
    resolved = idx.resolve(target)
    result = BlastResult(target=target, kind=kind)
    if resolved is None:
        return result
    seeds = _seed_functions(idx, resolved, kind)
    result.seeds = sorted({s for s, _ in seeds})

    best: dict[str, tuple[int, Provenance]] = {}
    frontier: deque[tuple[str, int, Provenance]] = deque(
        (fn, 0, prov) for fn, prov in seeds
    )
    while frontier:
        fn, depth, prov = frontier.popleft()
        seen = best.get(fn)
        if seen is not None and seen[0] <= depth and _weaken(seen[1], prov) == seen[1]:
            continue
        best[fn] = (depth, prov if seen is None else _weaken(seen[1], prov))
        if depth >= max_depth:
            continue
        for e in idx.in_edges(fn):          # reverse CALLS: who calls me
            if e.kind == EdgeKind.CALLS:
                frontier.append((e.source, depth + 1, _weaken(prov, e.provenance)))
            elif e.kind == EdgeKind.HANDLES:  # I'm a handler: hop to my rpc's clients
                for c in idx.in_edges(e.source):
                    if c.kind == EdgeKind.RPC_CALLS:
                        frontier.append((c.source, depth + 1,
                                         _weaken(_weaken(prov, e.provenance), c.provenance)))

    for fn, (depth, prov) in sorted(best.items()):
        node = idx.nodes.get(fn)
        result.impacted.append(ImpactItem(
            node_id=fn, service=node.service if node else None,
            file=node.file if node else None, line=node.line if node else None,
            provenance=prov, depth=depth,
        ))
        if node and node.service:
            result.by_service[node.service] = result.by_service.get(node.service, 0) + 1
    return result
