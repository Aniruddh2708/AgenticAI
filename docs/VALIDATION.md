# Current follow-up validation — 15 October 2026

The original 2019–2020 and once-only 2024–2025 forecast reports are preserved.
Both periods are spent. The corrected joint-denominator view is explicitly
exploratory, derived from identical saved predictions, radii and rows.

| Latest check | Actual result |
|---|---|
| Terminal/workspace/Git after reconnection | Working on main at `161d4f4`; prior changes preserved; original result hashes verified |
| Complete suite `make test` | **296 passed**, one existing Starlette/AnyIO deprecation warning |
| Stability-aware selection | Original causal validation reconstructed; prior/mean retained because feature gains were unsupported |
| Uncertainty invariants | Finite-rank failure, no future labels in preparation/bounds, training-only floor, separate per-security units, target non-overlap and same-row metric arithmetic |
| Spent-period protection | Evaluation-start ledger persists on scoring failures; another output directory cannot make the fixed period fresh |
| Joint denominator | Partial stock groups excluded, complete denominator recorded; no complete group means unavailable |
| Original evidence preservation | All original artifact/summary hashes unchanged; fresh report matches exploratory source hash and has identical prediction rows |
| Revised frozen evaluation | 80 observations, 24 calibration dates/120 rows; primary marginal coverage 91.25%, no supported predictive advantage |
| Running API smoke | Passed in isolated state on owned alternate ports; safeguards, claims, source matching, persistence and demo scenarios intact |
| Dashboard scripts | `check_dashboard.py` and `check_dashboard_extended.py` passed |
| Actual exploratory report via API/dashboard | Loaded 80 marginal rows, 10 complete origins, 12 partial exclusions; correction/spent status visible; no model promotion |
| Deployment/dependencies | Render, simulation, synthesis safeguards and lockfiles unchanged; no push or deployment |

The primary interval has approximate shared-quarter 95% coverage interval
84.70–98.46%. Its 27.36 pp full width and 34.15 pp interval score exceed the
matched-point refreshed pooled comparator's 24.05 pp and 29.84 pp. Coverage gain
is 3.75 pp with paired interval -2.50 to +12.86 pp; superior interval quality is
not established. Point Brier/MAE differences versus constant-half/zero baselines
also span zero. Per-security/year tables, source defects, complete-group joint
counts and limitations are in [FORECASTING_FOLLOWUP.md](FORECASTING_FOLLOWUP.md)
and [its derived summary](assets/forecast-followup-summary.json).

The original recorded fresh report retains its erroneous available-group joint
metric for traceability. Use `.runtime/forecast-followup/exploratory-report.json`
for the corrected denominator: primary 6/10, wide joint method 9/10, only five
quarters represented. Marginal coverage remains 73/80. No dates were realigned
and no forecasts/radii were revised after scoring.

# Original forecasting pass — 14 October 2026

This section records the forecasting pass actually run in this Linux/Python
3.11.17 cloud task. Older evidence is retained below and is not a claim that
container, neural-model or deployment checks were repeated.

| Current check | Result |
|---|---|
| Terminal/workspace/Git | Working; clean starting HEAD `161d4f4` matched GitHub main; local branch switched from work to main before coding |
| Complete suite `make test` | **197 passed**, one upstream Starlette/AnyIO deprecation warning |
| Startup regressions | Active 60-second retriever / 120-second launcher deadlines; cold initialization independent of agent timeout; root wrappers use package implementation |
| Historical artifact download | Five pinned Parquet files and source license fetched with TLS and exact SHA-256 checks; repeat download reused verified cache |
| Study data quality | 2,713 in-window rows per ticker, 2,711 traded sessions after uniform zero-volume exclusion; invalid values/dates fail rather than silently repair |
| Causal research tests | Future-mutation invariance, 30-session target alignment, purged boundaries, declared train gaps, frozen data/implementation identity, manual baseline metric arithmetic |
| Historical price experiment | Frozen train/validation/calibration selection evaluated once on 80 held-out 2019–2020 windows; **admission gate failed** |
| Historical full-agent replay | 80 real-price windows, 240 correlated synthetic-profile decisions; zero violations of all listed checks; 80 REDUCE, 160 WATCH |
| Running API smoke | Personalized synthetic scenarios, supported claims, source matching, concentration priority, persistence and evaluation passed on isolated state/alternate ports |
| Rendered dashboard scripts | Both `check_dashboard.py` and `check_dashboard_extended.py` passed |
| Actual saved report via running API/UI | Endpoint summarized 80 test windows, stripped rows and preserved failed gate; actual dashboard loaded report without exceptions |
| Existing files/state | No initial user changes; source/dependency locks and existing demo profiles preserved; testing services used isolated state |

The selected probability is the historical prior baseline; logistic features did
not win validation. Selected return ridge MAE is **9.3424 percentage points**,
versus **9.3050** for historical mean. Brier **0.223067** equals the prior baseline,
versus **0.25** for constant half. These classifiers have 50% balanced accuracy.
Nominal 90% intervals covered **78.75%**. Original momentum direction hit 54.6875%
on 64 non-neutral windows; same-mask always-up hit 68.75%, with 16 neutral
abstentions. No learned predictive edge or improved personalized effectiveness is
established. See [FORECASTING_AUDIT.md](FORECASTING_AUDIT.md) for protocol, paired
uncertainty, source limits and [machine-readable summary](assets/forecast-summary.json).

The raw archive explicitly preserves Yahoo `Adj Close`; it is a third-party,
noncommercial-research source, not independently cross-checked exchange truth.
Direct Yahoo/NSE requests failed proxy HTTP 403. Data from before 2010 and after
2020 is excluded by the predeclared study window before feature construction;
questionable pre-IPO TCS observations and out-of-window source missing values are
not silently repaired or used. The 2019–2020 holdout is now spent.

The full-agent replay deliberately withholds historical filings/news and uses
static synthetic profiles. It verifies missing-evidence and portfolio behavior,
not recommendation accuracy, investment returns or a trained five-agent model.
Local artifacts are `.runtime/forecast/{selection,report,policies}.json`; raw files
and attribution/license remain ignored under `.runtime/forecast/data/`.

Newer user-reported evidence: all original 130 tests passed on Windows, real local
MiniLM+BM25 worked with 21 chunks and stayed hybrid after analysis, and the BM25
service at https://vibefinance.onrender.com works. This pass did not reproduce
MiniLM locally or log into/deploy Render, and did not request the private password.
Container builds/checks, live Yahoo success, native macOS and fresh cloud
publication/restoration were not rerun or established by this pass.

# Earlier corrective-pass evidence

Core validation was executed in the cloud Linux/Python 3.11.17 instance. Statements
below distinguish tests, actual integrations and blocked external capabilities.
Synthetic results do not demonstrate investment suitability or profitability.

## Core checks

| Check | Observed result |
|---|---|
| `make setup` | Repeated successfully; all 52 core packages checked against hash-pinned lock |
| `make test` | 130 passed; one upstream Starlette/AnyIO deprecation warning |
| `make smoke` | Functional API scenarios, concentration priority, claim/source matching, persistence and evaluation passed |
| `scripts/check_dashboard.py` | Running-service interaction checks passed |
| `scripts/check_dashboard_extended.py` | Real TestClient API + rendered Streamlit checks passed |
| Graceful service restart | Owned launcher stopped and both services restarted successfully |
| Entire corpus unavailable | Actual alternate-port launcher starts degraded; five-agent WATCH result saves with two degraded textual agents |
| Claim adversarial regressions | Forged classifications, altered numbers/scores, duplicates, orphan/empty evidence and unsupported substitutions rejected |
| Upstream/storage regressions | Retrieval initialization/query/timeout, malformed corpus, market failure, database failure and rollback paths exercised |

Dashboard checks include profile edit/create, stale-cache refresh, bad input, source
highlighting/HTML escaping, beginner/analyst display, failed route handling, inline
unsaved sources, disabled decisions and shared-password login. The tests use their
own temporary databases and synthetic credentials; they do not overwrite demo profiles.

## Quantitative results

Technical evaluation uses 12 independent seeds, 60 paths and 1,080 windows without
the demo's injected trends. It scores 826 directional observations and separately
counts 254 neutral abstentions:

| Forecast / probability model | Measured value |
|---|---|
| Momentum directional accuracy | 45.52% |
| Seeded random direction | 52.54% |
| Always-up direction | 57.99% |
| Empirical label-conditioned probability Brier score | 0.2734 |
| Constant 0.5 probability Brier score | 0.2500 |
| Prior unconditional probability Brier score | 0.2652 |
| Momentum 95% seed-cluster accuracy interval | 43.05–47.98% |

There is no predictive advantage demonstrated. Probability calibration concerns the
next 30-session positive-return event, fitted only from matured earlier windows on
that path. It is not calibrated confidence in the personalized recommendation.
The calendar blocks identify artificial paths rather than actual market history.

Full-agent dated synthetic replay: 90 profile decisions over 30 market windows.
Five-agent/date-visibility checks passed 90/90; concentration precedence and cash
interpretation checks passed 30/30 each. Actions: ACCUMULATE 14, AVOID 3, HOLD 40,
REDUCE 33. These are correlated profile decisions, not independent trades. No
transaction simulation, costs or demonstrated action profitability was measured.

One final nine-repeat warm benchmark measured median compute times of 21.26 ms
parallel and 20.59 ms sequential: 0.968× sequential/parallel ratio, with paired
bootstrap interval 0.916–1.053×. Inputs and outputs matched; no artificial delays
were introduced. No useful speed advantage is established. HTTP, persistence,
downloads and cold-start work are excluded; host scheduling makes timings variable.

## Optional and container integrations

| Integration | Actual evidence |
|---|---|
| Core BM25 | Actual offline queries and filters passed |
| CPU embedding dependency environment | Installed successfully in isolated ignored environment |
| Real Chroma storage/query/filtering | Passed with explicitly labeled fixture vectors |
| Real MiniLM hybrid retrieval | Earlier cloud run unverified (HTTP 403); later local success reported by user as described above |
| Live Yahoo | **Not verified**; fc.yahoo.com returned CONNECT 403; strict check exited 1 |
| Yahoo fallback | Seeded 300-row frame validated successfully |
| Standard online Docker build | Failed at this host's build-container DNS/proxy access |
| Verified offline-wheel Docker build | Succeeded with pinned base image and required artifact hashes |
| Container behavior | Non-root, dashboard health, private API, API/password gate, five agents and persistence across restart passed |
| Public hosted URL | Not deployed in that earlier pass; later working BM25 Render deployment reported by user |
| Native macOS / fresh published cloud task | **Not independently validated** |

No TLS, package hash or image verification was disabled. Network requirements were
saved to the environment draft, which does not apply or publish them. See
[INTEGRATIONS.md](INTEGRATIONS.md) for precise commands and domains.

Final locally built image digest:
`sha256:353f4ef5c8be964154f05e132040adb03e8f99b03af81f6e43bc7cf1b5ac62bb`.
The seven container checks passed again after the last source changes. This image
was not published to a public registry; the recipes rebuild it from the repository.

## Presentation and backup delivery

The self-contained [PRESENTATION.html](PRESENTATION.html) deck was browser-checked
for eight slides, navigation and absence of JavaScript errors. A printable eight-page
PDF and title screenshot were rendered from the actual deck. Twelve dashboard
screenshots and a silent 119.3-second recording were generated from 305 observed
Chromium screen frames. The capture reported zero browser JavaScript errors.
They show synthetic data only and do not constitute a narrated rehearsal.

- [Presentation PDF](assets/VibeFinance-presentation.pdf)
- [Dashboard backup video](assets/demo/dashboard-backup.mp4)
- [Asset inventory and scope](assets/README.md)
- [Capture manifest](assets/demo/manifest.json)
- [Highlighted source passage](assets/demo/02-sources.png)
- [Three-profile comparison](assets/demo/04-comparison.png)
- [Evaluation screenshot](assets/demo/05-evaluation.png)
- [Calibration screenshot](assets/demo/05-calibration.png)

The capture script uses actual Chromium CDP frames and installed system FFmpeg.
Playwright's bundled FFmpeg download was blocked, so that download is not advertised
as installed. The generated video is not a slideshow substituted for live screen frames.

## What remains unimplemented or incomplete

- Real neural retrieval and BM25 hosting now have newer user-reported success;
  live Yahoo success remains unverified in this cloud task.
- Optional LLM narration, authentic filing/PDF ingestion and licensed real news.
- Comprehensive financial-language interpretation or general semantic entailment.
- Calibrated personalized-action success, real-history strategy evaluation, costs,
  portfolio revaluation, correlation optimization and demonstrated investment edge.
- Individual accounts, privacy isolation, production audit/security/regulatory work.
- Continuous watchlist monitoring/notifications; alerts currently require a scan.
- Hard termination/isolation of timed-out worker threads.
- Native macOS/fresh cloud restoration and a narrated rehearsal.

The complete continuation prompt is [HANDOFF_FOR_CLAUDE.md](HANDOFF_FOR_CLAUDE.md).
