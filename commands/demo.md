---
description: Run the Online Boutique flagship demo — map a real 11-service polyglot system and blast a proto field
---

Run COCOA's flagship demo end-to-end.

1. Run `cocoa demo` (if the `cocoa` CLI is unavailable, use `uvx --from git+https://github.com/codellm-devkit/cocoa cocoa demo`) (first run clones the pinned Online Boutique fixture and may
   take minutes; Java analysis downloads a JDK on first use).
2. Report the results per cocoa:grounding-claims: graph size, every skipped service
   with reason (a C# skip is expected until codeanalyzer-dotnet ships; a Go skip means
   `codeanalyzer-go` isn't on PATH or `$CODEANALYZER_GO_BIN` — an environment
   gap the user can fix, not a missing analyzer), the blast
   radius of `hipstershop.Money.units` grouped by service, and the token headline
   with its ratio — labeled as an estimate.
