from cocoa.system.htmlmap import render_html
from cocoa.system.models import Skipped
from cocoa.system.report import render_report
from test.test_blast import _g  # reuse the hand-built graph


def test_report_covers_services_topology_and_skips():
    g = _g()
    g.skipped.append(Skipped(
        service="cartservice-csharp", language="csharp", reason="codeanalyzer-dotnet pending"))
    md = render_report(g)
    assert "# System Report" in md
    assert "frontend" in md and "cartservice" in md
    assert "frontend → cartservice" in md            # topology line
    assert "DECLARED-UNUSED" in md or "None detected" in md
    assert "codeanalyzer-dotnet pending" in md       # skips are never silent


def test_html_is_self_contained():
    html = render_html(_g())
    assert "<svg" in html and "svc:frontend" in html
    for banned in ("http://", "https://cdn", "<script src"):
        assert banned not in html


def test_services_inventory_renders_names_and_counts():
    md = render_report(_g())
    assert "- **frontend** (?) — 2 functions" in md
    assert "- **cartservice** (?) — 2 functions" in md
    assert "**None**" not in md


def test_html_topology_agrees_with_report():
    html = render_html(_g())
    assert html.count("<line") == 2  # frontend→cartservice RPC + cartservice→redis READS
    assert "svc:frontend → svc:cartservice" in html


def test_data_access_truncation_is_labeled():
    from cocoa.system.models import Edge, EdgeKind, Node, NodeKind, Provenance, SystemGraph
    nodes = [Node(id="svc:s", kind=NodeKind.SERVICE, service="s"),
             Node(id="tbl:t", kind=NodeKind.TABLE)]
    nodes += [Node(id=f"fn:s/f{i}", kind=NodeKind.FUNCTION, service="s") for i in range(205)]
    edges = [Edge(source=f"fn:s/f{i}", target="tbl:t", kind=EdgeKind.READS,
                  provenance=Provenance.DERIVED_STATIC) for i in range(205)]
    md = render_report(SystemGraph(root="/x", nodes=nodes, edges=edges))
    assert "showing first 200 of 205" in md
