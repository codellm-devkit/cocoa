---
description: Build or refresh the COCOA system graph for this project and report coverage
---

Build the system graph for the current project (or the path given in $ARGUMENTS if
present), then report what it covered.

1. Invoke the cocoa:mapping-a-system skill and follow its checklist exactly.
2. Run `cocoa map -p <path>` (default `.`). If the `cocoa` CLI is unavailable, use
   `uvx --from git+https://github.com/codellm-devkit/cocoa cocoa map -p <path>`.
3. Report: services analyzed (with language + function counts), every skipped
   service with its reason, the cross-service topology summary, and the artifact
   paths under `.cocoa/`.
