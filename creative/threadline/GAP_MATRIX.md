# THREADLINE 90–95% implementation gap matrix

| Acceptance area | Implemented state | Status |
|---|---|---|
| Synthetic case | One coherent fictional Cyclone Ilyra case with six records, five fictional organizations, two languages, rival evidence, a 34-hour gap, and blocking location contradiction | Complete |
| Source integrity | Exact half-open offsets, quotation matching, document ownership, validation hash, language/status metadata, and immutability checks | Complete |
| Claim lineage | Extracted-to-normalized-to-derived parents, raw/normalized values, transformations, certainty monotonicity, candidate scope, and rule consumers | Complete |
| Candidate ledger | Candidate-specific support, contradictions, timeline, compatibility, rivals, gaps, follow-up, notices, and contract results | Complete |
| Evidence contract | Ten canonical deterministic versioned rules with pass/warn/fail/block results, reason codes, artifacts, and spans | Complete |
| Release safety | Closed release states; blocked/review-required responses expose no classification; dispositions require an authorized review reference | Complete |
| Authorized review | Exact conflicting evidence, timeline/rival inspection, canonical structured dispositions, rationale, uncertainty, evidence requests, and save path | Complete |
| Auditability | SHA-256 append-only chain with source/claim/contract/review events and deletion/reorder/mutation/broken-link detection | Complete |
| End-to-end demo | Static `/demo`, actual components/data, reset, manual exploration, keyboard controls, and 13-step guided journey | Complete |
| Brand/positioning | Shared canonical tokens, semantic evidence threads, evidence-operating-system positioning, and proof-before-release copy | Complete |
| Browser automation | Manual production-browser exercise plus structural frontend tests; CI-grade Playwright suite remains | Post-95% hardening |
| Cinematic production | Zero-cost references retained; paid production deliberately not started | Deferred by phase gate |

This matrix records implemented code and verified behavior; detailed command evidence is in `VALIDATION_REPORT.md`.
