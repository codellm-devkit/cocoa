"""Structural validation for plugin content: manifests, skills, commands."""
import json
from pathlib import Path

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


SKILLS = ["using-cocoa", "grounding-claims", "mapping-a-system", "blast-radius"]


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
