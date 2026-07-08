---
description: Compute provenance-tagged blast radius for a target (proto field, rpc, function, table, or redis key)
---

Compute the blast radius for the target in $ARGUMENTS.

1. Invoke the cocoa:blast-radius skill and follow it exactly — including its target
   phrasing table and reporting format.
2. Parse $ARGUMENTS as `<target> [kind]`; if kind is omitted, infer it from the
   target's shape (dots + field → proto-field; `rpc:`/Service-slash → rpc; `tbl:` →
   table; `ds:redis`/`key:` → redis-key; else function) and SAY which kind you chose.
3. Run `cocoa blast -p . --target <target> --kind <kind> --json` (or the
   blast_radius_tool MCP tool) — if no graph exists, run /cocoa:map first.
4. Report per the skill: grouped by service, file:line, provenance labels, coverage
   caveats. The cocoa:grounding-claims HARD-GATE applies.
