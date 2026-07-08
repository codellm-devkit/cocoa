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
