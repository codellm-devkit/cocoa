from cocoa.system.protos import parse_proto, rpcs_touching_field

DEMO = """
syntax = "proto3";
package hipstershop;

service CartService {
  rpc AddItem(AddItemRequest) returns (Empty) {}
  rpc GetCart(GetCartRequest) returns (Cart) {}
}

service CurrencyService {
  // converts money
  rpc Convert(CurrencyConversionRequest) returns (Money) {}
}

message Money {
  string currency_code = 1;
  int64 units = 2;
  int32 nanos = 3;
}

message CurrencyConversionRequest {
  Money from = 1;
  string to_code = 2;
}

message GetCartRequest { string user_id = 1; }
message AddItemRequest { string user_id = 1; CartItem item = 2; }
message CartItem { string product_id = 1; int32 quantity = 2; }
message Cart { string user_id = 1; repeated CartItem items = 2; }
message Empty {}
"""


def test_parses_services_rpcs_messages():
    m = parse_proto(DEMO)
    assert set(m.services) == {"hipstershop.CartService", "hipstershop.CurrencyService"}
    cart = m.services["hipstershop.CartService"]
    assert [(r.name, r.request, r.response) for r in cart.rpcs] == [
        ("AddItem", "hipstershop.AddItemRequest", "hipstershop.Empty"),
        ("GetCart", "hipstershop.GetCartRequest", "hipstershop.Cart"),
    ]
    money = m.messages["hipstershop.Money"]
    assert [(f.name, f.type, f.number) for f in money.fields] == [
        ("currency_code", "string", 1), ("units", "int64", 2), ("nanos", "int32", 3),
    ]
    assert m.messages["hipstershop.Cart"].fields[1].repeated is True


def test_field_reachability_walks_message_containment():
    m = parse_proto(DEMO)
    # Money.units: Money is Convert's response AND contained in CurrencyConversionRequest
    hits = rpcs_touching_field(m, "hipstershop.Money.units")
    assert ("hipstershop.CurrencyService", "Convert") in hits
    # CartItem.quantity reaches GetCart via Cart -> CartItem containment
    hits = rpcs_touching_field(m, "hipstershop.CartItem.quantity")
    assert ("hipstershop.CartService", "GetCart") in hits
    assert ("hipstershop.CartService", "AddItem") in hits
