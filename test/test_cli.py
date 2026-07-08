import json
from pathlib import Path

from pydantic import ValidationError
from typer.testing import CliRunner

import cocoa.cli as cli
from test.test_blast import _g

runner = CliRunner()


def _prime(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cli, "build_system_graph", lambda root, cache_dir=None: _g())


def test_map_writes_artifacts_and_summarizes(tmp_path: Path, monkeypatch):
    _prime(tmp_path, monkeypatch)
    result = runner.invoke(cli.app, ["map", "-p", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".cocoa" / "system-graph.json").exists()
    assert (tmp_path / ".cocoa" / "SYSTEM_REPORT.md").exists()
    assert "svc" in result.output or "services" in result.output.lower()


def test_blast_reads_persisted_graph(tmp_path: Path, monkeypatch):
    _prime(tmp_path, monkeypatch)
    runner.invoke(cli.app, ["map", "-p", str(tmp_path)])
    result = runner.invoke(cli.app, [
        "blast", "-p", str(tmp_path), "--target", "ds:redis:redis-cart",
        "--kind", "redis-key", "--json",
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["by_service"]["frontend"] >= 1


def test_blast_without_map_gives_actionable_error(tmp_path: Path):
    result = runner.invoke(cli.app, [
        "blast", "-p", str(tmp_path), "--target", "x", "--kind", "function",
    ])
    assert result.exit_code == 1
    assert "cocoa map" in result.output


def test_blast_unknown_kind_exits_cleanly(tmp_path: Path, monkeypatch):
    _prime(tmp_path, monkeypatch)
    runner.invoke(cli.app, ["map", "-p", str(tmp_path)])
    result = runner.invoke(cli.app, [
        "blast", "-p", str(tmp_path), "--target", "x", "--kind", "banana",
    ])
    assert result.exit_code == 1
    assert "unknown blast kind" in (result.output + str(result.stderr or ""))
    assert "Traceback" not in result.output


def test_blast_corrupted_graph_is_not_reported_as_kind_error(tmp_path: Path):
    gp = tmp_path / ".cocoa" / "system-graph.json"
    gp.parent.mkdir(parents=True)
    gp.write_text("{not valid json", encoding="utf-8")
    result = runner.invoke(cli.app, [
        "blast", "-p", str(tmp_path), "--target", "x", "--kind", "function",
    ])
    assert result.exit_code != 0
    assert "unknown blast kind" not in (result.output + str(result.stderr or ""))
    assert isinstance(result.exception, ValidationError)
