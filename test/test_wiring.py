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


def test_null_containers_keep_workload_name_without_crash():
    wls = parse_k8s_documents(
        "kind: Deployment\nmetadata: {name: broken}\nspec: {template: {spec: {containers: null}}}"
    )
    assert [w.name for w in wls] == ["broken"]
    assert wls[0].env == {}


def test_parse_compose_handles_map_list_and_scalar_env(tmp_path):
    from cocoa.system.wiring import parse_compose
    f = tmp_path / "docker-compose.yml"
    f.write_text(
        "services:\n"
        "  a: {environment: {X: '1'}}\n"
        "  b:\n    environment:\n      - Y=2\n"
        "  c: {environment: oops}\n"
        "  d: 42\n"
    )
    wls = {w.name: w.env for w in parse_compose(f)}
    assert wls == {"a": {"X": "1"}, "b": {"Y": "2"}, "c": {}}


def test_parse_compose_malformed_yaml_returns_empty(tmp_path):
    from cocoa.system.wiring import parse_compose
    f = tmp_path / "docker-compose.yml"
    f.write_text("services: [unclosed")
    assert parse_compose(f) == []


def test_rendered_helm_output_wins_dedup_over_raw_templates(tmp_path, monkeypatch):
    import cocoa.system.wiring as wiring
    (tmp_path / "Chart.yaml").write_text("name: chart")
    tpl = tmp_path / "templates"
    tpl.mkdir()
    (tpl / "frontend.yaml").write_text(
        "kind: Deployment\nmetadata: {name: frontend}\n"
        "spec: {template: {spec: {containers: [{name: s, env: [{name: CART_SERVICE_ADDR, value: '{{ .Values.addr }}'}]}]}}}"
    )
    monkeypatch.setattr(wiring.shutil, "which", lambda _: "/usr/bin/fake")
    monkeypatch.setattr(wiring, "_render", lambda cmd, cwd: (
        "kind: Deployment\nmetadata: {name: frontend}\n"
        "spec: {template: {spec: {containers: [{name: s, env: [{name: CART_SERVICE_ADDR, value: 'cartservice:7070'}]}]}}}"
    ))
    wls = wiring.parse_k8s_dir(tmp_path)
    assert len(wls) == 1
    assert wls[0].env["CART_SERVICE_ADDR"] == "cartservice:7070"
