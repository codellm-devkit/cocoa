---
name: mapping-a-system
description: "Use when a COCOA system graph needs to be built or refreshed — no .cocoa/system-graph.json exists, the code has changed meaningfully, or coverage looks wrong. Process for running the map and verifying what it actually covered."
---

# Mapping a System

**Announce at start:** "Using cocoa:mapping-a-system to build/refresh the graph."

## Checklist

1. **Build:** `cocoa map -p <project-root>` (or the `build_graph_tool` MCP tool with
   `rebuild=true` when refreshing). First Java analysis downloads a JDK into the
   project cache — expect minutes once per project.
2. **Read the skips — mandatory.** The map output and `.cocoa/SYSTEM_REPORT.md` list
   every service that was NOT analyzed and why (unsupported language, missing
   analyzer binary, analyzer crash with stderr). These skipped services must be
   reported to the user verbatim before answering anything from the graph.
3. **Sanity-check the inventory** against the repo: does the Services section list
   the services you expected, with plausible function counts? A major service
   missing from both the inventory AND the skips means detection failed — stop and
   investigate rather than proceeding on a partial graph silently.
4. **Check topology plausibility:** the report's "Cross-service topology" section
   should show the RPC edges you'd expect. `(INFERRED)` markers are honest
   fallbacks, not errors. An empty topology on a gRPC system usually means protos
   weren't found — check the report and the repo's proto locations.
5. **Artifacts:** `.cocoa/system-graph.json` (queryable), `system-map.html`
   (openable in a browser), `SYSTEM_REPORT.md` (human summary). Never commit
   `.cocoa/` — it is derived output.

## Red Flags

| Thought | Reality |
|---|---|
| "Map succeeded, moving on" | Success with 5 skips is a 50% map. Read the skips. |
| "I'll hand-draw the architecture instead" | The graph is derived; your diagram is vibes. |
| "Go/C# services are missing, oh well" | Say WHY (analyzer availability) — it's in the skips. |
