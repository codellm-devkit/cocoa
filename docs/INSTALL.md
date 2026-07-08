# Installing COCOA

COCOA is one Python package (`cocoa` CLI + MCP server) plus a skillset plugin.
Until the PyPI name is freed (tracked in cocoa-mcp#3), install from git via uv.

## Claude Code (full experience: skills + commands + MCP)

```
/plugin marketplace add codellm-devkit/cocoa
/plugin install cocoa@cocoa
```

This registers the four skills, `/cocoa:map`, `/cocoa:blast`, `/cocoa:demo`, and an
MCP server entry that launches `uvx --from git+https://github.com/codellm-devkit/cocoa
cocoa serve -p .` in your project.

## Codex / Cursor / other SKILL.md-compatible agents

Copy the `skills/` directories into your agent's skills location (e.g.
`~/.codex/skills/` or your Cursor rules directory) — each `SKILL.md` is
self-contained and includes the CLI fallback, so no MCP setup is required.
Install the CLI once: `uv tool install git+https://github.com/codellm-devkit/cocoa`.

## Plain MCP (any MCP client)

```json
{
  "mcpServers": {
    "cocoa": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/codellm-devkit/cocoa",
               "cocoa", "serve", "-p", "."]
    }
  }
}
```

## Docker (all analyzers, zero host toolchains)

```bash
docker run --rm -v "$PWD:/work" ghcr.io/codellm-devkit/cocoa map -p /work
```

Includes the unreleased Go analyzer (built from source) and the Java jar workaround.
Note: first Java analysis downloads a JDK into the project's `.cocoa/cache`
(network required once per project).

## Host toolchain notes

- Java: cldk auto-manages the JDK; clean pip installs currently need the jar
  workaround (python-sdk#236) — copy `codeanalyzer-2.4.1.jar` from the
  codeanalyzer-java releases into cldk's `analysis/java/codeanalyzer/jar/` dir.
- Go: put `codeanalyzer-go` on PATH or set `$CODEANALYZER_GO_BIN`.
- helm/kubectl: optional; enable static rendering of charts/kustomize wiring.
