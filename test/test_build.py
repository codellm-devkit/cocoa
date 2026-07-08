from pathlib import Path

from cocoa.system import build
from cocoa.system.facts import CallSiteFact, FunctionFact, ServiceFacts
from cocoa.system.models import EdgeKind, NodeKind, Skipped, SystemGraph


def _fake_analyze(system, cache_dir):
    cid = "fn:frontend/frontend.viewCart(w,r)"
    hid = "fn:cartservice/cart.GetCart(req)"
    frontend = ServiceFacts(
        service="frontend", language="go",
        functions={cid: FunctionFact(id=cid, service="frontend", name="viewCart",
                                     qualified="frontend.viewCart(w,r)", file="main.go")},
        call_sites=[CallSiteFact(caller_id=cid, method_name="GetCart",
                                 receiver_type="pb.CartServiceClient", line=41)],
    )
    cart = ServiceFacts(
        service="cartservice", language="python",
        functions={hid: FunctionFact(id=hid, service="cartservice", name="GetCart",
                                     qualified="cart.GetCart(req)")},
    )
    return {"frontend": frontend, "cartservice": cart}, [
        Skipped(service="loadgenerator", language="python", reason="test skip")
    ]


PROTO = 'syntax = "proto3";\npackage hipstershop;\nservice CartService { rpc GetCart(Req) returns (Resp) {} rpc AddItem(Req) returns (Resp) {} }\nmessage Req { string user_id = 1; }\nmessage Resp { string ok = 1; }\n'


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "protos").mkdir(parents=True)
    (tmp_path / "protos" / "demo.proto").write_text(PROTO)
    (tmp_path / "src" / "frontend").mkdir(parents=True)
    (tmp_path / "src" / "frontend" / "go.mod").write_text("module frontend")
    (tmp_path / "src" / "cartservice").mkdir(parents=True)
    (tmp_path / "src" / "cartservice" / "requirements.txt").write_text("grpcio")
    (tmp_path / "kubernetes-manifests").mkdir(parents=True)
    (tmp_path / "kubernetes-manifests" / "frontend.yaml").write_text(
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata: {name: frontend}\n"
        "spec:\n"
        "  template:\n"
        "    spec:\n"
        "      containers:\n"
        "        - name: server\n"
        "          image: frontend:v1\n"
        "          env:\n"
        "            - name: CART_SERVICE_ADDR\n"
        "              value: \"cartservice:7070\"\n"
    )
    return tmp_path


def test_build_assembles_and_annotates(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(build, "analyze_system", _fake_analyze)
    g = build.build_system_graph(_repo(tmp_path))
    ids = g.node_ids()
    assert {"svc:frontend", "svc:cartservice"} <= ids
    assert "fn:frontend/frontend.viewCart(w,r)" in ids
    assert any(e.kind == EdgeKind.RPC_CALLS for e in g.edges)
    # AddItem has no client call sites -> DECLARED-UNUSED
    unused = next(n for n in g.nodes if n.id == "rpc:hipstershop.CartService/AddItem")
    assert unused.attrs.get("annotation") == "DECLARED-UNUSED"
    used = next(n for n in g.nodes if n.id == "rpc:hipstershop.CartService/GetCart")
    assert "annotation" not in used.attrs
    assert g.skipped[0].service == "loadgenerator"


def test_build_assembles_workload_nodes_and_wiring(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(build, "analyze_system", _fake_analyze)
    g = build.build_system_graph(_repo(tmp_path))
    wl = next(n for n in g.nodes if n.id == "wl:frontend")
    assert wl.kind == NodeKind.K8S_WORKLOAD
    assert wl.attrs["image"] == "frontend:v1"


def test_write_artifacts_persists_graph(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(build, "analyze_system", _fake_analyze)
    g = build.build_system_graph(_repo(tmp_path))
    paths = build.write_artifacts(g, tmp_path / ".cocoa")
    assert SystemGraph.load(paths["graph"]) == g
