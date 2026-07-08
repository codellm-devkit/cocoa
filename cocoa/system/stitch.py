"""Cross-service RPC stitching: protos + call sites + wiring -> derived edges."""
from __future__ import annotations

import re

from cocoa.system.facts import ServiceFacts
from cocoa.system.models import Edge, EdgeKind, Node, NodeKind, Provenance
from cocoa.system.protos import ProtoModel

_STUB_SUFFIXES = "client|stub|server|servicer|impl"
_NON_ALNUM = re.compile(r"[^a-z0-9]")


def _rpc_id(service_fqn: str, rpc: str) -> str:
    return f"rpc:{service_fqn}/{rpc}"


def _evidence_matches(bare: str, evidence: str) -> bool:
    """bare service name appears in evidence at an identifier boundary, optionally
    glued to a known stub suffix (client/stub/server/servicer/impl)."""
    return re.search(
        rf"(?<![a-z0-9]){re.escape(bare)}(?:{_STUB_SUFFIXES})?(?![a-z0-9])",
        evidence,
    ) is not None


def _norm(s: str) -> str:
    return _NON_ALNUM.sub("", s.lower())


def _wiring_matches_bare(target: str, bare: str) -> bool:
    """normalized-name equality between a wiring target and a proto service's bare name."""
    nt, nb = _norm(target), _norm(bare)
    return nt == nb or nt + "service" == nb or nt == nb + "service"


def _proto_nodes(protos: ProtoModel) -> tuple[list[Node], list[Edge]]:
    nodes, edges = [], []
    seen_contains: set[tuple[str, str]] = set()
    for fqn, msg in protos.messages.items():
        nodes.append(Node(id=f"msg:{fqn}", kind=NodeKind.PROTO_MESSAGE))
        for f in msg.fields:
            fld = f"fld:{fqn}.{f.name}"
            nodes.append(Node(id=fld, kind=NodeKind.PROTO_FIELD,
                              attrs={"type": f.type, "number": str(f.number)}))
            edges.append(Edge(source=f"msg:{fqn}", target=fld, kind=EdgeKind.HAS_FIELD,
                              provenance=Provenance.DERIVED_STATIC))
            if f.type in protos.messages:
                key = (f"msg:{fqn}", f"msg:{f.type}")
                if key not in seen_contains:
                    seen_contains.add(key)
                    edges.append(Edge(source=key[0], target=key[1], kind=EdgeKind.CONTAINS,
                                      provenance=Provenance.DERIVED_STATIC))
    for fqn, svc in protos.services.items():
        for rpc in svc.rpcs:
            rid = _rpc_id(fqn, rpc.name)
            nodes.append(Node(id=rid, kind=NodeKind.RPC_ENDPOINT,
                              attrs={"proto_service": fqn, "rpc": rpc.name}))
            for msg in (rpc.request, rpc.response):
                if msg in protos.messages:
                    edges.append(Edge(source=rid, target=f"msg:{msg}",
                                      kind=EdgeKind.USES_TYPE,
                                      provenance=Provenance.DERIVED_STATIC))
    return nodes, edges


def _server_anchors(
    facts: dict[str, ServiceFacts], protos: ProtoModel
) -> dict[str, tuple[str | None, dict[str, str]]]:
    """proto service fqn -> (hosting service | None, {rpc_name_lower: handler fn id}).

    Anchor exclusivity: a proto service S keeps its winning candidate iff it matched
    >=2 distinct rpc names, OR (when it matched exactly 1) that single handler fn is
    not also claimed as a match by any other proto service. Otherwise S is unanchored
    for server-side purposes (it may still get an INFERRED host via wiring fallback).
    """
    candidates: dict[str, tuple[int, str | None, dict[str, str]]] = {}
    for fqn, svc in protos.services.items():
        rpc_names = {r.name.lower(): r.name for r in svc.rpcs}
        best: tuple[int, str | None, dict[str, str]] = (0, None, {})
        for sname, sf in facts.items():
            handlers = {
                fn.name.lower(): fid
                for fid, fn in sf.functions.items()
                if fn.name.lower() in rpc_names
            }
            if len(handlers) > best[0]:
                best = (len(handlers), sname, handlers)
        candidates[fqn] = best

    claims: dict[str, set[str]] = {}
    for fqn, (count, _host, handlers) in candidates.items():
        if count:
            for fid in handlers.values():
                claims.setdefault(fid, set()).add(fqn)

    out: dict[str, tuple[str | None, dict[str, str]]] = {}
    for fqn, (count, host, handlers) in candidates.items():
        if count >= 2:
            out[fqn] = (host, handlers)
        elif count == 1:
            (fid,) = handlers.values()
            out[fqn] = (host, handlers) if len(claims.get(fid, set())) == 1 else (None, {})
        else:
            out[fqn] = (None, {})
    return out


def stitch(
    facts_by_service: dict[str, ServiceFacts],
    protos: ProtoModel,
    client_targets: dict[str, dict[str, str]],
) -> tuple[list[Node], list[Edge]]:
    nodes, edges = _proto_nodes(protos)
    anchors = _server_anchors(facts_by_service, protos)
    wired_targets = {c: set(t.values()) for c, t in client_targets.items()}

    bare_by_fqn = {fqn: fqn.rsplit(".", 1)[-1].lower() for fqn in protos.services}
    rpc_lookup = {
        fqn: {r.name.lower(): r.name for r in svc.rpcs} for fqn, svc in protos.services.items()
    }

    # Resolve each proto service's host: server-anchored, or a wiring target whose
    # normalized name equals the proto service's bare name.
    resolved_host: dict[str, str | None] = {}
    for fqn in protos.services:
        host, _handlers = anchors[fqn]
        if host is None:
            bare = bare_by_fqn[fqn]
            for targets in wired_targets.values():
                match = next((t for t in targets if _wiring_matches_bare(t.lower(), bare)), None)
                if match and match in facts_by_service:
                    host = match
                    break
        resolved_host[fqn] = host

    # server side: HOSTS / HANDLES
    for fqn, svc in protos.services.items():
        _, handlers = anchors[fqn]
        host = resolved_host[fqn]
        for rpc in svc.rpcs:
            rid = _rpc_id(fqn, rpc.name)
            handler_fid = handlers.get(rpc.name.lower())
            if host:
                edges.append(Edge(
                    source=f"svc:{host}", target=rid, kind=EdgeKind.HOSTS,
                    provenance=Provenance.DERIVED_STATIC if handler_fid else Provenance.INFERRED,
                ))
            if handler_fid:
                edges.append(Edge(source=rid, target=handler_fid, kind=EdgeKind.HANDLES,
                                  provenance=Provenance.DERIVED_STATIC))

    # group proto services by rpc name so a call site can be checked against every
    # proto service that declares that rpc, not just one at a time
    services_by_rpc_name: dict[str, list[str]] = {}
    for fqn, svc in protos.services.items():
        for rpc in svc.rpcs:
            services_by_rpc_name.setdefault(rpc.name.lower(), []).append(fqn)

    # client side: RPC_CALLS
    for cname, sf in facts_by_service.items():
        for cs in sf.call_sites:
            candidate_fqns = services_by_rpc_name.get(cs.method_name.lower(), [])
            if not candidate_fqns:
                continue
            fn = sf.functions.get(cs.caller_id)
            site_file = fn.file if fn else None
            evidence = f"{cs.receiver_type} {cs.callee_hint}".lower()
            matched = [fqn for fqn in candidate_fqns if _evidence_matches(bare_by_fqn[fqn], evidence)]
            if len(matched) == 1:
                fqn = matched[0]
                edges.append(Edge(
                    source=cs.caller_id, target=_rpc_id(fqn, rpc_lookup[fqn][cs.method_name.lower()]),
                    kind=EdgeKind.RPC_CALLS, provenance=Provenance.DERIVED_STATIC,
                    site_file=site_file, site_line=cs.line,
                ))
            elif len(matched) > 1:
                for fqn in matched:
                    edges.append(Edge(
                        source=cs.caller_id, target=_rpc_id(fqn, rpc_lookup[fqn][cs.method_name.lower()]),
                        kind=EdgeKind.RPC_CALLS, provenance=Provenance.INFERRED,
                        site_file=site_file, site_line=cs.line, attrs={"ambiguous": "true"},
                    ))
            else:
                for fqn in candidate_fqns:
                    host = resolved_host[fqn]
                    if host and host in wired_targets.get(cname, set()):
                        edges.append(Edge(
                            source=cs.caller_id,
                            target=_rpc_id(fqn, rpc_lookup[fqn][cs.method_name.lower()]),
                            kind=EdgeKind.RPC_CALLS, provenance=Provenance.INFERRED,
                            site_file=site_file, site_line=cs.line,
                        ))
    return nodes, edges
