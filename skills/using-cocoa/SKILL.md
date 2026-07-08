---
name: using-cocoa
description: "Use when a question is about a codebase's SYSTEM structure — which services talk to which, what breaks if something changes, what touches a database, how a request flows — especially in polyglot or k8s-native repos. Establishes the rule: answer from the COCOA system graph, not by reading source files."
---

# Using COCOA

COCOA derives a precise system graph of a repo — per-service call graphs, cross-service
RPC edges (from protos + call sites + k8s wiring), and datastore access — with every
edge tagged `DERIVED-STATIC` (real static analysis) or `INFERRED` (labeled fallback).

**Announce at start:** "Using cocoa:using-cocoa to answer from the system graph."

## The Rule

For questions about system structure, impact, cross-service flow, or data access:
**query the graph; do not reconstruct the answer by reading source files.** Reading
files gives you an impression; the graph gives you derived facts with provenance.

## Checklist

1. Does `.cocoa/system-graph.json` exist in the project root?
   - No, or the code changed meaningfully since it was built → use
     **cocoa:mapping-a-system** to build/refresh it first.
2. Query it:
   - MCP server available (`cocoa` tools visible): use `build_graph_tool`,
     `service_graph_tool`, `data_access_tool`, `blast_radius_tool`,
     `query_subgraph_tool`.
   - No MCP: use the CLI — `cocoa map -p <root>`, `cocoa blast -p <root>
     --target <t> --kind <k> --json`.
3. For impact questions ("what breaks if…") follow **cocoa:blast-radius**.
4. Every claim you make from the graph follows **cocoa:grounding-claims** —
   provenance cited, `INFERRED` labeled, truncation and skips disclosed.

## Red Flags

| Thought | Reality |
|---|---|
| "I'll just grep for callers" | Grep finds text, not resolved edges. Query the graph. |
| "The graph is probably stale" | Then rebuild it (`cocoa map`) — don't guess instead. |
| "It's a small question" | Small answers from unresolved reads are still guesses. |
| "No graph exists, so I'll read files" | Building one is one command. Build it. |

## When NOT to use

Questions about a single function's internals, style, or logic — read the code.
COCOA is for the system layer: boundaries, edges, impact.
