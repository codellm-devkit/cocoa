from cocoa.system.facts import from_go, from_java, from_python

JAVA_DUMP = {
    "symbol_table": {
        "src/AdService.java": {
            "type_declarations": {
                "hipstershop.AdService": {
                    "annotations": ["@Service"],
                    "callable_declarations": {
                        "getAds(String)": {
                            "signature": "getAds(String)",
                            "code": "return jedis.get(\"ads:\" + id);",
                            "start_line": 10, "end_line": 20,
                            "annotations": [],
                            "call_sites": [{
                                "method_name": "get",
                                "receiver_expr": "jedis",
                                "receiver_type": "redis.clients.jedis.Jedis",
                                "argument_types": ["java.lang.String"],
                                "argument_expr": ['"ads:" + id'],
                                "callee_signature": "get(String)",
                                "start_line": 12,
                            }],
                        }
                    },
                }
            }
        }
    },
    # validated-model dump shape (JMethodDetail endpoints)
    "call_graph": [{
        "source": {"klass": "hipstershop.AdService",
                   "method": {"signature": "getAds(String)"}},
        "target": {"klass": "hipstershop.AdService",
                   "method": {"signature": "lookup(String)"}},
        "type": "CALL_DEP", "weight": "1",
    }],
}

PY_ENVELOPE = {
    "schema_version": "2.0.0",
    "language": "python",
    "application": {
        "symbol_table": {
            "email_server.py": {
                "module_name": "email_server",
                "functions": {
                    "can://python/app/email_server.py/SendOrderConfirmation(req)": {
                        "name": "SendOrderConfirmation",
                        "signature": "can://python/app/email_server.py/SendOrderConfirmation(req)",
                        "code": "send(req)", "start_line": 5, "end_line": 9,
                        "decorators": [],
                        "call_sites": [{
                            "method_name": "send", "receiver_expr": "smtp",
                            "receiver_type": "smtplib.SMTP", "argument_types": ["str"],
                            "callee_signature": "", "start_line": 7,
                        }],
                    }
                },
                "classes": {},
            }
        },
        "call_graph": [],
    },
}

GO_RAW = {
    "symbol_table": {
        "main.go": {
            "module_name": "frontend",
            "classes": {},
            "functions": {
                "frontend.viewCartHandler(w,r)": {
                    "name": "viewCartHandler",
                    "signature": "frontend.viewCartHandler(w,r)",
                    "start_line": 30, "end_line": 60,
                    "call_sites": [{
                        "method_name": "GetCart",
                        "receiver_expr": "cl",
                        "receiver_type": "pb.CartServiceClient",
                        "argument_types": ["context.Context", "*pb.GetCartRequest"],
                        "callee_signature": "pb.CartServiceClient.GetCart",
                        "start_line": 41,
                    }],
                }
            },
        }
    },
    "call_graph": [
        {"source": "frontend.viewCartHandler(w,r)", "target": "frontend.renderCart(w)",
         "type": "CALL_DEP", "weight": 1, "provenance": ["go/types"]}
    ],
    "entrypoints": [],
}


def test_java_adapter_functions_edges_and_literal_args():
    f = from_java(JAVA_DUMP, "adservice")
    fid = "fn:adservice/hipstershop.AdService.getAds(String)"
    assert fid in f.functions
    assert f.functions[fid].code.startswith("return jedis")
    assert f.call_edges == [(fid, "fn:adservice/hipstershop.AdService.lookup(String)")]
    cs = f.call_sites[0]
    assert cs.method_name == "get" and cs.receiver_type.endswith("Jedis")
    assert cs.args == ['"ads:" + id']            # Java carries literals


def test_python_adapter_unwraps_v2_envelope():
    f = from_python(PY_ENVELOPE, "emailservice")
    fid = "fn:emailservice/can://python/app/email_server.py/SendOrderConfirmation(req)"
    assert fid in f.functions
    assert f.call_sites[0].receiver_type == "smtplib.SMTP"
    assert f.call_sites[0].args == []             # no literals outside Java


def test_go_adapter_resolves_identity_edges():
    f = from_go(GO_RAW, "frontend")
    src = "fn:frontend/frontend.viewCartHandler(w,r)"
    assert src in f.functions
    assert f.call_edges == []  # target renderCart not in symbol table -> dropped
    assert f.call_sites[0].callee_hint == "pb.CartServiceClient.GetCart"
