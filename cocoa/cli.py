"""COCOA CLI: map | blast | serve | demo."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from cocoa.system.blast import blast_radius
from cocoa.system.build import ARTIFACT_DIR, build_system_graph, write_artifacts
from cocoa.system.models import SystemGraph

app = typer.Typer(
    name="cocoa",
    help="COCOA (Code Context Agent): precise static system graphs for AI agents.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)

_ProjectOpt = Annotated[Path, typer.Option("-p", "--project-path", help="Repo to analyze")]


def _graph_path(project: Path) -> Path:
    return Path(project) / ARTIFACT_DIR / "system-graph.json"


@app.command()
def map(
    project_path: _ProjectOpt,
    cache_dir: Annotated[Optional[Path], typer.Option(help="Analyzer cache dir")] = None,
):
    """Build the system graph and write .cocoa/ artifacts."""
    graph = build_system_graph(project_path, cache_dir=cache_dir)
    paths = write_artifacts(graph, project_path / ARTIFACT_DIR)
    services = sorted({n.service for n in graph.nodes if n.service})
    typer.echo(f"services analyzed: {', '.join(services) or '(none)'}")
    typer.echo(f"nodes: {len(graph.nodes)}  edges: {len(graph.edges)}  "
               f"skipped: {len(graph.skipped)}")
    for s in graph.skipped:
        typer.echo(f"  skipped {s.service} ({s.language}): {s.reason}")
    for name, p in paths.items():
        typer.echo(f"{name}: {p}")


@app.command()
def blast(
    project_path: _ProjectOpt,
    target: Annotated[str, typer.Option(help="Node id or unique suffix")],
    kind: Annotated[str, typer.Option(help="proto-field|rpc|function|table|redis-key")],
    depth: Annotated[int, typer.Option()] = 25,
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    """Blast radius: what breaks if the target changes."""
    gp = _graph_path(project_path)
    if not gp.exists():
        typer.echo("no system graph found — run `cocoa map -p <path>` first", err=True)
        raise typer.Exit(code=1)
    graph = SystemGraph.load(gp)
    try:
        result = blast_radius(graph, target, kind, max_depth=depth)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)
    if json_output:
        typer.echo(result.model_dump_json(indent=1))
        return
    typer.echo(f"target: {result.target} ({result.kind})  seeds: {len(result.seeds)}")
    for svc, count in sorted(result.by_service.items()):
        typer.echo(f"  {svc}: {count} impacted")
    for item in result.impacted:
        where = f"{item.file}:{item.line}" if item.file else ""
        typer.echo(f"  [{item.provenance.value}] {item.node_id} {where}")


@app.command()
def serve(project_path: _ProjectOpt):
    """Start the COCOA MCP server for a project."""
    from cocoa.server import create_server

    create_server(project_path).run()


@app.command()
def demo(
    workdir: Annotated[Optional[Path], typer.Option(help="Where to clone the fixture")] = None,
):
    """Run the Online Boutique flagship demo (fetch -> map -> blast -> headline)."""
    from cocoa.system.demo import DEMO_KIND, DEMO_TARGET, run_demo

    out = run_demo(workdir=workdir)
    graph, result = out["graph"], out["blast"]
    typer.echo(f"system graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    for s in graph.skipped:
        typer.echo(f"  skipped {s.service} ({s.language}): {s.reason}")
    typer.echo(f"blast({DEMO_TARGET}, {DEMO_KIND}):")
    for svc, n in sorted(result.by_service.items()):
        typer.echo(f"  {svc}: {n} impacted call sites/functions")
    ratio = out["naive_tokens"] / max(out["cocoa_tokens"], 1)
    typer.echo(f"tokens (est.): naive read-everything ≈ {out['naive_tokens']:,} "
               f"vs cocoa answer ≈ {out['cocoa_tokens']:,}  (~{ratio:.0f}x)")


if __name__ == "__main__":
    app()
