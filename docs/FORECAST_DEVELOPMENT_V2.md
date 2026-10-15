# Bounded forecasting development v2 — 15 October 2026

This is **exploratory development**, with stronger causal candidates and an
explicit failed admission decision. No new historical holdout was opened, no
prospective forecast was issued, and no predictive advantage is established.
The original experiments and their failed/uncertain results remain unchanged.

Starting terminal-verified checkout and remote main:
`ed7a5f4602fa2b241847b366f91e2ff2229500eb` (the dashboard merge after `a14df5d`).
The checkout was clean, with no repository AGENTS.md found. Work uses feature
branch `codex/credible-forecast-development`; Render settings/service are unchanged.
[Review the branch](https://github.com/Aniruddh2708/AgenticAI/compare/main...codex/credible-forecast-development).

## Data identity, quality and boundaries

The original [source manifest](../data/forecast_followup_manifest.json) remains
frozen. Five files from `aswinv90/indian-market-historical-data` commit
`5dffc0832c63d1558930510d081e076929608d82` were downloaded through verified HTTPS
and matched all pinned SHA-256 hashes, including the license. This is the same
Yahoo/yfinance lineage, not another independent provider. Its license allows
noncommercial research/personal use and requires separate permission for commercial
use. Its [exact license and attribution](licenses/FORECAST_ARCHIVE_LICENSE.txt)
accompany the derived numerical inventory; this does not certify upstream exchange
rights. No raw file or trained archive model was deployed or redistributed here.

Securities remain RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS and ITC.NS. This is a
five-survivor convenience universe, not historical index membership. Historical
ISIN mappings and corporate-action vintages are not independently established.

The new [versioned quality inventory](assets/data-quality-development-v2.json)
records raw artifact identities, numeric validity, observed calendars, adjustment
factor changes, reported dividend/split events, exact exclusion dates and outstanding
independent evidence. Each file has **3,454 observations in 2010–2023** and **3,452
positive-volume rows** (observed 2010-01-04 through 2023-12-29). The existing uniform policy excludes 2014-04-24 and
2014-10-15; the original rows remain unchanged. No missing price or calendar is
filled. Positive-volume weekend sessions are retained. Counting vendor rows does
not establish a complete exchange calendar. Missing older special sessions and
retrospective adjustments remain unresolved. The prior two official NSE samples
are recorded as partial historical evidence, not reacquired or promoted to full
approval. Source terms still prevent an unauthorized bulk NSE collection.

The [frozen protocol](../data/forecast_development_v2_protocol.json) inventories
all previously inspected periods **before** this run:

| Role | Dates / construction |
|---|---|
| Initial training | Origins from 2010, labels matured strictly before 2014-01-01; 120-row feature warmup |
| Expanding development | 2014, 2015, 2016, 2017 separately; each year's labels mature within that year |
| Final point refit | Eligible 2010–2017 labels only; final matured label by 2017-12-31 |
| Separate calibration | 2021-01-01 through 2023-12-31; previously inspected follow-up calibration, never a fresh test |
| Unused former calibration | 2018 |
| Spent evaluations excluded from fitting/selection/calibration labels | 2019–2020 and 2024–2025 |
| New evaluation | None; no uninspected historical period is asserted |

The main target remains **30 positive-volume vendor observations**, adjusted
close-to-close return after observing the origin close; positive-return probability
is a separate target. It is not guaranteed to equal 30 complete exchange sessions,
and it is not executable trading P&L. Current/past adjusted OHLC and volume alone
supply features. Calibration's trailing features may use earlier observed prices;
spent evaluation labels never select or fit candidates. Both numerator and
denominator use the same pinned vendor vintage. No text/fundamental features are
introduced without actual historical availability evidence.

Each development fold has 40 rows / eight shared origins (eight per security),
so the combined comparison has **160 rows, 32 origins and 16 calendar quarters**.
First/last origins and last target by fold:

| Year | First origin | Last origin | Last target | Stride-5 train rows |
|---|---|---|---|---:|
| 2014 | 2014-01-01 | 2014-11-17 | 2014-12-30 | 840 |
| 2015 | 2015-01-01 | 2015-11-06 | 2015-12-23 | 1,085 |
| 2016 | 2016-01-01 | 2016-11-10 | 2016-12-23 | 1,330 |
| 2017 | 2017-01-02 | 2017-11-07 | 2017-12-19 | 1,575 |

Labels crossing boundaries are purged. Training samples every five rows; scoring
every thirty rows avoids overlapping targets within each security. No additional
embargo is used because training labels mature strictly before the next fold.
Dependence remains across stocks and nearby origins; row counts are not IID trials.
Missing feature/peer rows and exact eligible cohorts are retained in the complete
report. The command refuses incomplete planned development/calibration cohorts.

## Implemented candidates and results

Eighteen dimensionless features have individual rationales in the saved report:
1/5/20/60/120-row momentum, downside semi-deviation, drawdown, intraday range,
volume and relative-illiquidity changes, volatility regimes, and same-date peer
returns. The other four stocks form a convenience peer basket, **not** a market
index. Only TCS/INFY have another IT stock; other sector-relative values have an
explicit unavailable flag. A missing peer row is excluded, never forward filled.
Training-only median/scale and fixed standardized clipping precede fitting.

The bounded search is two L2 logistic penalties, one fixed ridge, one Huber
regression and fixed 24-round decision-stump gradient boosting for each target.
No new model dependency is needed. Baselines include half, training-only prior,
always-up direction, zero/mean returns and train-fitted momentum-label forecasts.
Candidates use identical dates, securities, targets and exclusions.

| Probability method | Brier | Log loss |
|---|---:|---:|
| Constant half (retained) | 0.250000 | 0.693147 |
| Training prior | 0.252237 | 0.697985 |
| Momentum-label probability | 0.252162 | 0.698110 |
| Logistic L2 0.1 | 0.246625 | 0.686255 |
| Logistic L2 1 | 0.249493 | 0.692133 |
| Constrained stump logistic | 0.249327 | 0.691818 |
| Always-up probability | 0.450000 | 9.325470 |

Probability ties use >= 0.5, so half and always-up classify identically: 55%
accuracy / 50% balanced accuracy. Logistic 0.1 has 55.625% accuracy / 51.073%
balanced accuracy. It wins three years and loses 2014. Half is a probability
baseline, not a sampled random trading strategy. Log loss clips at 1e-9.

| Expected-return method | MAE (return pp) | RMSE (return pp) |
|---|---:|---:|
| Zero | 5.7390 | 7.2113 |
| Training mean | 5.6956 | 7.0155 |
| Momentum-label mean (retained) | 5.6757 | 6.9681 |
| Ridge L2 1 | 5.5661 | 6.9395 |
| Huber L2 1 | 5.5796 | 6.9410 |
| Constrained stump squared-error | 5.5932 | 6.9227 |

Ridge wins three years but loses 2017. Its point gain does not earn admission.
Selection requires paired shared-quarter upper loss-difference bounds below zero
against **every** appropriate baseline and at least three winning folds. Within
each target family, Bonferroni covers three candidates × three baselines;
per-comparison alpha is 0.05/9. Probability and return are two separately disclosed
families; these are conservative development screens, not confirmatory p-values.

Logistic 0.1 minus half Brier: **-0.003375**, adjusted interval **[-0.023922,
+0.019007]**. Ridge minus the strongest return baseline MAE: **-0.1096 pp**,
adjusted interval **[-0.2724, +0.0752 pp]**. Both include zero. The complete
summary supplies all comparisons, ordinary descriptive 95% metric intervals,
reliability bins, securities, years/folds and causally labelled regimes. Bootstrap
uses 2,000 draws, seed 2708, sampling stocks jointly by calendar quarter. Sixteen
quarters still provide weak support; adjacent-quarter dependence and selection
optimism remain. No parameter search followed these results.

The selected development baselines differ from earlier experiments because the
folds/training sampling and baseline set differ. They do not replace the frozen
prior/mean prospective protocol or old reported results. **No model is admitted.**

## Calibration and uncertainty

The primary comparator was fixed as pooled absolute residuals. Per-security
volatility-scaled and joint date-max intervals are declared comparators. Development
residuals update only after target maturity, using at most the past 24 origins;
first-fold training freezes the scale floor. The first ten origins lack nine strictly matured earlier calibration dates
and are excluded explicitly, identically across interval methods. This leaves **110 rows / 22 complete origins / 12 quarters**.
Point-model selection on these development folds is exploratory: this is not an
independent interval validation.

| Development interval | Marginal coverage | Width (return pp) | Proper score (pp; lower better) | Simultaneous complete-origin coverage |
|---|---:|---:|---:|---:|
| Pooled absolute (primary) | 91.82% | 23.58 | 27.02 | 14/22 = 63.64% |
| Security volatility-scaled | 92.73% | 26.91 | 30.38 | 16/22 = 72.73% |
| Joint date-max volatility-scaled | 99.09% | 34.12 | 35.13 | 21/22 = 95.45% |

Primary marginal coverage has an approximate shared-quarter 95% interval
**88.14–95.79%**. Width and score disclose the cost of coverage; wider intervals
are not a free improvement. Per-security coverage is in the artifact; e.g. scaled
TCS coverage is only 81.82% over 22 observations. Marginal coverage does not imply
security-specific or simultaneous coverage. Partial origins never enter a joint
denominator. Exchangeability and stable financial regimes are not assumed.

After point selection, the same frozen model is separately calibrated on the
previously inspected 2021–2023 data: 120 rows / 24 complete origins. The 90%
security/joint rank is 23/24; pooled rank is 109/120, with only 24 shared dates.
No outcome is scored as a new test and no interval method is selected on that
calibration. The 2017 point-model cutoff and calibration ending 2023 deliberately
produce a **stale historical research snapshot**, not a forecast for today's market.

## Application and performance

The authenticated `/evaluation/forecast/development` endpoint reads a saved,
identity-checked report only. Metrics → Historical forecasting research displays
model identity, historical as-of time, horizon, age, baselines, uncertainty and
failed admission. It never trains or changes recommendation actions. The old
forecast report remains separate. All concentration/cash/equity/sector/horizon/
behavior guards and `confidence_kind=evidence_strength` remain intact.

Profiling found repeated indicator computations in the orchestration/agent/
canonical-check paths. One immutable, independently computed snapshot now feeds
both market agents and their canonical checks; labels/claims are still regenerated
and adversarial claims rejected. Direct agent calls still compute/validate inputs.

[Actual local performance evidence](assets/performance-development-v2.json) uses
seven repeats per mode, alternating order, explicit warmup and identical-output
checks. Four tickers cover personalization, conflict, seeded outage and missing
filing; a 20× synthetic corpus is a separate load fixture. Before optimization,
parallel medians were 20.77–30.22 ms; afterward 5.21–10.68 ms. SQLite-backed in-process
HTTP median changed from 38.77 to 23.73 ms. These sequential runs have scheduling
noise; no universal speedup or hosted-throughput claim follows. Afterward,
sequential/parallel ratios are only 1.02–1.10. Thread dispatch is not the main gain;
removing redundant arithmetic is. No artificial delay was inserted.

## Reproduce and continue

From the existing checkout, with Python 3.11.17 and the saved environment setup:

```bash
.venv/bin/python scripts/develop_forecast.py download
.venv/bin/python scripts/develop_forecast.py run --run-dir .runtime/forecast-development/reproduction-NEW
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_production_storage.py
.venv/bin/python scripts/benchmark_workloads.py --repeats 7 --output .runtime/performance-NEW.json
VIBEFINANCE_EMBEDDINGS=0 .venv/bin/python -m vibefinance.demo
.venv/bin/python scripts/smoke.py
.venv/bin/python scripts/check_dashboard_extended.py
```

The run command exclusively creates its directory and freezes protocol/code
hashes before fitting. It produces registration, quality, full predictions and
summary. Repeat runs are **reproductions of inspected development**, never fresh
holdouts. The first development run and subsequent reporting/numerical-order
reproduction remain under ignored `.runtime/forecast-development/`; neither old
holdout was rescored. The tracked summary includes the complete-report hash.

A new prospective cycle still requires genuinely authorized independently reconciled
prices, complete calendars/actions, equivalent adjustment vintages, actual rights
and universe review, and a witnessed registration before a future origin. Update
the proposed origin start before registration if it is no longer future. Then use:

```bash
.venv/bin/python scripts/run_prospective_cycle.py ready \
  --run-dir .runtime/prospective/baselines-v1 --inputs /authorized-data/cycle-inputs.json
.venv/bin/python scripts/run_prospective_cycle.py run \
  --run-dir .runtime/prospective/baselines-v1 --inputs /authorized-data/cycle-inputs.json
```

Those input files do not exist here. Follow [prospective operations](PROSPECTIVE_OPERATIONS.md)
for registration/witness/issuance/outcome commands. Wait for 30 verified closed
sessions after actual issuance; do not fabricate maturity or backdate. The existing
protocol's support requirements can take years. This development run does not
modify or register that protocol.
