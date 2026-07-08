import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from cocoa.system.build import write_artifacts
from test.test_blast import _g

EXPECTED_TOOLS = {
    "build_graph_tool", "blast_radius_tool", "service_graph_tool",
    "data_access_tool", "query_subgraph_tool",
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    write_artifacts(_g(), tmp_path / ".cocoa")   # pre-built graph: no analyzers needed
    return tmp_path


@pytest.fixture
def params(project: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "cocoa.cli", "serve", "-p", str(project)],
    )


async def test_lists_exactly_the_system_tools(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == EXPECTED_TOOLS


async def test_blast_radius_tool_returns_cross_service_impact(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("blast_radius_tool", {
                "target": "ds:redis:redis-cart", "kind": "redis-key",
            })
            payload = json.loads(res.content[0].text)
            assert payload["by_service"]["frontend"] >= 1


async def test_service_graph_uses_handles_fallback(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("service_graph_tool", {})
            payload = json.loads(res.content[0].text)
            assert payload["rpc_edges"] == [{
                "client": "frontend", "server": "cartservice",
                "rpc": "rpc:hipstershop.CartService/GetCart",
                "provenance": "DERIVED-STATIC",
            }]
            assert payload["truncated"] is False


async def test_data_access_rows_and_totals(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("data_access_tool", {})
            payload = json.loads(res.content[0].text)
            assert payload["total_access"] == 1
            assert payload["access"][0]["target"] == "ds:redis:redis-cart"


async def test_query_subgraph_reports_truncation(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("query_subgraph_tool", {"node_kind": "function", "limit": 1})
            payload = json.loads(res.content[0].text)
            assert len(payload["nodes"]) == 1
            assert payload["total_nodes"] == 4
            assert payload["truncated"] is True
