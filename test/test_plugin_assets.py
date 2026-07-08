"""Structural validation for plugin content: manifests, skills, commands."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def _frontmatter(path: Path) -> dict:
    """Parse ----fenced YAML frontmatter at the top of a markdown file."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} missing frontmatter fence"
    body = text.split("---\n", 2)
    assert len(body) >= 3, f"{path} frontmatter not closed"
    return yaml.safe_load(body[1])


def test_plugin_manifest_is_valid():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "cocoa"
    assert manifest["license"] == "MIT"
    for key in ("description", "version", "author", "homepage", "repository", "keywords"):
        assert key in manifest, f"plugin.json missing {key}"


def test_marketplace_manifest_lists_cocoa():
    mp = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert mp["name"] == "cocoa"
    assert mp["plugins"][0]["name"] == "cocoa"
    assert mp["plugins"][0]["source"] == "."


def test_skill_frontmatter_follows_superpowers_conventions():
    for name in ("using-cocoa", "grounding-claims"):
        fm = _frontmatter(ROOT / "skills" / name / "SKILL.md")
        assert fm["name"] == name
        assert fm["description"].startswith("Use when"), f"{name}: description must start 'Use when'"


def test_grounding_claims_carries_the_hard_gate():
    text = (ROOT / "skills" / "grounding-claims" / "SKILL.md").read_text()
    assert "<HARD-GATE>" in text
    assert "Never present an `INFERRED` edge as fact." in text
    assert "DERIVED-STATIC" in text


def test_using_cocoa_names_the_other_skills():
    text = (ROOT / "skills" / "using-cocoa" / "SKILL.md").read_text()
    for ref in ("cocoa:mapping-a-system", "cocoa:blast-radius", "cocoa:grounding-claims"):
        assert ref in text


def test_skills_only_name_real_mcp_tools():
    """Any *_tool token mentioned in ANY skill must be a real registered tool."""
    import re
    real = {"build_graph_tool", "blast_radius_tool", "service_graph_tool",
            "data_access_tool", "query_subgraph_tool"}
    for skill_dir in (ROOT / "skills").iterdir():
        text = (skill_dir / "SKILL.md").read_text()
        named = set(re.findall(r"\b([a-z_]+_tool)\b", text))
        assert named <= real, f"{skill_dir.name} names unknown tools: {named - real}"
        assert re.search(r"`build_graph`", text) is None, f"{skill_dir.name} names bare build_graph"
    # the entry skill must still name all five
    entry = (ROOT / "skills" / "using-cocoa" / "SKILL.md").read_text()
    assert real <= set(re.findall(r"\b([a-z_]+_tool)\b", entry))


def test_process_skills_frontmatter():
    for name in ("mapping-a-system", "blast-radius"):
        fm = _frontmatter(ROOT / "skills" / name / "SKILL.md")
        assert fm["name"] == name
        assert fm["description"].startswith("Use when")


def test_blast_radius_documents_kinds_and_provenance():
    text = (ROOT / "skills" / "blast-radius" / "SKILL.md").read_text()
    for kind in ("proto-field", "rpc", "function", "table", "redis-key"):
        assert f"`{kind}`" in text
    assert "cocoa:grounding-claims" in text


def test_mapping_skill_mandates_skip_review():
    text = (ROOT / "skills" / "mapping-a-system" / "SKILL.md").read_text()
    assert "skipped" in text.lower()
    assert "SYSTEM_REPORT.md" in text


def test_commands_have_descriptions_and_invoke_skills():
    expectations = {
        "map.md": "cocoa:mapping-a-system",
        "blast.md": "cocoa:blast-radius",
        "demo.md": "cocoa:grounding-claims",
    }
    for fname, skill_ref in expectations.items():
        path = ROOT / "commands" / fname
        fm = _frontmatter(path)
        assert fm.get("description"), f"{fname} missing description"
        assert skill_ref in path.read_text(), f"{fname} must reference {skill_ref}"


def test_mcp_config_launches_cocoa_serve():
    cfg = json.loads((ROOT / ".mcp.json").read_text())
    server = cfg["mcpServers"]["cocoa"]
    assert server["command"] == "uvx"
    assert server["args"][-3:] == ["serve", "-p", "."]
    assert "git+https://github.com/codellm-devkit/cocoa" in " ".join(server["args"])


def test_blast_command_infers_by_prefix_and_handles_ambiguity():
    text = (ROOT / "commands" / "blast.md").read_text()
    for prefix in ("`fld:`", "`fn:`", "`tbl:`", "`key:`"):
        assert prefix in text
    assert "ambiguous" in text and "retry" in text


def test_demo_command_distinguishes_go_and_csharp_skips():
    text = (ROOT / "commands" / "demo.md").read_text()
    assert "CODEANALYZER_GO_BIN" in text
    assert "codeanalyzer-dotnet" in text


@pytest.mark.docker
def test_docker_smoke_builds_and_maps():
    if not shutil.which("docker"):
        pytest.skip("docker not available")
    res = subprocess.run(
        ["bash", str(ROOT / "scripts" / "docker-smoke.sh")],
        capture_output=True, text=True, timeout=1800,
    )
    assert res.returncode == 0, f"smoke failed:\n{res.stdout}\n{res.stderr}"
