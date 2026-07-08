"""Run the per-language analysis backends and normalize their output."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from cocoa.system.detect import DetectedService, DetectedSystem
from cocoa.system.facts import (
    ServiceFacts, from_go, from_java, from_python, from_typescript,
)
from cocoa.system.models import Skipped

log = logging.getLogger("cocoa.driver")


class ToolMissingError(Exception):
    pass


def _facts_java(svc: DetectedService, cache_dir: Path) -> ServiceFacts:
    from cldk import CLDK
    from cldk.analysis import AnalysisLevel
    from cldk.analysis.commons.backend_config import CodeAnalyzerConfig

    app = CLDK.java(
        project_path=svc.path,
        analysis_level=AnalysisLevel.call_graph,
        backend=CodeAnalyzerConfig(cache_dir=str(Path(cache_dir) / svc.name)),
    ).get_application_view()
    return from_java(app.model_dump(), svc.name)


def _facts_python(svc: DetectedService, cache_dir: Path) -> ServiceFacts:
    from cldk import CLDK
    from cldk.analysis import AnalysisLevel
    from cldk.analysis.commons.backend_config import PyCodeAnalyzerConfig

    app = CLDK.python(
        project_path=svc.path,
        analysis_level=AnalysisLevel.symbol_table,  # py emits call graph at level 1
        backend=PyCodeAnalyzerConfig(cache_dir=str(Path(cache_dir) / svc.name)),
    ).get_application_view()
    return from_python(app.model_dump(), svc.name)


def _facts_typescript(svc: DetectedService, cache_dir: Path) -> ServiceFacts:
    from cldk import CLDK
    from cldk.analysis import AnalysisLevel
    from cldk.analysis.commons.backend_config import TSCodeAnalyzerConfig

    app = CLDK.typescript(
        project_path=svc.path,
        analysis_level=AnalysisLevel.symbol_table,  # ts emits call graph at level 1
        backend=TSCodeAnalyzerConfig(cache_dir=str(Path(cache_dir) / svc.name)),
    ).get_application_view()
    return from_typescript(app.model_dump(), svc.name)


def _facts_go(svc: DetectedService, cache_dir: Path) -> ServiceFacts:
    binary = os.environ.get("CODEANALYZER_GO_BIN") or shutil.which("codeanalyzer-go")
    if not binary:
        raise ToolMissingError(
            "codeanalyzer-go not found (set CODEANALYZER_GO_BIN or add to PATH)"
        )
    outdir = Path(cache_dir) / svc.name / "go"
    outdir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [binary, "-i", svc.path, "-a", "2", "-o", str(outdir)],
        check=True, capture_output=True, text=True, timeout=1800,
    )
    raw = json.loads((outdir / "analysis.json").read_text(encoding="utf-8"))
    return from_go(raw, svc.name)


_LANG_RUNNERS = {
    "java": _facts_java,
    "python": _facts_python,
    "typescript": _facts_typescript,
    "go": _facts_go,
}

_UNSUPPORTED_REASONS = {
    "csharp": "no analyzer backend available yet (codeanalyzer-dotnet pending)",
    "unknown": "language not recognized",
}


def analyze_service(svc: DetectedService, cache_dir: Path) -> ServiceFacts:
    runner = _LANG_RUNNERS.get(svc.language)
    if runner is None:
        raise ToolMissingError(_UNSUPPORTED_REASONS.get(svc.language, f"unsupported: {svc.language}"))
    return runner(svc, cache_dir)


def analyze_system(
    system: DetectedSystem, cache_dir: Path
) -> tuple[dict[str, ServiceFacts], list[Skipped]]:
    facts: dict[str, ServiceFacts] = {}
    skipped: list[Skipped] = []
    for svc in system.services:
        runner = _LANG_RUNNERS.get(svc.language)
        if runner is None:
            skipped.append(Skipped(
                service=svc.name, language=svc.language,
                reason=_UNSUPPORTED_REASONS.get(svc.language, f"unsupported: {svc.language}"),
            ))
            continue
        try:
            facts[svc.name] = runner(svc, cache_dir)
            log.info("analyzed %s (%s): %d functions",
                     svc.name, svc.language, len(facts[svc.name].functions))
        except Exception as exc:  # never let one service kill the system pass
            detail = (getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or "").strip()
            reason = f"{exc}: {detail[:500]}" if detail else str(exc)
            skipped.append(Skipped(service=svc.name, language=svc.language, reason=reason))
            log.warning("skipped %s (%s): %s", svc.name, svc.language, reason)
    return facts, skipped
