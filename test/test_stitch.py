from cocoa.system.facts import CallSiteFact, FunctionFact, ServiceFacts
from cocoa.system.models import EdgeKind, Provenance
from cocoa.system.protos import parse_proto
from cocoa.system.stitch import stitch

PROTO = """
syntax = "proto3";
package hipstershop;
service CartService {
  rpc GetCart(GetCartRequest) returns (Cart) {}
  rpc AddItem(AddItemRequest) returns (Empty) {}
}
message GetCartRequest { string user_id = 1; }
message AddItemRequest { string user_id = 1; }
message Cart { string user_id = 1; }
message Empty {}
"""


def _fn(service, qualified, name):
    fid = f"fn:{service}/{qualified}"
    return fid, FunctionFact(id=fid, service=service, name=name, qualified=qualified)


def _facts():
    cid, client_fn = _fn("frontend", "frontend.viewCart(w,r)", "viewCart")
    h1, handler1 = _fn("cartservice", "cart.GetCart(req)", "GetCart")
    h2, handler2 = _fn("cartservice", "cart.AddItem(req)", "AddItem")
    frontend = ServiceFacts(
        service="frontend", language="go",
        functions={cid: client_fn},
        call_sites=[CallSiteFact(
            caller_id=cid, method_name="GetCart",
            receiver_type="pb.CartServiceClient",
            callee_hint="pb.CartServiceClient.GetCart", line=41,
        )],
    )
    cart = ServiceFacts(service="cartservice", language="python",
                        functions={h1: handler1, h2: handler2})
    return {"frontend": frontend, "cartservice": cart}


def test_stitches_client_to_rpc_to_handler_derived():
    nodes, edges = stitch(_facts(), parse_proto(PROTO),
                          {"frontend": {"CART_SERVICE_ADDR": "cartservice"}})
    rpc_id = "rpc:hipstershop.CartService/GetCart"
    kinds = {(e.source, e.kind.value, e.target): e.provenance for e in edges}
    assert kinds[("fn:frontend/frontend.viewCart(w,r)", "RPC_CALLS", rpc_id)] == Provenance.DERIVED_STATIC
    assert kinds[(rpc_id, "HANDLES", "fn:cartservice/cart.GetCart(req)")] == Provenance.DERIVED_STATIC
    assert kinds[("svc:cartservice", "HOSTS", rpc_id)] == Provenance.DERIVED_STATIC
    assert any(n.id == "fld:hipstershop.Cart.user_id" for n in nodes)


def test_name_only_match_with_wiring_is_inferred():
    facts = _facts()
    facts["frontend"].call_sites[0].receiver_type = ""   # kill stub evidence
    facts["frontend"].call_sites[0].callee_hint = ""
    _, edges = stitch(facts, parse_proto(PROTO),
                      {"frontend": {"CART_SERVICE_ADDR": "cartservice"}})
    e = next(e for e in edges if e.kind == EdgeKind.RPC_CALLS)
    assert e.provenance == Provenance.INFERRED


def test_no_evidence_no_wiring_means_no_client_edge():
    facts = _facts()
    facts["frontend"].call_sites[0].receiver_type = ""
    facts["frontend"].call_sites[0].callee_hint = ""
    _, edges = stitch(facts, parse_proto(PROTO), {})
    assert not [e for e in edges if e.kind == EdgeKind.RPC_CALLS]
