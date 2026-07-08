def test_inferred_hosts_binding_compounds_into_topology():
    from cocoa.system.models import Edge, EdgeKind as K, Node, NodeKind as N, Provenance as P, SystemGraph
    from cocoa.system.topology import service_rpc_edges
    nodes = [
        Node(id="svc:frontend", kind=N.SERVICE), Node(id="svc:cartsvc", kind=N.SERVICE),
        Node(id="fn:frontend/f", kind=N.FUNCTION, service="frontend"),
        Node(id="rpc:p.Cart/Get", kind=N.RPC_ENDPOINT),
    ]
    E = lambda s, t, k, p: Edge(source=s, target=t, kind=k, provenance=p)
    g = SystemGraph(root="/x", nodes=nodes, edges=[
        E("svc:cartsvc", "rpc:p.Cart/Get", K.HOSTS, P.INFERRED),        # wiring-only host
        E("fn:frontend/f", "rpc:p.Cart/Get", K.RPC_CALLS, P.DERIVED_STATIC),
    ])
    rows = service_rpc_edges(g)
    assert [(r.client, r.server, r.provenance) for r in rows] == [("frontend", "cartsvc", P.INFERRED)]


def test_self_loops_excluded_everywhere():
    from cocoa.system.models import Edge, EdgeKind as K, Node, NodeKind as N, Provenance as P, SystemGraph
    from cocoa.system.topology import service_rpc_edges
    nodes = [
        Node(id="svc:orders", kind=N.SERVICE),
        Node(id="fn:orders/a", kind=N.FUNCTION, service="orders"),
        Node(id="fn:orders/h", kind=N.FUNCTION, service="orders"),
        Node(id="rpc:p.O/Do", kind=N.RPC_ENDPOINT),
    ]
    g = SystemGraph(root="/x", nodes=nodes, edges=[
        Edge(source="rpc:p.O/Do", target="fn:orders/h", kind=K.HANDLES, provenance=P.DERIVED_STATIC),
        Edge(source="fn:orders/a", target="rpc:p.O/Do", kind=K.RPC_CALLS, provenance=P.DERIVED_STATIC),
    ])
    assert service_rpc_edges(g) == []
