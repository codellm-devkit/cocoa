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
