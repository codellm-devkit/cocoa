from pathlib import Path

import pytest

from cocoa.system import driver
from cocoa.system.detect import DetectedService, DetectedSystem
from cocoa.system.facts import ServiceFacts


def _sys(tmp_path, *svcs):
    return DetectedSystem(root=str(tmp_path), services=list(svcs))


def test_analyze_system_dispatches_and_records_skips(tmp_path: Path, monkeypatch):
    calls = []

    def fake(svc, cache_dir):
        calls.append(svc.name)
        return ServiceFacts(service=svc.name, language=svc.language)

    monkeypatch.setattr(driver, "_LANG_RUNNERS", {"go": fake, "python": fake})
    system = _sys(
        tmp_path,
        DetectedService(name="frontend", path=str(tmp_path), language="go"),
        DetectedService(name="emailservice", path=str(tmp_path), language="python"),
        DetectedService(name="cartservice", path=str(tmp_path), language="csharp"),
    )
    facts, skipped = driver.analyze_system(system, tmp_path / "cache")
    assert set(facts) == {"frontend", "emailservice"}
    assert calls == ["frontend", "emailservice"]
    assert skipped[0].service == "cartservice"
    assert "codeanalyzer-dotnet" in skipped[0].reason


def test_analyzer_crash_becomes_skip_not_crash(tmp_path: Path, monkeypatch):
    def boom(svc, cache_dir):
        raise RuntimeError("jar exploded")

    monkeypatch.setattr(driver, "_LANG_RUNNERS", {"java": boom})
    system = _sys(tmp_path, DetectedService(name="adservice", path=str(tmp_path), language="java"))
    facts, skipped = driver.analyze_system(system, tmp_path / "cache")
    assert facts == {}
    assert skipped[0].reason == "jar exploded"


def test_go_runner_requires_binary(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CODEANALYZER_GO_BIN", raising=False)
    monkeypatch.setattr(driver.shutil, "which", lambda _: None)
    svc = DetectedService(name="frontend", path=str(tmp_path), language="go")
    with pytest.raises(driver.ToolMissingError):
        driver._facts_go(svc, tmp_path / "cache")


def test_go_subprocess_failure_reason_includes_stderr(tmp_path: Path, monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        raise sp.CalledProcessError(2, cmd, output="", stderr="go build: package broken/x not found")

    monkeypatch.setenv("CODEANALYZER_GO_BIN", "/usr/bin/fake-cango")
    monkeypatch.setattr(driver.subprocess, "run", fake_run)
    system = _sys(tmp_path, DetectedService(name="frontend", path=str(tmp_path), language="go"))
    facts, skipped = driver.analyze_system(system, tmp_path / "cache")
    assert facts == {}
    assert "package broken/x not found" in skipped[0].reason


@pytest.mark.integration
def test_real_python_analysis_yields_functions(tmp_path: Path):
    proj = tmp_path / "miniapp"
    proj.mkdir()
    (proj / "app.py").write_text("def greet(name):\n    return helper(name)\n\ndef helper(n):\n    return n\n")
    svc = DetectedService(name="miniapp", path=str(proj), language="python")
    facts = driver.analyze_service(svc, tmp_path / "cache")
    assert any("greet" in f.name for f in facts.functions.values())
