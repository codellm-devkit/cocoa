# COCOA — dev guide

Static system-graph engine. Package manager: `uv` (`uv sync --all-groups`).

- Tests: `uv run pytest` (unit; integration/e2e/docker markers deselected by
  default). `-m integration` runs a real cldk analyzer; `-m e2e` runs the Online
  Boutique demo (network + analyzers; strict launch gate); `-m docker` builds and
  smokes the image.
- Module map: `cocoa/system/` = engine (detect → driver → facts → stitch →
  datastore → build → blast → topology → report/htmlmap); `cocoa/cli.py` = typer
  CLI; `cocoa/server.py` + `cocoa/tools/` = MCP; `skills//commands/` = plugin
  content (validated by `test/test_plugin_assets.py`).
- Provenance discipline is the product: never emit an edge without
  `DERIVED-STATIC`/`INFERRED` tagging; skips are recorded, never silent.
- Conventional commits, no trailers. Branch-per-issue `feat/issue-NNN-<slug>`.
