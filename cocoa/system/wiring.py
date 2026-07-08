"""Static topology sources: k8s manifests (raw / helm-rendered / kustomize) + compose."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

_ADDR = re.compile(r"^([a-z0-9][a-z0-9-]*):\d+$")


class Workload(BaseModel):
    name: str
    image: str | None = None
    env: dict[str, str] = Field(default_factory=dict)


def _workload_from_deployment(doc: dict) -> Workload | None:
    try:
        name = doc["metadata"]["name"]
        containers = doc["spec"]["template"]["spec"]["containers"]
    except (KeyError, TypeError):
        return None
    env: dict[str, str] = {}
    image = None
    for c in containers:
        image = image or c.get("image")
        for e in c.get("env") or []:
            if "name" in e and isinstance(e.get("value"), str):
                env[e["name"]] = e["value"]
    return Workload(name=name, image=image, env=env)


def parse_k8s_documents(text: str) -> list[Workload]:
    out: list[Workload] = []
    for doc in yaml.safe_load_all(text):
        if isinstance(doc, dict) and doc.get("kind") in ("Deployment", "StatefulSet", "DaemonSet"):
            wl = _workload_from_deployment(doc)
            if wl:
                out.append(wl)
    return out


def _render(cmd: list[str], cwd: Path) -> str:
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
        return res.stdout if res.returncode == 0 else ""
    except OSError:
        return ""


def parse_k8s_dir(path: Path) -> list[Workload]:
    path = Path(path)
    workloads: list[Workload] = []
    for f in sorted(path.rglob("*.yaml")) + sorted(path.rglob("*.yml")):
        try:
            workloads.extend(parse_k8s_documents(f.read_text(encoding="utf-8", errors="replace")))
        except yaml.YAMLError:
            continue
    if (path / "Chart.yaml").exists() and shutil.which("helm"):
        workloads.extend(parse_k8s_documents(_render(["helm", "template", "."], path)))
    if (path / "kustomization.yaml").exists() and shutil.which("kubectl"):
        workloads.extend(parse_k8s_documents(_render(["kubectl", "kustomize", "."], path)))
    dedup: dict[str, Workload] = {}
    for w in workloads:
        dedup.setdefault(w.name, w)
    return list(dedup.values())


def parse_compose(path: Path) -> list[Workload]:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8", errors="replace")) or {}
    out: list[Workload] = []
    for name, svc in (doc.get("services") or {}).items():
        raw = svc.get("environment") or {}
        if isinstance(raw, list):
            env = dict(item.split("=", 1) for item in raw if "=" in item)
        else:
            env = {k: str(v) for k, v in raw.items() if v is not None}
        out.append(Workload(name=name, image=svc.get("image"), env=env))
    return out


def rpc_addr_targets(workloads: list[Workload]) -> dict[str, dict[str, str]]:
    """client workload -> {ENV_VAR: target workload} for host:port env values."""
    names = {w.name for w in workloads}
    out: dict[str, dict[str, str]] = {}
    for w in workloads:
        for var, val in w.env.items():
            m = _ADDR.match(val.strip())
            if m and m.group(1) in names:
                out.setdefault(w.name, {})[var] = m.group(1)
    return out
