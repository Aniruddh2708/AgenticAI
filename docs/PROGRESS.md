# Blueprint compliance — updated 15 October 2026

Read the original [BLUEPRINT.md](BLUEPRINT.md) alongside actual tests and
[VALIDATION.md](VALIDATION.md). A phase being implemented does not certify every
stretch requirement or production capability.

The current forecasting audit and complete implemented research plan are in
[FORECASTING_AUDIT.md](FORECASTING_AUDIT.md). The trained return candidate did not
beat the historical mean baseline and the admission gate failed. The price
experiment and full-agent policy checks remain separate from investment effectiveness.
The [uncertainty follow-up](FORECASTING_FOLLOWUP.md) retains simple baselines,
fixes unsupported quantiles and joint denominators, and records 91.25% marginal
coverage on a separately frozen 2024–2025 period. Wider intervals and uncertain
score comparisons prevent a stronger improvement claim; both periods are spent.

The user has now requested a release to the existing Render service. Startup
honors Render's assigned port, the corrected research summary ships with the
release, and a pre-login commit marker identifies the running revision. Native
Render-style startup and 305 tests passed; see [RENDER.md](RENDER.md) and current
[validation evidence](VALIDATION.md). Live deployment remains unverified because
Render API credentials and working network access are unavailable in this task.

| Phase / requirement | Status | Evidence / limit |
|---|---|---|
| Contracts, profiles, configuration | Implemented | Compatible original fields; additive claims, decision basis and policy identifiers |
| Seeded OHLCV and indicators | Implemented | Five reproducible demo tickers; independent evaluation paths separate |
| Five parallel agents | Implemented and tested | Barrier regression proves overlap; actual timing does not show a useful speedup |
| BM25 corpus retrieval and cited filings | Implemented and tested | 21 synthetic documents; malformed metadata skipped; ticker/type/date filters |
| Chroma persistence/filtering | Package integration tested | Fixture vectors only; not MiniLM success |
| MiniLM + BM25 hybrid retrieval | Implemented; successful local run reported by user | 21 chunks; stayed hybrid after analysis. Not repeated in this core-only cloud task |
| Risk and personalized synthesis | Corrected and tested | Concentration precedes missing evidence; cash/equity/sector metrics separated; fixed demo heuristics |
| Failure handling | Expanded and tested | Ingest/retrieval/agent/storage failures; unsaved results explicit; timed-out threads can still finish later |
| Claim-level evidence checks | Implemented within finite rules | Exact quotation, financial template or recomputation; no generic semantic truth proof |
| Session metrics | Implemented | Supported/submitted claims, failures, compute time, cash/equity what-if and evaluation summaries |
| Technical backtest and calibration | Expanded and measured | 826 scored of1080 windows; direction probabilities only; underperforms baselines |
| Full-agent point-in-time replay | Implemented and measured | 90 profile decisions/30 market windows; synthetic policy checks, not strategy profitability |
| Real dated return forecasting | Implemented and evaluated; research gate failed | Hash-pinned 2010–2020 data; chronological train/validation/calibration/test; 80 held-out windows, no established learned edge |
| Historical price full-agent replay | Implemented and evaluated | Genuine dated prices, three synthetic profiles, historical text withheld; constraint checks, no action accuracy/P&L |
| Forecast audit dashboard/API | Implemented and tested | Reads saved summary only; no auto-training, model promotion or portfolio action changes |
| Uncertainty calibration and stability selection | Implemented; research-only | Per-security causal scales, 24 calibration dates, finite rank checks, shared spent-period ledger; point baselines retained |
| Fresh follow-up and exploratory reporting | Evaluated and labelled | Same-row baseline/width/score comparisons; partial origins excluded from joint coverage; source calendar gap disclosed |
| Active startup paths | Corrected and tested | 60-second initialization, 120-second readiness; root compatibility wrappers prevent duplicate drift |
| Measured sequential/parallel benchmark | Implemented | Identical warmed inputs/output verification; no artificial delays |
| Dashboard | Implemented and exercised | Profile forms, cache refresh, failures, real session chart, source highlighting, beginner/analyst views |
| Watchlist/history/decisions | Implemented | Profile-dependent alerts; no broker execution or holdings mutation |
| Presentation | Implemented | HTML deck and generated presentation PDF; no guaranteed judging outcome |
| Backup capture | Actual 119.3-second video and twelve screenshots verified | Silent recorded browser views are not a narrated five-minute rehearsal |
| Docker deployment | Implemented and locally verified | Non-root/shared gate/private API/persistent volume; offline wheels build used |
| Public hosted application | BM25 Render deployment reported working by user | https://vibefinance.onrender.com; not logged into or redeployed in this pass |
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
investment suitability or alpha. Historical price model evidence also fails the
research promotion gate: probability selection chose the prior baseline, return
MAE did not beat the mean baseline and 90% intervals covered only 78.75%.

User-reported real local neural retrieval and BM25 Render hosting supersede the
older global blocker claims. This cloud task did not reproduce MiniLM or access
the private demo. Live Yahoo access remains unverified here; the historical
archive is a documented third-party snapshot, licensed for noncommercial research.
Native macOS execution and restoration into a fresh published cloud task are unverified.

The original implementation and this corrective pass belong to the same authorized
GitHub repository. Inspect its Git history for the delivered commit. Environment
setup, startup and required network additions were saved as a draft; they do not
publish or apply themselves. Fresh-task restoration remains unverified.
