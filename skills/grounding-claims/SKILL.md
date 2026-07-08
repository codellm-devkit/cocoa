---
name: grounding-claims
description: "Use when reporting ANY fact derived from a COCOA system graph — edges, impact sets, topology, data access. Enforces provenance discipline: label INFERRED, disclose skips and truncation, never overstate."
---

# Grounding Claims

COCOA's value is that its edges are derived, not guessed. That value survives only if
you report them honestly.

<HARD-GATE>
Never present an `INFERRED` edge as fact. Every edge-level claim states its
provenance. If any hop in a path is `INFERRED`, the conclusion is inferred —
say so. Do not answer system-impact questions from raw file reading when a
system graph exists or can be built.
</HARD-GATE>

## Provenance vocabulary (and annotations)

- `DERIVED-STATIC` — produced by a real analyzer, the proto/wiring stitcher, or a
  datastore extractor. Report as fact.
- `INFERRED` — name-plus-wiring fallback or ambiguous evidence (edges carry
  `ambiguous=true` when applicable). Report as "likely/inferred", never as fact.
- `DECLARED-UNUSED` — a node *annotation* (not an edge provenance): an RPC declared
  in a proto with no derived caller. A *candidate* dead RPC, not proof.

## Disclosure duties (all mandatory)

1. **Skips:** if the graph's `skipped` list is non-empty (also listed in
   `.cocoa/SYSTEM_REPORT.md`), your answer covers only the analyzed services — name
   the skipped ones and the reason (e.g. "cartservice (C#) not analyzed — analyzer
   pending"). An impact answer that ignores skips is wrong.
2. **Truncation:** MCP tools return `truncated` + `total_*` fields. If `truncated` is
   true, state the total and that you're showing a subset.
3. **Depth semantics:** blast-radius `depth` is the strongest path's depth; the
   provenance shown is that path's compounded provenance.
4. **Absence ≠ safety:** "no edge in the graph" means "not derivable statically" —
   for dynamic dispatch, reflection, or skipped services, say "no derived evidence",
   not "unaffected".

## Red Flags

| Thought | Reality |
|---|---|
| "The INFERRED label clutters the answer" | The label IS the answer's integrity. Keep it. |
| "Skips are noise, the user asked about X" | Undisclosed skips silently narrow the answer. Disclose. |
| "truncated=true but 200 rows is plenty" | Say it's 200 of N. The user decides if that's plenty. |
| "No edge found, so it's safe to change" | Say "no derived evidence" and name the blind spots. |
