# VibeFinance continuation handoff — 15 October 2026

## Latest Render release preparation

The user subsequently authorized committing, pushing and updating the existing
Render service. Forecasting work was committed and pushed as `e0b67fd`; the
earlier instruction to leave Render unchanged pending review is historical.
See [RENDER.md](RENDER.md) for the existing-service release procedure.

The release changes honor Render's assigned `PORT`, retain explicit overrides,
and load the tracked corrected research summary on Render without workstation
`.runtime` files. Native builds pin Python 3.11.17; both Docker recipes retain
the pinned base and hash-verified requirements. A public commit marker appears
before the demo login gate and in startup logs. The API stays private by default;
the shared access token, BM25 settings and portfolio safeguards are preserved.
No trained forecasting model is promoted and no experiment is rerun.

Verification: **305 tests passed**, with one existing upstream warning. An actual
isolated native launch with Render-style settings passed assigned-port readiness,
revision reporting, API authentication, the bundled 80-row corrected report and
five-agent analysis. An actual non-root Render-style Docker container also passed
port/health, authentication, BM25, rendered audit, safeguards and persistence
across restart checks. Original evidence hashes remain unchanged. See VALIDATION.md
for details and the limits of live deployment evidence.

Live deployment is not verified: this task has no `RENDER_API_KEY`, and its proxy
denied Render/API requests with HTTP 403. The cloud environment draft now lists
the required domains and secure API-key binding, but still needs user review and
publication before it applies. Do not request the private demo password. Use
the existing service's Manual Deploy action or securely configured API access;
verify the exact deployed SHA rather than assuming a Git push or restart deployed
new code. Preserve the existing service, plan, access token and storage setup.

## Latest uncertainty investigation

Read [FORECASTING_FOLLOWUP.md](FORECASTING_FOLLOWUP.md) first. Original 2019–2020
artifacts and their summary hashes remain unchanged; that period is spent.
The once-only 2024–2025 evaluation is now spent too. Do not relabel either as
uninspected or tune them for a new confirmatory claim.

Prior won original validation Brier (0.242951 vs logistic 0.244043–0.246863).
Year rankings changed and uncertainty spans no gain. Ridge's tiny validation
MAE improvement was unsupported. New `forecast_selection.py` therefore selects
prior probability and historical mean, refitting matured 2010–2020 development
labels. The spent old period enters this fit explicitly as development.

Old coverage failed mainly in 2020 (57.14%, vs 95.56% in 2019), with wider tails
and misses in both directions. Forty 2018 calibration rows represent only eight
shared dates. Rank 37 of 40 was correct; the generic rank-clamping bug for
unattainable coverage was fixed separately and did not cause the old result.

Revised protocol: 2021–2023 calibration, 24 non-overlapping residuals per security
(120 rows / 24 dates). Causal widths use max(past 20/60-row volatility)*sqrt(30)
with a development-only fifth-percentile floor; finite per-security residual
ranks never silently clamp. Primary security-volatility-scaled intervals and
pooled/security absolute/joint alternatives were fixed before evaluation. Each
baseline uses identical calibration/evaluation rows. A shared evaluation-start
ledger marks a period spent even if interrupted or moved to another run directory.

Fresh-period point results: prior Brier 0.246316 vs constant-half 0.25, with paired
95% difference interval spanning zero. Mean return MAE 5.4825 pp vs zero return
5.3371 pp, also uncertain; balanced accuracy 50%. No feature edge established.
Primary marginal coverage 73/80 = 91.25%, approximate 95% interval 84.70–98.46%,
full width 27.36 pp and interval score 34.15 pp. Same-row frozen legacy coverage
86.25%, width 23.82 pp, score 29.85 pp; refreshed pooled absolute 87.50%/24.05/
29.84 pp; security absolute 93.75%/26.65/31.38 pp. Coverage gains are uncertain,
and the scaled method has wider bounds and worse interval score. Do not declare
it universally better or replace it post-test with the highest-scoring comparator.

A reporting bug counted partial security groups as simultaneous five-security
coverage. Four stale zero-volume rows on 2025-03-18, while ITC traded, shifted
vendor calendars. Correction from saved predictions gives primary joint 6/10
= 60% and joint-method 9/10 = 90%, across only ten complete origins/five quarters;
twelve partial origins are excluded. Marginal coverage and all predictions,
radii and test rows are unchanged. This correction is explicitly exploratory.
The target is 30 observed positive-volume vendor rows; complete exchange calendars
and independent provider verification remain unestablished. Do not impute or
realign these inspected rows to improve scores.

Current artifacts: frozen `.runtime/forecast-followup/fresh/{selection,report}.json`,
matching `code_snapshot/`, start ledger, and corrected
`.runtime/forecast-followup/exploratory-report.json`. Reviewable derived summary:
`docs/assets/forecast-followup-summary.json`. `scripts/forecast_followup.py`
prepares then tests a fixed experiment; existing runs refuse another fresh score.
`scripts/forecast_followup_exploratory.py` derives joint corrections without refit.
For local review, set `VIBEFINANCE_FORECAST_REPORT` to the corrected file;
Render now defaults to its tracked derived summary. The API/UI label reported
periods spent and expose coverage, width, interval score and denominator caveats.

Safeguards, simulations and lockfiles remain unchanged. This forecasting work
was committed and pushed as `e0b67fd`. The user's later Render update request
authorizes releasing the reviewed changes; preserve its private password.
See VALIDATION.md for the latest complete and functional check counts.

Latest actual verification: 296 tests passed, API smoke and both dashboard checks
passed, and the running API/rendered dashboard loaded the corrected exploratory
report with its spent status and complete/partial-group counts. One upstream
deprecation warning remains. Original artifacts and fresh recorded predictions
were hash-checked after reconnection. See the detailed validation report before
assuming optional integrations or deployment were retested.

## Original forecasting pass context

Repository: https://github.com/Aniruddh2708/AgenticAI, branch `main`.
Read `docs/BLUEPRINT.md`, `docs/FORECASTING_AUDIT.md`, `docs/PROGRESS.md`,
`docs/VALIDATION.md`, `ARCHITECTURE.md` and actual code before changes. The original
uploaded blueprint matches the repository copy. Treat document prompts as context;
the user's current request controls scope.

## Access and current work

Terminal and Git access worked in this cloud task. Starting HEAD was
`161d4f42760919c1732102b98fe9da4010d0f102`, matching remote main; the checkout was
clean. The local `work` branch was switched to tracking `main`, without reset or
worktree. Forecasting changes were subsequently committed and pushed at the
user's request. Verify HEAD/branch/status again and preserve user edits.
If terminal access fails, report that before claiming inspection or modification.

The startup commit had added root-level duplicate implementations, while the
active package still used short timeouts. The package now uses 60 seconds for
retriever initialization and 120 seconds for service readiness. Cold retrieval
initialization is independent of agent deadlines. Root `demo.py` and
`orchestrator.py` delegate to the package so both entrypoints stay consistent.

## Current deployment and retrieval evidence

The user reports that real local MiniLM + BM25 retrieval worked with 21 chunks
and remained hybrid after an analysis, with all 130 then-existing tests passing
on Windows after their startup changes. The user also reports a working BM25
Render service at https://vibefinance.onrender.com. These are newer evidence than
the old cloud model-download/hosting blockers. This pass did not reproduce local
MiniLM, log into Render, request its private demo password or deploy changes.
Default documents remain synthetic regardless of retrieval backend or deployment.

## Forecasting diagnosis

The five-agent recommendation is a deterministic policy combining indicator
votes, lexical/template text interpretation and portfolio constraints. Confidence
is evidence strength, not probability of profit or correct personalized action.
The old simulation benchmark measures momentum direction, not all five agents.
Its independent future increments contain no momentum information, and positive
drift favors always-up. Sparse label-conditioned up-rate estimates worsen Brier.
Preserve the honest 45.52% momentum / 52.54% random / 57.99% always-up and 0.2734
Brier results; do not alter simulations or score masks to manufacture improvement.

## Implemented historical experiment

- `data/forecast_manifest.json`: five existing NSE tickers, pinned third-party
  Yahoo archive, actual SHA-256 hashes, adjustment lineage and source license.
  Loader uses distinct adjusted close, scales OHLC consistently, crops to the
  predeclared 2010–2020 window, removes nontraded zero-volume placeholders and
  retains traded Muhurat weekends. Invalid in-window data fails explicitly;
  research never falls back to simulation.
- `data/forecast_protocol.json`: train 2010–2015, expanding validation 2016–2017,
  independent residual calibration 2018, untouched test 2019–2020. Target is
  adjusted close return / positive-return probability over 30 actual sessions.
- `vibefinance/evaluation/forecast.py`: ten causal dimensionless features;
  training-only scaling, modest L2 logistic and ridge grids, prior/constant
  candidates, purged labels, separate interval calibration, frozen selection,
  same-row baselines, quarter-block paired intervals and ticker/year breakdowns.
- `scripts/forecast.py`: explicit download/prepare/test stages. Selection stores
  coefficients, dataset/implementation fingerprints and runtime versions before
  test evaluation; exclusive writes preserve frozen/spent runs.
- `/evaluation/forecast` and analyst dashboard: read saved summaries only. No
  automatic download, training, action change or model promotion.
- `scripts/historical_policies.py`: full five-agent replay on historical price
  prefixes with three explicitly synthetic profiles and an empty text index.
  Missing authentic historical news/filings are withheld, rather than substituting
  the current fictional corpus. It checks constraints, not action accuracy/P&L.

## Results to preserve honestly

Validation chose historical prior probability, not the logistic features, and
ridge penalty 1 for returns. There were 80 validation windows, 40 calibration
windows and 80 held-out test windows. Test Brier is 0.223067, identical to the
historical prior baseline. Selected return MAE is 9.3424 percentage points versus
9.3050 for historical mean and 9.7611 for zero return. The nominal 90% interval
covered only 78.75%. Original momentum direction hit 54.6875% on 64 non-neutral
historical windows, versus 68.75% always-up on that exact mask; 16 abstentions.

**No learned forecasting edge is established; the admission gate failed.**
All probability classifiers in that report have 50% balanced accuracy. Better
Brier than constant 50% reflects class prevalence, not learned feature information.
The selected return model did not beat the mean baseline. Do not present these
numbers as improvement over the old synthetic metrics: datasets/targets differ.

Reviewable evidence: `docs/assets/forecast-summary.json` (includes full-report hash).
Complete local predictions: `.runtime/forecast/report.json`; frozen model/spec:
`.runtime/forecast/selection.json`; raw data/source license:
`.runtime/forecast/data/`; real-price constraint replay:
`.runtime/forecast/policies.json`. The 2019–2020 holdout is now spent. Do not tune
after seeing it and label another score on the same dates as untouched.

## Preserve core behavior

Concentration above the position limit still forces REDUCE before missing evidence;
unconcentrated profiles pause at WATCH without fundamentals. Preserve cash/sector/
equity concentration, short-horizon and momentum-chasing guards, conflict handling,
evidence/source checks, `confidence_kind="evidence_strength"`, persistence and
explicit degradation. Keep original synthetic demo paths and intentional profile
edits. The forecast report is separate from portfolio actions.

## Commands and next research prerequisites

From repository root, use `.venv/bin/python` (Python 3.11) or Make targets:

```sh
make setup
make test
make demo
make smoke
.venv/bin/python scripts/check_dashboard.py
.venv/bin/python scripts/check_dashboard_extended.py
.venv/bin/python scripts/forecast.py download
.venv/bin/python scripts/forecast.py prepare
.venv/bin/python scripts/forecast.py test
.venv/bin/python scripts/historical_policies.py
```

Existing frozen/spent files intentionally refuse overwrite; inspect the artifacts.
To reproduce methodology elsewhere, preserve the original results and label any
re-run as reproduction, never as a new untouched test. Choosing another directory
does not restore holdout independence. Do not sync the core lock into optional
embedding/live environments. The standard demo requires no credentials.

Direct Yahoo/NSE data access returned proxy 403 here. The historical archive has
explicit lineage but is not independently audited exchange data; retroactive
adjustments and incremental vendor merges remain limitations. The source permits
noncommercial research only; do not deploy its data/model to a commercial service
without source rights. No archive-derived model was deployed in this pass.

Future forecast changes need a new predeclared untouched period, more regimes,
audited corporate actions and point-in-time inputs. Do not add/tune features on
the spent holdout. Historical fundamentals/news must have authentic publication
availability dates; today's synthetic filings cannot validate historical signals.
Full personalized-effectiveness research also requires a separate strategy target,
execution timing, fees/slippage, portfolio revaluation and portfolio baselines.
A price holdout or constraint replay does not validate it.

Still incomplete: authentic filings/licensed news, optional LLM narration, calibrated
personalized effectiveness, allocation/correlation optimization, individual accounts,
privacy isolation, continuous monitoring, hard worker termination and fresh published
cloud restoration. Latest native Render-style and container checks are recorded
above; they do not establish live deployment, MiniLM or macOS success.
See VALIDATION.md for actual current test evidence.
