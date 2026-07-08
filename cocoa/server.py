"""FastMCP assembly: lifespan carries lazily loaded/built system graph."""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from fastmcp import FastMCP

from cocoa.system.build import ARTIFACT_DIR, build_system_graph, write_artifacts
from cocoa.system.models import SystemGraph
from cocoa.tools import iter_tools


@dataclass
class SystemState:
    project_path: Path
    _graph: SystemGraph | None = field(default=None, init=False)

    def artifact_paths(self) -> dict[str, Path]:
        d = Path(self.project_path) / ARTIFACT_DIR
        return {"graph": d / "system-graph.json", "report": d / "SYSTEM_REPORT.md",
                "html": d / "system-map.html"}

    def graph(self, rebuild: bool = False) -> SystemGraph:
        if self._graph is not None and not rebuild:
            return self._graph
        gp = self.artifact_paths()["graph"]
        if gp.exists() and not rebuild:
            self._graph = SystemGraph.load(gp)
        else:
            self._graph = build_system_graph(self.project_path)
            write_artifacts(self._graph, Path(self.project_path) / ARTIFACT_DIR)
        return self._graph


def create_server(project_path: Path) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server: FastMCP):
        yield SystemState(project_path=Path(project_path))

    mcp = FastMCP(name="cocoa", lifespan=lifespan,
                  instructions="Precise static system graphs: build once, query cheap.")
    for tool in iter_tools():
        mcp.add_tool(tool)
    return mcp
