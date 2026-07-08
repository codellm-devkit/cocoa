"""The Online Boutique flagship demo: fetch -> map -> blast -> headline."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from cocoa.system.blast import blast_radius
from cocoa.system.build import ARTIFACT_DIR, build_system_graph, write_artifacts

DEMO_REPO = "https://github.com/GoogleCloudPlatform/microservices-demo"
DEMO_TAG = "v0.10.5"
DEMO_TARGET = "fld:hipstershop.Money.units"
DEMO_KIND = "proto-field"


def _fetch(workdir: Path) -> Path:
    dest = workdir / f"microservices-demo-{DEMO_TAG}"
    if not dest.exists():
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", DEMO_TAG, DEMO_REPO, str(dest)],
            check=True, capture_output=True, text=True, timeout=600,
        )
    return dest


def _naive_tokens(root: Path) -> int:
    """Rough estimate: chars/4 over every source file an agent would have to read."""
    exts = {".go", ".py", ".java", ".js", ".ts", ".cs", ".proto"}
    total = 0
    for p in root.rglob("*"):
        if p.suffix in exts and p.is_file() and "node_modules" not in p.parts:
            try:
                total += len(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    return total // 4


def run_demo(workdir: Path | None = None) -> dict:
    workdir = Path(workdir) if workdir else Path.home() / ".cocoa" / "demo"
    workdir.mkdir(parents=True, exist_ok=True)
    repo = _fetch(workdir)
    graph = build_system_graph(repo)
    write_artifacts(graph, repo / ARTIFACT_DIR)
    result = blast_radius(graph, DEMO_TARGET, DEMO_KIND)
    return {
        "graph": graph,
        "blast": result,
        "naive_tokens": _naive_tokens(repo),
        "cocoa_tokens": len(result.model_dump_json()) // 4,
    }
