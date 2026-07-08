from cocoa.system.wiring import Workload, parse_k8s_documents, rpc_addr_targets

K8S = """
apiVersion: apps/v1
kind: Deployment
metadata: { name: frontend }
spec:
  template:
    spec:
      containers:
        - name: server
          image: frontend:v1
          env:
            - name: CART_SERVICE_ADDR
              value: "cartservice:7070"
            - name: CURRENCY_SERVICE_ADDR
              value: "currencyservice:7000"
            - name: PORT
              value: "8080"
---
apiVersion: apps/v1
kind: Deployment
metadata: { name: cartservice }
spec:
  template:
    spec:
      containers:
        - name: server
          image: cartservice:v1
          env:
            - name: REDIS_ADDR
              value: "redis-cart:6379"
---
apiVersion: apps/v1
kind: Deployment
metadata: { name: currencyservice }
spec:
  template:
    spec:
      containers:
        - name: server
          image: currencyservice:v1
---
apiVersion: v1
kind: Service
metadata: { name: cartservice }
spec: { ports: [{ port: 7070 }] }
"""


def test_parses_deployments_with_env():
    wls = parse_k8s_documents(K8S)
    names = {w.name for w in wls}
    assert names == {"frontend", "cartservice", "currencyservice"}
    fe = next(w for w in wls if w.name == "frontend")
    assert fe.env["CART_SERVICE_ADDR"] == "cartservice:7070"
    assert fe.image == "frontend:v1"


def test_rpc_addr_targets_resolves_host_to_workload():
    wls = parse_k8s_documents(K8S)
    targets = rpc_addr_targets(wls)
    assert targets["frontend"]["CART_SERVICE_ADDR"] == "cartservice"
    assert targets["frontend"]["CURRENCY_SERVICE_ADDR"] == "currencyservice"
    assert "PORT" not in targets["frontend"]           # not host:port to a workload
    assert "REDIS_ADDR" not in targets.get("cartservice", {})  # redis-cart is no workload
