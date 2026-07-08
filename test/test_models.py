from pathlib import Path

from cocoa.system.models import (
    Edge, EdgeKind, Node, NodeKind, Provenance, Skipped, SystemGraph,
)


def _graph() -> SystemGraph:
    return SystemGraph(
        root="/tmp/app",
        nodes=[
            Node(id="svc:frontend", kind=NodeKind.SERVICE, service="frontend"),
            Node(id="rpc:hipstershop.CartService/GetCart", kind=NodeKind.RPC_ENDPOINT),
        ],
        edges=[
            Edge(
                source="svc:frontend",
                target="rpc:hipstershop.CartService/GetCart",
                kind=EdgeKind.RPC_CALLS,
                provenance=Provenance.DERIVED_STATIC,
                site_file="src/frontend/rpc.go",
                site_line=42,
            )
        ],
        skipped=[Skipped(service="cartservice", language="csharp", reason="no analyzer backend")],
    )


def test_provenance_values_are_spec_exact():
    assert Provenance.DERIVED_STATIC.value == "DERIVED-STATIC"
    assert Provenance.INFERRED.value == "INFERRED"


def test_graph_round_trips_through_json(tmp_path: Path):
    g = _graph()
    out = tmp_path / "system-graph.json"
    g.save(out)
    g2 = SystemGraph.load(out)
    assert g2 == g
    assert g2.node_ids() == {"svc:frontend", "rpc:hipstershop.CartService/GetCart"}
    assert g2.edges[0].provenance == Provenance.DERIVED_STATIC
    assert g2.skipped[0].reason == "no analyzer backend"
