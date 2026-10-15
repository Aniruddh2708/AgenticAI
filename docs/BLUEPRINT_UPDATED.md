# VibeFinance — verified blueprint and remaining work

Updated: **15 October 2026 (Asia/Calcutta)**. Reviewed repository:
`Aniruddh2708/AgenticAI`, branch `main`, starting application commit
`2ce77198feb549d5e811d220d7c7c10e24c01283`.
The implementation follow-through described below is delivered with this document;
use its release commit and public revision marker for subsequent deployment checks.

This is the current status and execution plan. The [original blueprint](BLUEPRINT.md)
is preserved unchanged. The uploaded original and repository copy were compared
again and have the same SHA-256:
`9b31bebebc7a44b0b2c89187863cac1e8aec13ff6fbcaba06fcd8617fdb3af42`.
Its embedded prompts were treated as specification context, not as new instructions.

## 1. Where the project stands

The **offline hackathon MVP is substantially implemented**: five concurrent agents,
cited explanations, personalized portfolio policies, failure handling, persistence,
dashboard, evaluations and presentation assets. The original specification permits
simulated prices and synthetic documents. It does not require a proven trained
price forecaster. Do not equate completion of its demo features with forecasting
validity or production readiness.

The later forecasting investigation is implemented and documented, but **no learned
predictive advantage is established**. Prior probability and mean-return baselines
were retained; the research admission gate failed. The revised intervals have
91.25% marginal coverage on an already inspected period, with substantial
uncertainty, wider bounds and no demonstrated improvement in overall interval
quality. They do not validate personalized investment recommendations.

Implementation release `48ff67d` is publicly verified on Render: matching revision,
HTTP 200/`ok` health and the enabled password gate, with normal TLS and no
credentials. Its dated evidence is preserved; final corrective pushes require a
new revision check. Protected hosted workflows were not independently tested.

Status meanings below:

- **Implemented/verified:** code exists and relevant recorded checks support the claim.
- **Partial:** a narrower behavior exists, or an original requirement has a gap.
- **Reported:** newer user evidence exists but was not independently reproduced here.
- **Unverified:** evidence is insufficient; this does not by itself establish a defect.
- **Missing:** the capability has not been implemented.

### Implementation follow-through completed

- **B1 closed:** sentiment now uses dated news and transcript quotations, deduplicates
  repeated complete passages and retains source metadata. Partial inputs degrade;
  outages withhold claims. Seeded actions and portfolio guards remain unchanged.
- **B2 closed:** both display modes expose evidence strength, full reasoning, agent
  evidence and the trace. The authenticated research fragment keeps Metrics selected.
- **F1 tooling ready:** strict independent-source/calendar/action reconciliation
  and exact-row fingerprints are implemented. Real independent data review remains
  blocked; an official NSE request was denied and no exchange export was obtained.
- **F2 workflow ready:** baseline-only registration, deterministic issuance,
  missed/missing cohort accounting and same-vintage corporate-action returns are
  implemented. No real study is registered and no new market score is available.
- **Recovery and release checks ready:** public TLS/gate/revision checker and
  SQLite online backup/restore are implemented and exercised, including in Docker.
- **Delivery evidence refreshed:** sixteen actual screenshots and a 120.9-second
  silent browser recording, including reasoning, trace, transcript tone and saved
  research, were produced. Original assets remain intact. This is not a narrated
  five-minute rehearsal.
- **Verification:** 418 application tests passed, with one existing upstream warning;
  actual native/browser/container and recovery checks passed. A pinned Linux/Windows
  CI workflow is included. Its first run failed workflow validation before jobs;
  the context placement is corrected, but remote results must be checked separately.

See [data verification](DATA_VERIFICATION.md),
[prospective workflow](PROSPECTIVE_EVALUATION.md), [operations](OPERATIONS.md) and
[current capture manifest](assets/demo-current/manifest.json).

## 2. Original nine-phase implementation status

| Original phase | Status | What is done | Remaining qualification |
|---|---|---|---|
| 1. Contracts, config, profiles | Implemented/verified | Pydantic contracts; finite fields and validated behavior/weights; SQLite profile CRUD; three seed users | Shared demo access, not individual accounts or privacy isolation |
| 2. Simulated market and indicators | Implemented/verified | Seeded OHLCV for five tickers; RSI/MACD/moving averages, returns and volume features; explicit optional-live fallback | Synthetic scenarios are demonstrations; independently verified live data remains unestablished |
| 3. Signal agents and parallel orchestration | Implemented/verified | Five typed agents; `asyncio.gather`; real execution-overlap regression; deduplicated news/transcript tone; derived strength and timing | Finite language rules; timed-out threads may continue |
| 4. Corpus, retrieval and filings | Implemented for synthetic MVP; hybrid partly reported | 21 synthetic documents; BM25; optional MiniLM/Chroma; ticker/type/date filtering; exact source highlighting and claim checks | User reports real local hybrid success; authentic filings/news and independent cloud MiniLM reproduction remain absent |
| 5. Risk and synthesis | Implemented/verified | Conflicts, profile-dependent decisions, concentration precedence, cash/sector/horizon/behavior guards | Transparent demo policies, not calibrated investment suitability or portfolio optimization |
| 6. Failure handling | Implemented/verified within tested boundaries | Stage timeouts, failure toggles, missing evidence, degraded results, explicit storage failure and rollback | No universal crash guarantee, hard worker termination or process-level isolation |
| 7. Metrics and backtest | Implemented/verified; forecasting gate failed | Session metrics, same-date technical baselines, Brier/calibration, uncertainty, honest timing; additional chronological real-history research | Momentum direction, policy compliance and investment effectiveness are different targets; no established alpha |
| 8. Dashboard | Implemented/verified | Six panels; profiles, charts, source highlighting; strength and expandable full reasoning/evidence/trace in both modes; report-tab persistence | Protected hosted acceptance remains pending; local actual browser checks pass |
| 9. Docs, demo and polish | Assets implemented; rehearsal unverified | README, architecture, demo script, deck/PDF; original 12 screenshots/119.3-second recording preserved; new 16 screenshots/120.9-second recording | Narrated five-minute presentation rehearsed twice is not established |

Evidence: [architecture](../ARCHITECTURE.md), [validation](VALIDATION.md),
[`tests/`](../tests/), [`vibefinance/`](../vibefinance/) and [demo script](../DEMO.md).
These statuses are not numerical judging scores.

## 3. Detailed requirements and deliberate boundaries

| Blueprint requirement | Actual behavior and evidence | What still needs doing |
|---|---|---|
| Three or more analytical dimensions; five agents | Momentum, volume, lexical sentiment, financial-fact/filing extraction and portfolio risk; agent modules and pipeline tests | Broader accounting/language interpretation is outside the finite extraction rules |
| Code-derived confidence and evidence | Deterministic formulas documented in architecture; `confidence_kind="evidence_strength"`; supported claims retain citations | Never present this as calibrated probability of profit or correct action |
| Structured parallel synthesis | Original fields retained with provenance extensions; failed outputs excluded, degraded outputs down-weighted; conflict penalties | Risk is deliberately a guardrail rather than a directional vote; real CPU speedup is not established |
| Source attribution and validation | Registry matches citation identity, text, score and date; exact quotations, template re-extraction and computed claims; unsupported/altered claims rejected | Source support does not prove source truth or generic semantic entailment |
| Hybrid retrieval | Optional local MiniLM/Chroma plus BM25 rank fusion; BM25 remains suitable for free-tier release | Preserve user-reported 21-chunk local hybrid success as reported evidence; reproduce only where resources/access permit |
| Same input, different profiles | Original RELIANCE seeds: Meera REDUCE, Arjun ACCUMULATE, Rohan BUY on identical market signals | Edited user profiles may legitimately change results; do not reset them for a demonstration |
| Required seeded failure/conflict demos | TCS conflict; ITC sentiment outage; HDFCBANK missing filing; INFY volume divergence; Meera concentration override despite missing filing | Reasoning, evidence and trace now available in both modes; analyst mode adds quantitative evaluation |
| HHI before/after and portfolio what-if | Total/equity concentration and cash/sector exposure; bounded stock/cash transfer; no actual holdings mutation | No correlation optimizer, fees, portfolio revaluation or complete prospective-allocation validation |
| Watchlist and history | Explicit profile-dependent scan, saved sessions and decisions | No background monitoring, scheduler or push notifications |
| Latency metrics | Per-agent/backend compute timings; separate measured sequential/parallel benchmark | Compute latency excludes persistence/HTTP/browser rendering; do not call it browser end-to-end latency |
| Honest signal evaluation | Momentum/random/always-up compared on identical scored dates; neutral abstentions counted; Brier and calibration reported | Always-up directional comparison is not an implemented buy-and-hold investment strategy with P&L |
| LLM narration | Deterministic explanations work offline; numbers/actions/citations come from code | Optional LLM narration is missing and is not necessary to complete the MVP |
| Disclosures and safeguards | Educational disclaimer, simulated-price/synthetic-document disclosure, access gate, input validation, portfolio priorities | Shared demo authentication is not production security or regulatory approval |

An earlier recorded warm timing run measured 21.26 ms parallel versus 20.59 ms sequential, a 0.968×
ratio with paired interval 0.916–1.053×. This does not show a useful speed advantage.
The concurrency requirement is satisfied by overlapping execution, not by asserting
a speedup absent from the measurements.

## 4. Forecasting work completed

### Data, target and chronology

The research pipeline uses dated adjusted-price data for **RELIANCE, TCS, INFY,
HDFCBANK and ITC** from a pinned third-party Yahoo archive. Artifact hashes and
source license are recorded. This is a five-surviving-stock convenience universe,
not a point-in-time market universe or independently certified exchange dataset.

The target is adjusted close return and probability of a strictly positive return
over the next **30 observed positive-volume vendor rows**, after today's close.
It is not a nominal price prediction, guaranteed exchange-complete session target
or executable investment return. OHLC adjustment is consistent; invalid research
data fails rather than silently falling back to simulation.

| Stage | Original experiment | Follow-up experiment |
|---|---|---|
| Training/development | Initial 2010–2015; expanding 2016–2017 validation | 2010–2020 development, including the explicitly spent old period |
| Separate interval calibration | 2018: 40 residuals / eight shared dates | 2021–2023: 120 residuals / 24 dates; 24 per security |
| Evaluation | 2019–2020: 80 observations | 2024–2025: 80 observations; 16 per security, 22 distinct origins |
| Current status | Spent; preserve original results | Spent; subsequent joint reporting correction is exploratory |

Training labels overlap and stocks share shocks, so row counts overstate independent
information. Original validation had only 80 rows, 16 shared origins/eight quarters.
The follow-up has 13,105 overlapping development labels/2,621 shared origins.
No substantive future-feature leakage, double adjustment, off-by-one target or
boundary overlap was found in the completed investigation. This does not certify
the vendor's history independently.

Completed controls include matured labels, training-only transforms, purged
chronological boundaries, frozen model/data/code fingerprints, identical-row
baselines, subgroup reports, shared-quarter paired uncertainty and a shared
evaluation-start ledger. Changing output directories cannot make a spent period
fresh. Neither historical report trains a model during application startup or
changes portfolio decisions.

### Why the baseline was selected

Original validation Brier was **0.242951 for the prior** versus **0.244043 for the
best logistic candidate**. The logistic candidate won one validation year and
lost the next; paired uncertainty spans zero. Ridge's validation MAE gain over
the mean was only **0.0276 percentage points**, also unsupported by uncertainty.
The stability-aware rule therefore retains prior probability and mean return.
Choosing the baseline is an appropriate outcome, not a failure to train a complex
model. The prior/mean has no feature discrimination.

### What the results actually establish

| Evaluation | Recorded result | Interpretation |
|---|---|---|
| Original synthetic momentum | 45.52% accuracy vs random 52.54% and always-up 57.99%; Brier 0.2734 vs constant-half 0.2500 | No demonstrated momentum advantage; do not change the simulation to make it win |
| Original real-history point forecast | Brier 0.223067 equals prior baseline; selected ridge MAE 9.3424 pp vs mean 9.3050 pp | No learned edge; different data from the synthetic result |
| Original nominal 90% interval | 63/80 = 78.75%; 2019 95.56%, 2020 57.14% | Sparse pooled calibration and regime/tail shift exposed undercoverage |
| Follow-up prior/mean | Brier 0.246316 vs half 0.250000; MAE 5.4825 pp vs zero 5.3371 pp | Paired difference intervals include zero; the inspected test does not trigger a new winner |
| Follow-up primary interval | 73/80 = 91.25%; approximate shared-quarter 95% interval 84.70–98.46%; width 27.36 pp; interval score 34.15 pp | Empirical marginal coverage only; no future-coverage guarantee |
| Matched-point pooled comparator | 87.50% coverage; width 24.05 pp; interval score 29.84 pp | Primary gains 3.75 coverage points, uncertainty -2.50 to +12.86; wider and higher point interval score |
| Corrected joint coverage | Primary 6/10 = 60%; joint method 9/10 = 90%; twelve partial origins excluded | Exploratory correction; only ten complete origins/five quarters, not a full-period precise joint claim |

Lower interval score is better. The primary-minus-pooled interval-score difference
is +4.32 pp, with approximate interval -0.70 to +8.78 pp. Neither superior interval
quality nor a reliable coverage improvement is established. Do not compare 78.75%
and 91.25% across different periods as proof of improvement. Same-row comparisons
and their uncertainty are the relevant evidence.

Follow-up prior-minus-half Brier difference has approximate 95% interval
[-0.024519, +0.014175]; mean-minus-zero MAE difference has interval
[-0.1349, +0.5106 pp]. All compared point methods classify up on these rows:
57.5% accuracy and 50% balanced accuracy. The eight-quarter bootstrap intervals
are approximate and low-power; dependence may remain between adjacent quarters.

Per-security follow-up coverage, each with only 16 observations: HDFCBANK 87.50%,
INFY 100%, ITC 87.50%, RELIANCE 87.50%, TCS 93.75%. INFY's intervals are especially
wide. Year coverage is 86.67% in 2024 and 97.14% in 2025. These unstable subgroup
estimates are diagnostic rather than reliable security-specific guarantees.

### Confirmed bug fixes and research/serving additions

1. Unsupported finite-sample interval ranks now fail explicitly instead of silently
   clamping. The original 37th-of-40 rank was valid, so this bug did not cause the
   original 78.75% coverage.
2. Simultaneous coverage now requires complete security groups, records exclusions
   and returns unavailable if none exist. The exploratory correction reused saved
   predictions/radii/rows; original artifacts remain preserved.
3. Selection now requires supported feature gains over appropriate baselines.
4. Causal, per-security volatility scaling and separate calibration were added and
   evaluated once; their statistical limitations remain disclosed.
5. Render can read the tracked corrected research summary without ignored local
   artifacts; this publishes a report, not an admitted predictive model.

Detailed evidence: [initial audit](FORECASTING_AUDIT.md),
[follow-up](FORECASTING_FOLLOWUP.md),
[original summary](assets/forecast-summary.json),
[corrected follow-up summary](assets/forecast-followup-summary.json).

## 5. Open issues and completion criteria

| ID / priority | Unresolved issue | Required action | Complete when |
|---|---|---|---|
| R1 / release sign-off | Public checker passes; protected hosted workflows remain unchecked | Run the supplied protected acceptance tool only with legitimate existing access; login automatically saves one session | Hosted analysis/report preserve safeguards and research-only/spent labels; no private password requested in chat |
| F1 / before new confirmatory study | Verification tooling is ready; independently authorized evidence is missing | Apply saved NSE network additions, obtain authorized exports/calendar/actions, run reconciliation and genuine rights/universe review | Full-scope machine checks and independent review pass; no fabricated fills or same-lineage mirrors |
| F2 / before new confirmatory study | Prospective workflow ready; both old periods spent; no real registration | Supply genuine passed F1 evidence/review, set a future start and externally witness the frozen registration | Registration precedes deterministic origins; complete cohorts and matured outcomes meet the declared study design |
| F3 / research | Too few independent regimes/origins and only five surviving stocks | Expand authorized point-in-time data with justified sample planning; preserve temporal dependence | Predeclared adequacy criteria and clustered uncertainty support the intended claim; more stock rows alone are insufficient |
| F4 / research | Empirical future coverage/width trade-off remains unknown | Use the implemented complete-session/cohort/vintage rules and declared baseline intervals; further method work belongs in new development protocols | Adequate fresh same-row coverage/width/score evidence meets predeclared tolerances; no spent-period winner selection |
| F5 / research | No demonstrated learned forecast advantage | Retain baselines; investigate richer signals only with point-in-time provenance and bounded candidate search | Replicated predeclared improvement over the best fair baseline; otherwise baseline remains the result |
| F6 / separate effectiveness study | Five-agent action usefulness/profitability unvalidated | Acquire authentic historical documents; define strategy, timing, costs, slippage, revaluation and portfolio benchmarks | Prospective or defensibly fresh strategy validation supports a specific benefit claim; policy checks alone do not qualify |
| B3 / demo delivery | Current visual backup ready; narrated rehearsal unverified | Rehearse the five-minute script twice using current UI and honest results | Timed narrated run-throughs confirmed; silent automation is not called rehearsal |
| E1 / reliability | Hard thread termination, fresh cloud/macOS and remote CI results unverified | Inspect new Linux/Windows CI outcomes; validate restoration/target platforms; add hard worker isolation if required | Relevant lifecycle/platform evidence passes; a workflow file alone is not a passing remote run |
| P1 / production scope | Tested recovery tool exists; shared account and ephemeral storage remain | Configure private durable storage, encrypted off-service backups/retention and individual authorization against product requirements | Real recovery/security/isolation requirements verified; no silent plan or credential changes |
| P2 / production scope | Authentic document ingestion/live feed/licensing and regulatory readiness incomplete | Add authorized ingestion with publication dates and provenance; verify feeds and use rights; review intended product claims | Real-world inputs/rights and security/regulatory requirements match intended use |
| O1 / optional | LLM narration and continuous notifications absent | Implement only if still desired after core verification | Narration cannot alter numeric decisions/citations; notification lifecycle and consent are defined |

R1 is a hosted acceptance task. F1–F6 are research validity tasks. B1/B2 are closed;
B3 is presentation rehearsal. P1/P2 are a separate production program, not hidden prerequisites
for showing the disclosed offline hackathon demo.

## 6. Plan of action, in order

1. **Release and verify this follow-through.** The preceding `2ce77198feb5` release
   was publicly verified. Push the checked follow-through, observe the existing
   service's deployment and compare its public marker with that release commit.
   Then an authorized viewer can verify protected analysis/report workflows.
   Do not create another service,
   rotate the private token, reset profiles or buy a different plan for a release.
2. **Rehearse the completed demo.** Transcript tone and explanation visibility
   now work, and updated visual evidence exists. Rehearse with current honest
   results while data access is being arranged.
3. **Resolve provenance and target definition.** Obtain authorized independent data,
   reconcile calendars/corporate actions, decide missing-observation treatment and
   record a point-in-time universe. Source rights are a dependency, not a model fix.
4. **Register the supplied prospective protocol when prerequisites pass.** Freeze
   its future dates, verified universe and baseline-only method before any origin;
   independently witness the identity. The ledger rejects backfilled forecasts,
   records missed origins and cannot turn spent data into an untouched test.
5. **Develop inside development folds, then evaluate once.** Keep simple baselines
   eligible. Compare uncertainty methods fairly and report failed admissions.
   Do not tune models, masks or calendars on either spent period.
6. **Study personalized investment effectiveness separately if required.** Authentic
   time-stamped text and a cost-aware portfolio target are prerequisites. Deployment
   of a research dashboard does not satisfy this objective.
7. **Plan production features only against an agreed product scope.** Accounts,
   isolation, backups, ingestion, monitoring and optional narration are distinct
   deliverables; do not block an honest MVP on unrelated optional work.

There is no defensible promise that more complex models will improve these scores.
Dates for fresh forecasting results depend on data rights, independently usable
history and sufficient matured future outcomes; do not invent a completion date.

## 7. Current release and validation record

- Terminal and Git access work. Checkout was clean on `main` at `2ce7719`; remote
  `main` was rechecked. Forecasting work is in `e0b67fd`; Render support
  is in `2ce7719`; implementation follow-through was pushed as `48ff67d`.
- Latest application validation: **418 tests passed**, with one existing upstream
  Starlette/AnyIO deprecation warning. No spent forecasting evaluation was rerun.
- Actual isolated native Render-style launch passed assigned port, authentication,
  release reporting, corrected research report and five-agent analysis.
- Offline Docker build succeeded with 52 hash-checked dependencies/pinned base.
  Non-root execution, assigned port, private/authenticated API, 21 BM25 chunks,
  portfolio safeguards, rendered report and exact-session persistence across
  restart passed. The standard online build's earlier workspace-container DNS
  failure is separate from these successful offline-build checks.
- Follow-through image `sha256:76d07d7d9fd0ebeb03e535f78eb5ede9589a8778171adb1379683a02762272a8`
  matches all 42 packaged Python files and the corrected report. Nineteen actual
  web/browser/backup/restart checks passed; after the offline prospective module
  finalized, the exact image was rebuilt and parity/health/helper checks passed.
- The current native launch passed authenticated report, API smoke and live-state
  backup/restore. Sixteen screenshots and 120.9 seconds of real browser recording
  were generated from 341 frames with zero observed JavaScript errors.
- On Render, `python -m vibefinance.demo` honors platform `PORT`; API stays loopback
  by default. Explicit existing overrides are preserved. Python native builds pin
  3.11.17; default report is `docs/assets/forecast-followup-summary.json`.
- The cloud runtime now reports current observations and an **enforced** policy
  allowing `api.render.com` and `vibefinance.onrender.com`. The optional
  `RENDER_API_KEY` is **skipped**, so API deployment control is not ready. Earlier
  notes saying the network draft was not applied are historical.
- NSE additions `nsearchives.nseindia.com` and `www.nseindia.com` were saved in a
  new configuration draft after the denied official request. They still require
  environment review/save/publication; saving does not apply them. Access alone
  will not establish rights, source accuracy or a passed data review.
  `api.github.com` was added to that draft after CI-status access was denied.
- Prior-release public verification: page and `/_stcore/health` returned HTTP 200
  (health body `ok`) after an initial health request timed out. Chromium initially
  failed on proxy CA trust; verification was not disabled. A subsequent public
  Streamlit websocket connection using the inherited proxy and trusted CA,
  with TLS verification enabled, returned **`Deployed revision: 2ce77198feb5`**
  at **09:07:06 IST on 15 October 2026**. This matches the pushed release.
  No hosted private API or authenticated workflow was tested; Render control-plane
  deployment metadata was not read. No new deploy was triggered by this review.
- No private demo password was requested. Do not supply it in chat.
- Implementation release `48ff67d` subsequently passed the reusable public checker:
  health200/ok, password-type gate and matching `48ff67da9318` revision using normal
  TLS, without credentials. See the
  [implementation release evidence](assets/render-implementation-verification.json).
  A final corrective push still needs its own revision check.
- The [first CI run](https://github.com/Aniruddh2708/AgenticAI/actions/runs/38692171843)
  failed workflow validation before jobs because `runner.temp` was in job-level
  `env`. Its expression is now in step environments; actual corrected Linux and
  Windows runs still require verification. The failed run measured no test result.

Use [Render instructions](RENDER.md), [validation history](VALIDATION.md) and
[handoff](HANDOFF_FOR_CLAUDE.md). The sanitized
[public release evidence](assets/render-release-verification.json) is included
with this blueprint. Local test-only evidence is under ignored
`.runtime/render-setup/`; public read-only evidence is under
`.runtime/blueprint-review/public-websocket-release.json` and `public-release.json`.
Neither local path is a public deployment endpoint.

## 8. Rules for the next implementation pass

Preserve concentration-before-missing-evidence priority, cash/sector/equity limits,
short-horizon and momentum-chasing guards, conflict handling, source checks,
`confidence_kind="evidence_strength"`, atomic persistence and explicit degradation.
Keep original synthetic simulations, user-edited profiles, dependency hashes and
frozen/spent research artifacts. Price research remains separate from synthesis.

A later contributor should verify terminal/HEAD/branch/status first, read this
status alongside original requirements and actual code, then take the next
unblocked item with its acceptance criteria. Distinguish measured evidence,
user reports, exploratory analysis and unverified capabilities. Preserve failed
results rather than manufacturing a better story.
