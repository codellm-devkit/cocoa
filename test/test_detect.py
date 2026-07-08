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


def test_unknown_language_service_with_dockerfile_is_recorded(tmp_path: Path):
    _mk(tmp_path, "src/rustservice/Cargo.toml", "[package]")
    _mk(tmp_path, "src/rustservice/Dockerfile", "FROM rust")
    _mk(tmp_path, "src/goservice/go.mod", "module g")
    _mk(tmp_path, "docs/readme.md", "# docs")
    d = detect(tmp_path)
    by_name = {s.name: s.language for s in d.services}
    assert by_name["rustservice"] == "unknown"
    assert by_name["goservice"] == "go"
    assert "docs" not in by_name


def test_nested_csproj_detects_csharp(tmp_path: Path):
    _mk(tmp_path, "src/cartservice/src/cartservice.csproj", "<Project/>")
    _mk(tmp_path, "src/cartservice/Dockerfile", "FROM dotnet")
    d = detect(tmp_path)
    by_name = {s.name: s.language for s in d.services}
    assert by_name["cartservice"] == "csharp"


def test_hidden_dirs_excluded_from_all_discovery(tmp_path: Path):
    _mk(tmp_path, ".terraform/modules/x.proto", 'syntax = "proto3";')
    _mk(tmp_path, ".terraform/modules/dep.yaml", "kind: Deployment")
    _mk(tmp_path, "protos/real.proto", 'syntax = "proto3";')
    d = detect(tmp_path)
    assert [Path(p).name for p in d.proto_files] == ["real.proto"]
    assert d.manifest_dirs == []


def test_large_combined_manifest_detected_past_4k(tmp_path: Path):
    pad = "# " + "x" * 5000 + "\n"
    _mk(tmp_path, "k8s/all.yaml", pad + "kind: Deployment\nmetadata: {name: svc}\n")
    d = detect(tmp_path)
    assert any(Path(m).name == "k8s" for m in d.manifest_dirs)
