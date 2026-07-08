"""Orchestrate: detect -> analyze -> stitch -> data access -> annotated SystemGraph."""
from __future__ import annotations

from pathlib import Path

from cocoa.system.datastore import extract_data_access
from cocoa.system.detect import detect
from cocoa.system.driver import analyze_system
from cocoa.system.models import Edge, EdgeKind, Node, NodeKind, Provenance, SystemGraph
from cocoa.system.protos import parse_proto_files
from cocoa.system.stitch import stitch
from cocoa.system.wiring import Workload, parse_compose, parse_k8s_dir, rpc_addr_targets

ARTIFACT_DIR = ".cocoa"


def build_system_graph(root: Path, cache_dir: Path | None = None) -> SystemGraph:
    root = Path(root).resolve()
    cache = Path(cache_dir) if cache_dir else root / ARTIFACT_DIR / "cache"
    system = detect(root)

    workloads: list[Workload] = []
    for d in system.manifest_dirs:
        workloads.extend(parse_k8s_dir(Path(d)))
    for f in system.compose_files:
        workloads.extend(parse_compose(Path(f)))

    facts, skipped = analyze_system(system, cache)
    protos = parse_proto_files([Path(p) for p in system.proto_files])
    client_targets = rpc_addr_targets(workloads)

    graph = SystemGraph(root=str(root), skipped=skipped)
    for svc in system.services:
        graph.nodes.append(Node(id=f"svc:{svc.name}", kind=NodeKind.SERVICE,
                                service=svc.name, attrs={"language": svc.language}))
    for w in workloads:
        graph.nodes.append(Node(id=f"wl:{w.name}", kind=NodeKind.K8S_WORKLOAD,
                                attrs={"image": w.image or ""}))
    for sf in facts.values():
        for fn in sf.functions.values():
            graph.nodes.append(Node(id=fn.id, kind=NodeKind.FUNCTION, service=fn.service,
                                    file=fn.file, line=fn.start_line))
        for s, t in sf.call_edges:
            graph.edges.append(Edge(source=s, target=t, kind=EdgeKind.CALLS,
                                    provenance=Provenance.DERIVED_STATIC))

    s_nodes, s_edges = stitch(facts, protos, client_targets)
    d_nodes, d_edges = extract_data_access(facts, workloads)
    known = graph.node_ids()
    graph.nodes.extend(n for n in s_nodes + d_nodes if n.id not in known)
    graph.edges.extend(s_edges + d_edges)

    called = {e.target for e in graph.edges if e.kind == EdgeKind.RPC_CALLS}
    for n in graph.nodes:
        if n.kind == NodeKind.RPC_ENDPOINT and n.id not in called:
            n.attrs["annotation"] = "DECLARED-UNUSED"
    return graph


def write_artifacts(graph: SystemGraph, out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    graph_path = out_dir / "system-graph.json"
    graph.save(graph_path)
    return {"graph": graph_path}
