---
name: blast-radius
description: "Use when asked what breaks, what's affected, or what depends on something — a proto field, an RPC, a function, a table, or a Redis key — in a repo with a COCOA system graph. How to phrase the query, interpret results, and report impact."
---

# Blast Radius

**Announce at start:** "Using cocoa:blast-radius to compute impact from the graph."

## Phrasing the query

`cocoa blast -p <root> --target <target> --kind <kind> --json` or the
`blast_radius_tool` MCP tool. Kinds and target forms:

| kind | target form (unique suffix is enough) |
|---|---|
| `proto-field` | `hipstershop.Money.units` |
| `rpc` | `rpc:hipstershop.CartService/GetCart` or `CartService/GetCart` |
| `function` | any `fn:` node id or unique signature suffix |
| `table` | `tbl:orders` or `orders` |
| `redis-key` | `ds:redis:redis-cart`, `key:<literal>`, or a unique suffix |

An ambiguous suffix resolves to nothing (empty result, not a guess) — qualify it more.

## Interpreting results

- `impacted[*].depth` — hops along the STRONGEST available path (an RPC boundary
  counts as one hop). `provenance` is that path's compounded provenance.
- Cross-service propagation is automatic: handlers hop to their RPC's clients.
- Via the MCP tool, `by_service` is the complete per-service tally even when the
  detail list is truncated (`truncated=true` → cite `total_impacted`); the CLI
  `--json` output is never truncated.
- Empty result for a real node usually means nothing calls it (check
  `DECLARED-UNUSED` on the RPC) — or coverage gaps; check the graph's skips.

## Reporting impact

Group by service; per item cite `file:line` when present and the provenance tag.
Lead with the derived (`DERIVED-STATIC`) impact; list inferred impact separately and
labeled. Close with coverage caveats (skipped services, truncation) per
**cocoa:grounding-claims** — that skill's HARD-GATE applies to every claim here.

## Red Flags

| Thought | Reality |
|---|---|
| "I'll pad the result with likely-affected files" | The graph IS the result. Padding is guessing. |
| "Depth 1 means most important" | Depth is path length, not importance. |
| "Empty blast = safe to change" | Empty = no derived evidence. Report blind spots. |
