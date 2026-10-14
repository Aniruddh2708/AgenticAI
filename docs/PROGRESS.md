# Blueprint compliance after the corrective implementation

Read the original [BLUEPRINT.md](BLUEPRINT.md) alongside actual tests and
[VALIDATION.md](VALIDATION.md). A phase being implemented does not certify every
stretch requirement or production capability.

| Phase / requirement | Status | Evidence / limit |
|---|---|---|
| Contracts, profiles, configuration | Implemented | Compatible original fields; additive claims, decision basis and policy identifiers |
| Seeded OHLCV and indicators | Implemented | Five reproducible demo tickers; independent evaluation paths separate |
| Five parallel agents | Implemented and tested | Barrier regression proves overlap; actual timing does not show a useful speedup |
| BM25 corpus retrieval and cited filings | Implemented and tested | 21 synthetic documents; malformed metadata skipped; ticker/type/date filters |
| Chroma persistence/filtering | Package integration tested | Fixture vectors only; not MiniLM success |
| MiniLM + BM25 hybrid retrieval | Implemented but blocked/unverified | Real model unavailable; huggingface.co HTTP403 |
| Risk and personalized synthesis | Corrected and tested | Concentration precedes missing evidence; cash/equity/sector metrics separated; fixed demo heuristics |
| Failure handling | Expanded and tested | Ingest/retrieval/agent/storage failures; unsaved results explicit; timed-out threads can still finish later |
| Claim-level evidence checks | Implemented within finite rules | Exact quotation, financial template or recomputation; no generic semantic truth proof |
| Session metrics | Implemented | Supported/submitted claims, failures, compute time, cash/equity what-if and evaluation summaries |
| Technical backtest and calibration | Expanded and measured | 826 scored of1080 windows; direction probabilities only; underperforms baselines |
| Full-agent point-in-time replay | Implemented and measured | 90 profile decisions/30 market windows; synthetic policy checks, not strategy profitability |
| Measured sequential/parallel benchmark | Implemented | Identical warmed inputs/output verification; no artificial delays |
| Dashboard | Implemented and exercised | Profile forms, cache refresh, failures, real session chart, source highlighting, beginner/analyst views |
| Watchlist/history/decisions | Implemented | Profile-dependent alerts; no broker execution or holdings mutation |
| Presentation | Implemented | HTML deck and generated presentation PDF; no guaranteed judging outcome |
| Backup capture | Actual 119.3-second video and twelve screenshots verified | Silent recorded browser views are not a narrated five-minute rehearsal |
| Docker deployment | Implemented and locally verified | Non-root/shared gate/private API/persistent volume; offline wheels build used |
| Public hosted application | Not deployed | User confirmed no hosting account |
| Live Yahoo success | Blocked/unverified | Observed fc.yahoo.com HTTP403; simulation fallback verified |
| Optional LLM narration | Not implemented | Deterministic explanation remains the offline behavior |
| Real filings, licensed news, real-history strategy validation | Not implemented | Fictional documents are explicitly disclosed |
| Individual accounts/privacy isolation/regulatory approval | Not implemented | Shared demo token only; production requirements remain |

## Confirmed earlier problems resolved

- Excessive position still triggers REDUCE when fundamentals are missing.
- All-cash allocation is not classified as high equity risk.
- Known upstream failures do not bypass agent degradation; storage failure cannot
  be advertised as successfully saved.
- No-growth, negated-positive and resolved/absent-risk phrases have regression cases.
- Altered/unsupported/duplicated claims and forged classifications are rejected.
- Evidence coverage includes rejected submitted statements rather than hiding them.
- Calibration and backtest definitions clearly distinguish direction probabilities
  from recommendation evidence strength.
- Actual benchmark measures sequential and parallel modes, including equivalence.
- Dashboard edits invalidate stale profile-dependent results and all network
  interactions have explicit error paths.

## Remaining substantive limitations

Finite extraction is not comprehensive accounting or arbitrary-language understanding.
Portfolio rules do not optimize allocations/correlations or evaluate every prospective
HHI boundary crossing. Forward returns are descriptive: no trading simulation,
transaction costs, revaluation or calibrated personalized-action success model exists.
Recommendation evidence strength and synthetic benchmark accuracy do not establish
investment suitability or alpha.

Successful real neural/live integration needs external network/model access.
A public deployment needs a host/persistent disk and access configuration. Native
macOS execution and restoration into a fresh published cloud task are unverified.

The original implementation and this corrective pass belong to the same authorized
GitHub repository. Inspect its Git history for the delivered commit. Environment
setup, startup and required network additions were saved as a draft; they do not
publish or apply themselves. Fresh-task restoration remains unverified.
