---
description: Run the Online Boutique flagship demo — map a real 11-service polyglot system and blast a proto field
---

Run COCOA's flagship demo end-to-end.

1. Run `cocoa demo` (first run clones the pinned Online Boutique fixture and may
   take minutes; Java analysis downloads a JDK on first use).
2. Report the results per cocoa:grounding-claims: graph size, every skipped service
   with reason (Go/C# skips are expected until their analyzers ship), the blast
   radius of `hipstershop.Money.units` grouped by service, and the token headline
   with its ratio — labeled as an estimate.
