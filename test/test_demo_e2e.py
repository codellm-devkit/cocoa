import shutil
from pathlib import Path

import pytest

from cocoa.system.demo import DEMO_REPO, DEMO_TAG, run_demo


def test_demo_constants_pin_the_fixture():
    assert DEMO_REPO == "https://github.com/GoogleCloudPlatform/microservices-demo"
    assert DEMO_TAG == "v0.10.5"


def test_fetch_cleans_up_partial_clone(tmp_path, monkeypatch):
    import subprocess as sp
    from cocoa.system import demo

    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).mkdir(parents=True)          # git created the dir...
        raise sp.TimeoutExpired(cmd, 600)          # ...then died

    monkeypatch.setattr(demo.subprocess, "run", fake_run)
    with pytest.raises(sp.TimeoutExpired):
        demo._fetch(tmp_path)
    assert list(tmp_path.iterdir()) == []          # no partial dir, no dest


def test_naive_tokens_ignores_artifacts_and_hidden_dirs(tmp_path):
    from cocoa.system.demo import _naive_tokens
    (tmp_path / "app.py").write_text("x = 1\n" * 100)
    (tmp_path / ".cocoa").mkdir()
    (tmp_path / ".cocoa" / "cache.py").write_text("y = 2\n" * 10000)
    (tmp_path / "node_modules" / "dep").mkdir(parents=True)
    (tmp_path / "node_modules" / "dep" / "index.js").write_text("z\n" * 10000)
    assert _naive_tokens(tmp_path) == len(("x = 1\n" * 100)) // 4


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
