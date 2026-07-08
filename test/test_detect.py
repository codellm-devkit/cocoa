from pathlib import Path

from cocoa.system.detect import detect


def _mk(tmp: Path, rel: str, content: str = "") -> None:
    p = tmp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def test_detects_polyglot_services_protos_and_manifests(tmp_path: Path):
    _mk(tmp_path, "src/frontend/go.mod", "module frontend")
    _mk(tmp_path, "src/cartservice/cartservice.csproj", "<Project/>")
    _mk(tmp_path, "src/currencyservice/package.json", "{}")
    _mk(tmp_path, "src/emailservice/requirements.txt", "grpcio")
    _mk(tmp_path, "src/adservice/build.gradle", "")
    _mk(tmp_path, "protos/demo.proto", 'syntax = "proto3";')
    _mk(tmp_path, "kubernetes-manifests/frontend.yaml", "kind: Deployment")
    _mk(tmp_path, "node_modules/junk/package.json", "{}")

    d = detect(tmp_path)
    by_name = {s.name: s.language for s in d.services}
    assert by_name == {
        "frontend": "go",
        "cartservice": "csharp",
        "currencyservice": "typescript",
        "emailservice": "python",
        "adservice": "java",
    }
    assert [Path(p).name for p in d.proto_files] == ["demo.proto"]
    assert any(Path(m).name == "kubernetes-manifests" for m in d.manifest_dirs)


def test_single_service_repo_detects_root_itself(tmp_path: Path):
    _mk(tmp_path, "pyproject.toml", "[project]")
    _mk(tmp_path, "app.py", "x = 1")
    d = detect(tmp_path)
    assert len(d.services) == 1
    assert d.services[0].language == "python"
    assert d.services[0].name == tmp_path.name
