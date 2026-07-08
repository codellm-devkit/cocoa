from cocoa.system.blast import blast_radius
from cocoa.system.models import Edge, EdgeKind as K, Node, NodeKind as N, Provenance as P, SystemGraph


def _g() -> SystemGraph:
    """frontend.viewCart -RPC-> GetCart -HANDLES-> cart.GetCart -CALLS<- (reverse) cart.load
    cart.GetCart -READS-> ds:redis. Money.units field on Cart used by GetCart."""
    nodes = [
        Node(id="svc:frontend", kind=N.SERVICE), Node(id="svc:cartservice", kind=N.SERVICE),
        Node(id="fn:frontend/viewCart", kind=N.FUNCTION, service="frontend", file="main.go", line=40),
        Node(id="fn:frontend/render", kind=N.FUNCTION, service="frontend"),
        Node(id="fn:cartservice/GetCart", kind=N.FUNCTION, service="cartservice"),
        Node(id="fn:cartservice/load", kind=N.FUNCTION, service="cartservice"),
        Node(id="rpc:hipstershop.CartService/GetCart", kind=N.RPC_ENDPOINT),
        Node(id="msg:hipstershop.Cart", kind=N.PROTO_MESSAGE),
        Node(id="msg:hipstershop.Money", kind=N.PROTO_MESSAGE),
        Node(id="fld:hipstershop.Money.units", kind=N.PROTO_FIELD),
        Node(id="ds:redis:redis-cart", kind=N.DATASTORE),
    ]
    E = lambda s, t, k, p=P.DERIVED_STATIC: Edge(source=s, target=t, kind=k, provenance=p)
    edges = [
        E("fn:frontend/render", "fn:frontend/viewCart", K.CALLS),
        E("fn:frontend/viewCart", "rpc:hipstershop.CartService/GetCart", K.RPC_CALLS),
        E("rpc:hipstershop.CartService/GetCart", "fn:cartservice/GetCart", K.HANDLES),
        E("fn:cartservice/GetCart", "fn:cartservice/load", K.CALLS),
        E("fn:cartservice/GetCart", "ds:redis:redis-cart", K.READS),
        E("rpc:hipstershop.CartService/GetCart", "msg:hipstershop.Cart", K.USES_TYPE),
        E("msg:hipstershop.Cart", "msg:hipstershop.Money", K.CONTAINS),
        E("msg:hipstershop.Money", "fld:hipstershop.Money.units", K.HAS_FIELD),
    ]
    return SystemGraph(root="/x", nodes=nodes, edges=edges)


def test_proto_field_blast_crosses_services():
    r = blast_radius(_g(), "hipstershop.Money.units", "proto-field")
    ids = {i.node_id for i in r.impacted}
    assert "fn:cartservice/GetCart" in ids          # handler
    assert "fn:frontend/viewCart" in ids            # client call site
    assert "fn:frontend/render" in ids              # reverse CALLS closure on client side
    assert r.by_service == {"cartservice": 1, "frontend": 2}


def test_redis_blast_reaches_frontend_through_rpc_hop():
    r = blast_radius(_g(), "ds:redis:redis-cart", "redis-key")
    ids = {i.node_id for i in r.impacted}
    assert {"fn:cartservice/GetCart", "fn:frontend/viewCart", "fn:frontend/render"} <= ids


def test_inferred_hop_weakens_provenance():
    g = _g()
    rpc_edge = next(e for e in g.edges if e.kind == K.RPC_CALLS)
    rpc_edge.provenance = P.INFERRED
    r = blast_radius(g, "ds:redis:redis-cart", "redis-key")
    fe = next(i for i in r.impacted if i.node_id == "fn:frontend/viewCart")
    assert fe.provenance == P.INFERRED


def test_unknown_target_returns_empty_result():
    r = blast_radius(_g(), "no.such.thing", "function")
    assert r.impacted == [] and r.seeds == []


def test_later_weaker_path_does_not_corrupt_strong_result():
    """Diamond: X has a direct DERIVED path (depth 1) and a longer INFERRED path via M."""
    nodes = [
        Node(id="fn:s/seed", kind=N.FUNCTION, service="s"),
        Node(id="fn:s/X", kind=N.FUNCTION, service="s"),
        Node(id="fn:s/M", kind=N.FUNCTION, service="s"),
    ]
    E = lambda s, t, k, p=P.DERIVED_STATIC: Edge(source=s, target=t, kind=k, provenance=p)
    g = SystemGraph(root="/x", nodes=nodes, edges=[
        E("fn:s/X", "fn:s/seed", K.CALLS),                       # strong, depth 1
        E("fn:s/M", "fn:s/seed", K.CALLS),
        E("fn:s/X", "fn:s/M", K.CALLS, P.INFERRED),              # weak, depth 2
    ])
    r = blast_radius(g, "fn:s/seed", "function")
    x = next(i for i in r.impacted if i.node_id == "fn:s/X")
    assert (x.provenance, x.depth) == (P.DERIVED_STATIC, 1)


def test_stronger_later_path_upgrades_inferred_result():
    """X reaches seed via INFERRED depth-1 AND via DERIVED depth-2: strongest path wins, with ITS depth."""
    nodes = [
        Node(id="fn:s/seed", kind=N.FUNCTION, service="s"),
        Node(id="fn:s/X", kind=N.FUNCTION, service="s"),
        Node(id="fn:s/Y", kind=N.FUNCTION, service="s"),
    ]
    E = lambda s, t, k, p=P.DERIVED_STATIC: Edge(source=s, target=t, kind=k, provenance=p)
    g = SystemGraph(root="/x", nodes=nodes, edges=[
        E("fn:s/X", "fn:s/seed", K.CALLS, P.INFERRED),
        E("fn:s/Y", "fn:s/seed", K.CALLS),
        E("fn:s/X", "fn:s/Y", K.CALLS),
    ])
    r = blast_radius(g, "fn:s/seed", "function")
    x = next(i for i in r.impacted if i.node_id == "fn:s/X")
    assert (x.provenance, x.depth) == (P.DERIVED_STATIC, 2)


def test_cycles_terminate_with_min_depths():
    nodes = [Node(id=f"fn:s/{n}", kind=N.FUNCTION, service="s") for n in ("seed", "A", "B")]
    E = lambda s, t: Edge(source=s, target=t, kind=K.CALLS, provenance=P.DERIVED_STATIC)
    g = SystemGraph(root="/x", nodes=nodes, edges=[
        E("fn:s/B", "fn:s/seed"), E("fn:s/A", "fn:s/B"), E("fn:s/B", "fn:s/A"),
    ])
    r = blast_radius(g, "fn:s/seed", "function")
    depths = {i.node_id: i.depth for i in r.impacted}
    assert depths["fn:s/B"] == 1 and depths["fn:s/A"] == 2


def test_ambiguous_suffix_resolves_to_nothing():
    nodes = [Node(id="fn:a/x.go", kind=N.FUNCTION, service="a"),
             Node(id="fn:b/x.go", kind=N.FUNCTION, service="b")]
    g = SystemGraph(root="/x", nodes=nodes, edges=[])
    r = blast_radius(g, "x.go", "function")
    assert r.seeds == [] and r.impacted == []


def test_unknown_kind_raises():
    import pytest as _pytest
    g = SystemGraph(root="/x", nodes=[], edges=[])
    with _pytest.raises(ValueError):
        blast_radius(g, "anything", "banana")
