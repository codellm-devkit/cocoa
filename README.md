# COCOA — Code Context Agent

**Precise static system graphs of polyglot, k8s-native codebases — for AI agents.**

Point COCOA at a repo and it derives one queryable graph of the whole system:
per-service call graphs, cross-service RPC edges (stitched from protos, call sites,
and k8s wiring), and datastore access — every edge tagged `DERIVED-STATIC` (real
static analysis, via [CLDK](https://github.com/codellm-devkit/python-sdk)) or
`INFERRED` (labeled fallback). Never guessed.

> **Graphify indexes files. COCOA understands systems.**
> See the head-to-head: [docs/COMPARISON.md](docs/COMPARISON.md)

## The hero query: blast radius

```bash
cocoa blast -p . --target hipstershop.Money.units --kind proto-field
```

…returns exactly which functions in which services break — across languages, across
RPC boundaries, through the database — with call sites and provenance per hop.
On Google's Online Boutique (11 services, 5 languages), the answer costs ~1/25,000th
of the tokens an agent would burn reading every service (estimated; `cocoa demo`
prints the measurement).

## Quick start

```bash
# no install (uv required):
uvx --from git+https://github.com/codellm-devkit/cocoa cocoa map -p /path/to/repo
uvx --from git+https://github.com/codellm-devkit/cocoa cocoa blast -p /path/to/repo \
    --target <target> --kind <proto-field|rpc|function|table|redis-key>

# flagship demo (clones Online Boutique, maps it, blasts a proto field):
uvx --from git+https://github.com/codellm-devkit/cocoa cocoa demo

# docker (all analyzers baked in, incl. the unreleased Go analyzer):
docker run --rm -v "$PWD:/work" ghcr.io/codellm-devkit/cocoa map -p /work
```

Agent setups (Claude Code plugin with skills + slash commands + MCP, Codex, Cursor,
plain MCP): [docs/INSTALL.md](docs/INSTALL.md).

## What you get

| Artifact | What it is |
|---|---|
| `.cocoa/system-graph.json` | the full graph — query it forever without re-reading source |
| `.cocoa/system-map.html` | self-contained interactive map, provenance-colored |
| `.cocoa/SYSTEM_REPORT.md` | services, topology, data access, dead-RPC candidates, and **every skipped service with its reason** |

## Language & analyzer status (honest)

| Language | Analyzer | Status |
|---|---|---|
| Java | codeanalyzer-java (via cldk) | works; clean pip installs need the jar workaround ([python-sdk#236](https://github.com/codellm-devkit/python-sdk/issues/236)) — the Docker image includes it |
| Python | codeanalyzer-python (via cldk) | works |
| JS/TS | codeanalyzer-typescript (via cldk) | works |
| Go | codeanalyzer-go | unreleased ([codeanalyzer-go#5](https://github.com/codellm-devkit/codeanalyzer-go/issues/5)); Docker image builds it from source; host installs need `codeanalyzer-go` on PATH or `$CODEANALYZER_GO_BIN` |
| C# | codeanalyzer-dotnet | pending ([codeanalyzer-dotnet#1](https://github.com/codellm-devkit/codeanalyzer-dotnet/issues/1)) — services are recorded as skipped, never silently dropped |

## Skills (the agent discipline layer)

The plugin ships four skills modeled on the
[obra/superpowers](https://github.com/obra/superpowers) paradigm: `using-cocoa`
(answer system questions from the graph, not file reads), `mapping-a-system`,
`blast-radius`, and `grounding-claims` — whose HARD-GATE is the product promise:
*never present an `INFERRED` edge as fact.*

## License

MIT. Built on [CodeLLM-DevKit](https://codellm-devkit.info).
