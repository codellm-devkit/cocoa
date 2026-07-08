import shutil

import pytest

from cocoa.system.demo import DEMO_REPO, DEMO_TAG, run_demo


def test_demo_constants_pin_the_fixture():
    assert DEMO_REPO == "https://github.com/GoogleCloudPlatform/microservices-demo"
    assert DEMO_TAG == "v0.10.5"


@pytest.mark.e2e
def test_online_boutique_demo_end_to_end(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git required")
    out = run_demo(workdir=tmp_path)
    g = out["graph"]
    langs = {n.attrs.get("language") for n in g.nodes if n.kind.value == "service"}
    assert {"go", "python", "java", "typescript"} <= langs
    # cross-service RPC edges derived across at least 3 services
    from cocoa.system.models import EdgeKind
    rpc_edges = [e for e in g.edges if e.kind == EdgeKind.RPC_CALLS]
    assert len(rpc_edges) >= 3
    # blast radius on the Money field reaches multiple services
    assert len(out["blast"].by_service) >= 2
    assert out["naive_tokens"] > out["cocoa_tokens"] * 10
    # C# cartservice is recorded, never silently dropped
    assert any(s.language == "csharp" for s in g.skipped)
