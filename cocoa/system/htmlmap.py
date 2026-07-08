"""Self-contained SVG system map: services on a circle, provenance-colored edges."""
from __future__ import annotations

import html
import math

from cocoa.system.models import EdgeKind, NodeKind, Provenance, SystemGraph
from cocoa.system.topology import service_rpc_edges

_COLORS = {Provenance.DERIVED_STATIC: "#2563eb", Provenance.INFERRED: "#d97706"}


def render_html(graph: SystemGraph) -> str:
    services = [n for n in graph.nodes if n.kind in (NodeKind.SERVICE, NodeKind.DATASTORE)]
    fn_svc = {n.id: f"svc:{n.service}" for n in graph.nodes
              if n.kind == NodeKind.FUNCTION and n.service}
    links: dict[tuple[str, str], Provenance] = {}
    for t in service_rpc_edges(graph):
        pair = (f"svc:{t.client}", f"svc:{t.server}")
        prev = links.get(pair)
        links[pair] = t.provenance if prev is None else (
            Provenance.INFERRED if Provenance.INFERRED in (prev, t.provenance) else prev)
    for e in graph.edges:
        if e.kind not in (EdgeKind.READS, EdgeKind.WRITES):
            continue
        pair = (fn_svc.get(e.source, ""), e.target)
        if all(pair) and pair[0] != pair[1]:
            prev = links.get(pair)
            links[pair] = e.provenance if prev is None else (
                Provenance.INFERRED if Provenance.INFERRED in (prev, e.provenance) else prev)

    cx, cy, r = 480, 360, 280
    pos = {}
    for i, n in enumerate(services):
        a = 2 * math.pi * i / max(len(services), 1)
        pos[n.id] = (cx + r * math.cos(a), cy + r * math.sin(a))
    parts = ['<svg viewBox="0 0 960 720" font-family="monospace" font-size="12">']
    for (a, b), prov in sorted(links.items()):
        if a in pos and b in pos:
            (x1, y1), (x2, y2) = pos[a], pos[b]
            parts.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
                         f'stroke="{_COLORS[prov]}" stroke-width="1.5">'
                         f'<title>{html.escape(f"{a} → {b} ({prov.value})")}</title></line>')
    for n in services:
        x, y = pos[n.id]
        fill = "#0f172a" if n.kind == NodeKind.SERVICE else "#7c2d12"
        label = html.escape(n.id)
        parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="6" fill="{fill}"/>'
                     f'<text x="{x + 9:.0f}" y="{y + 4:.0f}">{label}</text>')
    parts.append('</svg>')
    legend = (f'<p><span style="color:{_COLORS[Provenance.DERIVED_STATIC]}">■</span> DERIVED-STATIC '
              f'&nbsp; <span style="color:{_COLORS[Provenance.INFERRED]}">■</span> INFERRED</p>')
    return (f"<!doctype html><meta charset='utf-8'><title>cocoa system map</title>"
            f"<h1>System map</h1><p>root: <code>{html.escape(graph.root)}</code></p>"
            f"{legend}{''.join(parts)}")
