# COCOA — Code Context Agent

Precise static system graphs of polyglot, k8s-native codebases — code + RPC
topology + data access — for AI agents. Powered by [CLDK](https://github.com/codellm-devkit/python-sdk).

Status: v1 under construction. See issue #1 (epic).

## Quick start

```bash
uv run cocoa map -p /path/to/your/polyglot/repo     # build .cocoa/ artifacts
uv run cocoa blast -p /path/to/repo --target hipstershop.Money.units --kind proto-field
uv run cocoa serve -p /path/to/repo                 # MCP server (5 system tools)
uv run cocoa demo                                   # Online Boutique flagship demo
```

Requires Docker-less local analyzers today: Java/Python/TypeScript run via CLDK
automatically; Go needs `codeanalyzer-go` on PATH (or pointed to via
`CODEANALYZER_GO_BIN`); C# is recorded as skipped until `codeanalyzer-dotnet` ships.
