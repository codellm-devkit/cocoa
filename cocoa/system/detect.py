"""Walk a repo: find services (per-dir language), protos, manifest dirs, compose files."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

_SKIP_DIRS = {".git", "node_modules", ".venv", "vendor", "dist", "build", ".cocoa", ".codeanalyzer"}


class DetectedService(BaseModel):
    name: str
    path: str
    language: str


class DetectedSystem(BaseModel):
    root: str
    services: list[DetectedService] = Field(default_factory=list)
    proto_files: list[str] = Field(default_factory=list)
    manifest_dirs: list[str] = Field(default_factory=list)
    compose_files: list[str] = Field(default_factory=list)


def _language_of(d: Path) -> str | None:
    if (d / "go.mod").exists():
        return "go"
    if (d / "pom.xml").exists() or (d / "build.gradle").exists() or (d / "build.gradle.kts").exists():
        return "java"
    if any(d.glob("*.csproj")):
        return "csharp"
    if (d / "package.json").exists():
        return "typescript"
    if (d / "pyproject.toml").exists() or (d / "requirements.txt").exists():
        return "python"
    if any(d.glob("*.py")):
        return "python"
    if (
        (d / "Dockerfile").exists()
        or (d / "Cargo.toml").exists()
        or (d / "Gemfile").exists()
        or (d / "composer.json").exists()
        or any(d.glob("*.sln"))
    ):
        return "unknown"
    return None


def _excluded(p: Path, root: Path) -> bool:
    rel_parts = p.relative_to(root).parts
    return any(part in _SKIP_DIRS or part.startswith(".") for part in rel_parts)


def detect(root: Path) -> DetectedSystem:
    root = Path(root).resolve()
    out = DetectedSystem(root=str(root))

    candidates: list[Path] = []
    for base in (root, root / "src"):
        if base.is_dir():
            candidates.extend(
                p for p in sorted(base.iterdir())
                if p.is_dir() and p.name not in _SKIP_DIRS and not p.name.startswith(".")
            )
    seen: set[str] = set()
    for d in candidates:
        lang = _language_of(d)
        if lang and d.name not in seen:
            seen.add(d.name)
            out.services.append(DetectedService(name=d.name, path=str(d), language=lang))
    if not out.services:
        lang = _language_of(root)
        if lang:
            out.services.append(DetectedService(name=root.name, path=str(root), language=lang))

    for p in sorted(root.rglob("*.proto")):
        if not _excluded(p, root):
            out.proto_files.append(str(p))

    manifest_dirs: set[str] = set()
    for p in sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml")):
        if _excluded(p, root):
            continue
        if p.name in ("docker-compose.yml", "docker-compose.yaml", "compose.yaml"):
            out.compose_files.append(str(p))
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "kind: Deployment" in text or "kind: StatefulSet" in text or "kind: DaemonSet" in text:
            manifest_dirs.add(str(p.parent))
    out.manifest_dirs = sorted(manifest_dirs)
    return out
