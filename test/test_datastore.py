from cocoa.system.datastore import extract_data_access
from cocoa.system.facts import CallSiteFact, FunctionFact, ServiceFacts
from cocoa.system.models import EdgeKind
from cocoa.system.wiring import Workload


def _svc(service, lang, fn_kwargs, sites=()):
    fid = f"fn:{service}/{fn_kwargs['qualified']}"
    fn = FunctionFact(id=fid, service=service, **fn_kwargs)
    return ServiceFacts(service=service, language=lang,
                        functions={fid: fn}, call_sites=list(sites)), fid


def test_redis_get_becomes_read_edge_with_key_literal():
    facts, fid = _svc(
        "adservice", "java",
        dict(name="getAds(String)", qualified="Ads.getAds(String)"),
        [CallSiteFact(caller_id="fn:adservice/Ads.getAds(String)", method_name="get",
                      receiver_type="redis.clients.jedis.Jedis", args=['"ads:hot"'], line=12)],
    )
    wl = Workload(name="adservice", env={"REDIS_ADDR": "redis-cart:6379"})
    nodes, edges = extract_data_access({"adservice": facts}, [wl])
    ids = {n.id for n in nodes}
    assert "ds:redis:redis-cart" in ids and "key:ads:hot" in ids
    reads = [(e.source, e.target) for e in edges if e.kind == EdgeKind.READS]
    assert (fid, "ds:redis:redis-cart") in reads
    assert (fid, "key:ads:hot") in reads


def test_sql_literal_in_code_yields_table_edges():
    facts, fid = _svc(
        "productcatalog", "go",
        dict(name="listProducts", qualified="cat.listProducts()",
             code='rows := db.Query("SELECT id, name FROM products WHERE active = 1")'),
    )
    nodes, edges = extract_data_access({"productcatalog": facts}, [])
    assert "tbl:products" in {n.id for n in nodes}
    assert [(e.source, e.target) for e in edges if e.kind == EdgeKind.READS] == [(fid, "tbl:products")]


def test_sqlalchemy_tablename_yields_orm_table():
    facts, fid = _svc(
        "emailservice", "python",
        dict(name="Order", qualified="models.Order",
             code='class Order(Base):\n    __tablename__ = "orders"\n'),
    )
    nodes, edges = extract_data_access({"emailservice": facts}, [])
    assert "tbl:orders" in {n.id for n in nodes}
    kinds = {e.kind for e in edges if e.target == "tbl:orders"}
    assert kinds == {EdgeKind.READS, EdgeKind.WRITES}


def test_unknown_redis_command_becomes_write_edge_with_op_attr():
    facts, fid = _svc(
        "cartservice", "java",
        dict(name="doThing(String)", qualified="Cart.doThing(String)"),
        [CallSiteFact(caller_id="fn:cartservice/Cart.doThing(String)", method_name="pfadd",
                      receiver_type="redis.clients.jedis.Jedis", args=[], line=5)],
    )
    nodes, edges = extract_data_access({"cartservice": facts}, [])
    writes = [e for e in edges if e.kind == EdgeKind.WRITES and e.source == fid]
    assert len(writes) == 1
    assert writes[0].attrs.get("op") == "pfadd"


def test_no_env_match_falls_back_to_service_name_unresolved():
    facts, fid = _svc(
        "cartservice", "java",
        dict(name="get(String)", qualified="Cart.get(String)"),
        [CallSiteFact(caller_id="fn:cartservice/Cart.get(String)", method_name="get",
                      receiver_type="redis.clients.jedis.Jedis", args=[], line=7)],
    )
    wl = Workload(name="cartservice", env={"OTHER_VAR": "somehost:1234"})
    nodes, edges = extract_data_access({"cartservice": facts}, [wl])
    ds_nodes = [n for n in nodes if n.id == "ds:redis:cartservice"]
    assert len(ds_nodes) == 1
    assert ds_nodes[0].attrs.get("resolved") == "false"
    ds_edges = [e for e in edges if e.target == "ds:redis:cartservice"]
    assert ds_edges and all(e.provenance == "DERIVED-STATIC" for e in ds_edges)


def test_insert_into_orders_yields_write_edge():
    facts, fid = _svc(
        "checkoutservice", "go",
        dict(name="placeOrder", qualified="co.placeOrder()",
             code='db.Exec("INSERT INTO orders (id, total) VALUES (?, ?)")'),
    )
    nodes, edges = extract_data_access({"checkoutservice": facts}, [])
    assert "tbl:orders" in {n.id for n in nodes}
    writes = [(e.source, e.target) for e in edges if e.kind == EdgeKind.WRITES]
    assert (fid, "tbl:orders") in writes


def test_jpa_table_annotation_yields_orm_table():
    facts, fid = _svc(
        "adservice", "java",
        dict(name="Ad", qualified="model.Ad", annotations=['@Table(name="ads")']),
    )
    nodes, edges = extract_data_access({"adservice": facts}, [])
    assert "tbl:ads" in {n.id for n in nodes}
    kinds = {e.kind for e in edges if e.target == "tbl:ads"}
    assert kinds == {EdgeKind.READS, EdgeKind.WRITES}


def test_predisposition_service_call_site_yields_no_datastore_edges():
    facts, fid = _svc(
        "recommendationservice", "java",
        dict(name="get(String)", qualified="Rec.get(String)"),
        [CallSiteFact(caller_id="fn:recommendationservice/Rec.get(String)", method_name="get",
                      receiver="predispositionService", receiver_type="PredispositionService",
                      callee_hint="PredispositionService.get", args=[], line=3)],
    )
    nodes, edges = extract_data_access({"recommendationservice": facts}, [])
    assert nodes == []
    assert edges == []


def test_expire_with_non_key_second_arg_has_no_key_node():
    facts, fid = _svc(
        "cartservice", "java",
        dict(name="expire(String,String)", qualified="Cart.expire(String,String)"),
        [CallSiteFact(caller_id="fn:cartservice/Cart.expire(String,String)", method_name="expire",
                      receiver_type="redis.clients.jedis.Jedis",
                      args=["userIdVar", '"30"'], line=9)],
    )
    nodes, edges = extract_data_access({"cartservice": facts}, [])
    ds_edges = [e for e in edges if e.target.startswith("ds:redis:")]
    assert ds_edges
    assert not any(n.kind == "key_pattern" for n in nodes)
    assert not any(e.target.startswith("key:") for e in edges)


def test_prose_select_yields_no_table_nodes():
    facts, fid = _svc(
        "cartservice", "python",
        dict(name="get_cart", qualified="cart.get_cart",
             code='label = "select an item from your cart"'),
    )
    nodes, edges = extract_data_access({"cartservice": facts}, [])
    assert not any(n.kind == "table" for n in nodes)
    assert edges == []


def test_prose_select_with_the_catalog_yields_no_table_nodes():
    facts, fid = _svc(
        "productcatalogservice", "python",
        dict(name="describe", qualified="cat.describe",
             code='msg = "select a product from the catalog"'),
    )
    nodes, edges = extract_data_access({"productcatalogservice": facts}, [])
    assert not any(n.kind == "table" for n in nodes)


def test_three_methods_sharing_tablename_dedup_to_one_edge_pair():
    tablename_code = 'class Cart(Base):\n    __tablename__ = "carts"\n'
    fid1 = "fn:cartservice/Cart.add"
    fid2 = "fn:cartservice/Cart.remove"
    fid3 = "fn:cartservice/Cart.empty"
    fn1 = FunctionFact(id=fid1, service="cartservice", name="add", qualified="Cart.add", code=tablename_code)
    fn2 = FunctionFact(id=fid2, service="cartservice", name="remove", qualified="Cart.remove", code=tablename_code)
    fn3 = FunctionFact(id=fid3, service="cartservice", name="empty", qualified="Cart.empty", code=tablename_code)
    facts = ServiceFacts(service="cartservice", language="python",
                         functions={fid1: fn1, fid2: fn2, fid3: fn3})
    nodes, edges = extract_data_access({"cartservice": facts}, [])
    tbl_edges = [e for e in edges if e.target == "tbl:carts"]
    assert len(tbl_edges) == 2
    assert {e.kind for e in tbl_edges} == {EdgeKind.READS, EdgeKind.WRITES}
