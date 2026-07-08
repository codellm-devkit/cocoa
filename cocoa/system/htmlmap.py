"""Self-contained SVG system map: services on a circle, provenance-colored edges."""
from __future__ import annotations

import html
import math

from cocoa.system.models import EdgeKind, NodeKind, Provenance, SystemGraph

_COLORS = {Provenance.DERIVED_STATIC: "#2563eb", Provenance.INFERRED: "#d97706"}


def render_html(graph: SystemGraph) -> str:
    services = [n for n in graph.nodes if n.kind in (NodeKind.SERVICE, NodeKind.DATASTORE)]
    hosts = {e.target: e.source for e in graph.edges if e.kind == EdgeKind.HOSTS}
    fn_svc = {n.id: f"svc:{n.service}" for n in graph.nodes
              if n.kind == NodeKind.FUNCTION and n.service}
    handler_svc: dict[str, tuple[str, Provenance]] = {
        e.source: (fn_svc.get(e.target, ""), e.provenance)
        for e in graph.edges if e.kind == EdgeKind.HANDLES}
    links: dict[tuple[str, str], Provenance] = {}
    for e in graph.edges:
        prov = e.provenance
        if e.kind == EdgeKind.RPC_CALLS:
            host = hosts.get(e.target, "")
            if not host:
                host, h_prov = handler_svc.get(e.target, ("", None))
                if host and Provenance.INFERRED in (prov, h_prov):
                    prov = Provenance.INFERRED  # compound across the fallback hop
            pair = (fn_svc.get(e.source, ""), host)
        elif e.kind in (EdgeKind.READS, EdgeKind.WRITES):
            pair = (fn_svc.get(e.source, ""), e.target)
        else:
            continue
        if all(pair) and pair[0] != pair[1]:
            prev = links.get(pair)
            links[pair] = prov if prev is None else (
                Provenance.INFERRED if Provenance.INFERRED in (prev, prov) else prev)

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
