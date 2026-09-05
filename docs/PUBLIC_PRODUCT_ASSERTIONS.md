# Public Product Assertions

This register is the evidence index for Atested-authored public product
assertions. Factual assertions name an observable subject and action and point
to repository evidence. Statements that are not yet factual are explicitly
marked aspirational.

| Assertion | Concrete subject and action | Evidence basis | Status |
| --- | --- | --- | --- |
| Atested's proxy intercepts model tool-call proposals before the agent receives them. | The HTTP proxy intercepts tool-call blocks and forwards the governed response. | `proxy/server.py`; `docs/website/docs-pages/how-atested-fits-in.md` | verified |
| The classifier assigns an evidence-based confidence tier to tool-call parameters. | The classifier inspects paths, commands, URLs, and related parameters and returns a tier. | `scripts/classifier.py`; `docs/website/docs-pages/how-the-classifier-works.md` | verified |
| The governance chain records policy decisions with linked hashes. | The record writer stores each decision and links it to the previous record hash. | `scripts/governance_chain.py`; `quality-service/src/writer.rs` | verified |
| Atested will provide hosted policy administration in a future release. | Atested will provide hosted policy administration after that capability is implemented. | This statement is aspirational; no current product behavior is asserted. | aspirational |
