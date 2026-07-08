# COCOA vs. graphify

[graphify](https://github.com/Graphify-Labs/graphify) popularized the "index your
repo into a queryable graph" workflow for AI agents — one-command setup, three
artifacts, token-efficient queries. COCOA adopts that exact UX and changes one
thing: **where the edges come from.**

| | graphify | COCOA |
|---|---|---|
| Unit of understanding | a folder of files | a distributed system |
| Edge derivation | tree-sitter AST for code (deterministic); LLM inference for docs/PDFs/images | real analyzers (WALA, Jedi, ts-morph, go/types via CLDK) + proto/k8s stitching |
| Edge provenance | `EXTRACTED` / `INFERRED` / `AMBIGUOUS` | `DERIVED-STATIC` / `INFERRED` (labeled fallback only) |
| Cross-language links | inferred by the model | derived: proto stubs ↔ handlers ↔ k8s wiring, with anchor-exclusivity and boundary-matching to prevent false edges |
| Databases | absent | first-class: Redis ops, SQL tables, ORM mappings as graph nodes/edges |
| k8s manifests | more files in the graph | a topology source (raw YAML + `helm template` + `kustomize build`) |
| Impact queries | neighborhood lookups | cross-service blast radius with strongest-path provenance semantics |
| Coverage honesty | n/a | every unanalyzed service recorded with a reason; truncation always labeled |
| Artifacts | `graph.json` / `graph.html` / `GRAPH_REPORT.md` | `system-graph.json` / `system-map.html` / `SYSTEM_REPORT.md` |
| Token efficiency | ~1.7k/query vs ~123k naive (their number) | same persisted-graph mechanism; `cocoa demo` measures ~25,000× on Online Boutique (estimate, printed per run) |

The trade: graphify covers 36 grammars and multi-modal inputs (docs, PDFs, images)
today; COCOA covers the languages with real analyzers (Java/Python/JS/TS shipped,
Go built-from-source in Docker, C# pending) and only code + configs. If you need
breadth-first repo Q&A, graphify is excellent. If an agent is about to *change* a
distributed system and needs to know what breaks — edges that are derived, labeled,
and complete-or-disclosed matter. That's COCOA.
