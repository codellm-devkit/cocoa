---
description: Compute provenance-tagged blast radius for a target (proto field, rpc, function, table, or redis key)
---

Compute the blast radius for the target in $ARGUMENTS.

1. Invoke the cocoa:blast-radius skill and follow it exactly — including its target
   phrasing table and reporting format.
2. Parse $ARGUMENTS as `<target> [kind]`. If kind is omitted, infer by PREFIX
   first: `fld:` → proto-field · `rpc:` (or a `Service/Rpc` slash form) → rpc ·
   `fn:` → function · `tbl:` → table · `ds:redis:`/`key:` → redis-key. For
   UNPREFIXED targets the shape is ambiguous (function signatures and proto
   fields both contain dots) — ask the user for the kind, or state your best
   guess and, if the result comes back empty, retry the other plausible kind
   before reporting "no impact". Always say which kind you used.
3. Run `cocoa blast -p . --target <target> --kind <kind> --json` (or the
   blast_radius_tool MCP tool) — if no graph exists, run /cocoa:map first.
4. Report per the skill: grouped by service, file:line, provenance labels, coverage
   caveats. The cocoa:grounding-claims HARD-GATE applies.
