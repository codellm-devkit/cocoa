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


_KNOWN_KINDS = {"proto-field", "rpc", "function", "table", "redis-key"}


def blast_radius(graph: SystemGraph, target: str, kind: str, max_depth: int = 25) -> BlastResult:
    if kind not in _KNOWN_KINDS:
        raise ValueError(f"unknown blast kind: {kind!r} (expected one of {sorted(_KNOWN_KINDS)})")
    idx = GraphIndex(graph)
    resolved = idx.resolve(target)
    result = BlastResult(target=target, kind=kind)
    if resolved is None:
        return result
    seeds = _seed_functions(idx, resolved, kind)
    result.seeds = sorted({s for s, _ in seeds})

    _RANK = {Provenance.DERIVED_STATIC: 0, Provenance.INFERRED: 1}
    _PROV = {0: Provenance.DERIVED_STATIC, 1: Provenance.INFERRED}

    best: dict[str, tuple[int, int]] = {}  # fn -> (prov_rank, depth), lexicographic best
    frontier: deque[str] = deque()

    def relax(fn: str, key: tuple[int, int]) -> None:
        if fn not in best or key < best[fn]:
            best[fn] = key
            frontier.append(fn)

    for fn, prov in seeds:
        relax(fn, (_RANK[prov], 0))

    while frontier:
        fn = frontier.popleft()
        rank, depth = best[fn]  # read current label (may have improved since enqueue)
        if depth >= max_depth:
            continue
        for e in idx.in_edges(fn):
            if e.kind == EdgeKind.CALLS:
                relax(e.source, (max(rank, _RANK[e.provenance]), depth + 1))
            elif e.kind == EdgeKind.HANDLES:
                # fn is a handler: hop to its rpc's clients. Two edges compound into
                # one logical hop (depth + 1 by design — an RPC boundary is one step).
                for c in idx.in_edges(e.source):
                    if c.kind == EdgeKind.RPC_CALLS:
                        hop_rank = max(rank, _RANK[e.provenance], _RANK[c.provenance])
                        relax(c.source, (hop_rank, depth + 1))

    for fn, (rank, depth) in sorted(best.items()):
        node = idx.nodes.get(fn)
        result.impacted.append(ImpactItem(
            node_id=fn, service=node.service if node else None,
            file=node.file if node else None, line=node.line if node else None,
            provenance=_PROV[rank], depth=depth,
        ))
        if node and node.service:
            result.by_service[node.service] = result.by_service.get(node.service, 0) + 1
    return result
