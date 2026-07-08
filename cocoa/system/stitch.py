"""Cross-service RPC stitching: protos + call sites + wiring -> derived edges."""
from __future__ import annotations

from cocoa.system.facts import ServiceFacts
from cocoa.system.models import Edge, EdgeKind, Node, NodeKind, Provenance
from cocoa.system.protos import ProtoModel


def _rpc_id(service_fqn: str, rpc: str) -> str:
    return f"rpc:{service_fqn}/{rpc}"


def _proto_nodes(protos: ProtoModel) -> tuple[list[Node], list[Edge]]:
    nodes, edges = [], []
    for fqn, msg in protos.messages.items():
        nodes.append(Node(id=f"msg:{fqn}", kind=NodeKind.PROTO_MESSAGE))
        for f in msg.fields:
            fld = f"fld:{fqn}.{f.name}"
            nodes.append(Node(id=fld, kind=NodeKind.PROTO_FIELD,
                              attrs={"type": f.type, "number": str(f.number)}))
            edges.append(Edge(source=f"msg:{fqn}", target=fld, kind=EdgeKind.HAS_FIELD,
                              provenance=Provenance.DERIVED_STATIC))
            if f.type in protos.messages:
                edges.append(Edge(source=f"msg:{fqn}", target=f"msg:{f.type}",
                                  kind=EdgeKind.CONTAINS, provenance=Provenance.DERIVED_STATIC))
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
    """proto service fqn -> (hosting service | None, {rpc_name_lower: handler fn id})."""
    out: dict[str, tuple[str | None, dict[str, str]]] = {}
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
        out[fqn] = (best[1], best[2])
    return out


def stitch(
    facts_by_service: dict[str, ServiceFacts],
    protos: ProtoModel,
    client_targets: dict[str, dict[str, str]],
) -> tuple[list[Node], list[Edge]]:
    nodes, edges = _proto_nodes(protos)
    anchors = _server_anchors(facts_by_service, protos)
    wired_targets = {c: set(t.values()) for c, t in client_targets.items()}

    for fqn, svc in protos.services.items():
        host, handlers = anchors[fqn]
        bare = fqn.rsplit(".", 1)[-1].lower()
        if host is None:  # fall back to wiring: some client points at a workload named like it
            for targets in wired_targets.values():
                match = next((t for t in targets if t.lower() in bare or bare in t.lower()), None)
                if match and match in facts_by_service:
                    host = match
                    break
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
        # client side
        for cname, sf in facts_by_service.items():
            for cs in sf.call_sites:
                rpc_real = {r.name.lower(): r.name for r in svc.rpcs}.get(cs.method_name.lower())
                if not rpc_real:
                    continue
                evidence = f"{cs.receiver_type} {cs.callee_hint}".lower()
                if bare in evidence:
                    prov = Provenance.DERIVED_STATIC
                elif host and host in wired_targets.get(cname, set()):
                    prov = Provenance.INFERRED
                else:
                    continue
                edges.append(Edge(
                    source=cs.caller_id, target=_rpc_id(fqn, rpc_real),
                    kind=EdgeKind.RPC_CALLS, provenance=prov,
                    site_file=sf.functions.get(cs.caller_id, None) and sf.functions[cs.caller_id].file,
                    site_line=cs.line,
                ))
    return nodes, edges
