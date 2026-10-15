# Forecasting investigation — 15 October 2026

The original 2019–2020 results remain byte-for-byte preserved. They are spent
development evidence, not a reusable test. The revised experiment was frozen
before opening 2024–2025 outcomes and evaluated once. Those dates are now spent
too. A subsequently discovered joint-coverage denominator error was corrected
from saved predictions in a separately labelled exploratory artifact; no point
forecast, calibration radius, outcome or evaluation row was changed.

## Why prior probability won

The original validation comprised 80 observations, but only 16 shared forecast
dates and eight calendar quarters. Each stock had eight non-overlapping windows
in 2016 and eight in 2017. Daily training targets overlap, and the securities
share market shocks, so raw training/test row counts overstate independent
information.

| Probability candidate | Validation Brier |
|---|---:|
| Historical prior | 0.242951 |
| Logistic, penalty 1 | 0.244043 |
| Logistic, penalty 0.01 | 0.246823 |
| Logistic, penalty 0.1 | 0.246863 |
| Constant 50% | 0.250000 |

All candidates use the same dates/outcomes. Prior had the lowest loss. Logistic
penalty 1 beat prior in 2016 (0.251234 vs 0.255987) but lost in 2017 (0.236852 vs
0.229916). Its aggregate Brier disadvantage was only 0.001091; the approximate
paired quarter-cluster 95% interval spans -0.0066 to +0.0078. There is no stable
evidence that the ten price/volume features improve probability forecasts.

The original return selection chose ridge penalty 1 by a tiny MAE difference:
0.056897 vs mean 0.057172. Its improvement is just **0.0276 percentage points**,
with paired 95% interval approximately **-0.3645 to +0.2621 pp** for ridge-minus-
mean loss. The revised rule lets a feature model replace the best baseline only
when its paired upper loss-difference bound is below zero with eight quarters.
Neither learned candidate qualified, so the revision keeps **prior probability
and historical mean return**. The comparisons are exploratory development
checks, not a new confirmatory claim about the inspected old periods.

## Why the original intervals missed

The original point model stopped fitting before 2018. Forty 2018 calibration
residuals represented **eight shared dates × five securities**, with only eight
residuals per security. The pooled 90% order statistic was correctly rank 37 of
40, giving a constant half-width of **11.9094 return percentage points** for all
securities and regimes. A correct order statistic does not make financial
residuals independent or exchangeable.

| Inspected original period | N | Coverage | Selected return MAE |
|---|---:|---:|---:|
| 2019 | 45 | 43/45 = 95.56% | 5.18 pp |
| 2020 | 35 | 20/35 = 57.14% | 14.69 pp |
| Entire original period | 80 | 63/80 = 78.75% | 9.34 pp |

The return standard deviation increased from about **7.30 pp** in calibration
to **13.57 pp** in the inspected test. Mean causal 60-row daily volatility rose
from 1.31% to 1.91%. The 2020-02-07 forecast origin covered zero of five outcomes;
its horizon includes the COVID drawdown. Rebound windows also breached the
bounds: misses were nine below and eight above overall. This is broader tails
and regime shift rather than a purely one-sided mean bias.

| Security | Original coverage (16 observations each) | Revised-period coverage (16 each) |
|---|---:|---:|
| HDFCBANK | 81.25% | 87.50% |
| INFY | 87.50% | 100.00% |
| ITC | 62.50% | 87.50% |
| RELIANCE | 68.75% | 87.50% |
| TCS | 93.75% | 93.75% |

These columns concern different periods and cannot establish improvement by
themselves. Both have only 16 observations per security. Pooled constant widths
also hide security-specific tail/volatility differences. The original aggregate
coverage has a descriptive quarter-bootstrap interval of approximately 61.3–
92.5%; eight time blocks do not permit precise coverage claims.

## Provenance, dates and construction

All five original Parquet hashes match the pinned
`aswinv90/indian-market-historical-data` commit
`5dffc0832c63d1558930510d081e076929608d82`. Cached fetch code uses Yahoo/yfinance
with `auto_adjust=False`, retaining distinct `Adj Close` and corporate actions.
Historical adjustment-factor changes match dividends; split dates do not show
an unexplained second split adjustment. No substantive double-adjustment,
future-feature leakage, target off-by-one or split-boundary overlap was found.

The loader scales OHLC by adjusted/raw close; forecasts target adjusted returns,
not nominal cash prices. Targets use **30 observed positive-volume vendor rows**.
The exchange calendar has not been independently verified, and expected older
Muhurat observations appear missing. Do not claim an exchange-complete session
calendar. Source hashes establish identity, not independent price accuracy.

The study's five existing, surviving stocks include two IT services names and
one bank, energy name and consumer name. This is not a point-in-time index
universe. It cannot establish broad market performance or personalized-action
effectiveness. Default filing/news documents remain fictional and are absent
from the forecasting experiment.

Original inputs: 2,713 rows per security during 2010–2020, two excluded zero-volume
rows, 2,711 observed traded rows. Original final fitting used 9,255 overlapping
daily labels across 1,851 shared origins, all matured by 2017-12-29. Original
calibration matured by 2018-12-21; original evaluation ended at 2020-12-11.
These are actual boundary checks, not random train/test splits.

The extension's raw 2021–2025 calendars have 1,236 dated rows per security before
zero-volume exclusions. The archive was created in September 2026, so the entire
extension predates its later five-day incremental-update boundary. Retrospective
vendor adjustments, questionable pre-IPO TCS history (excluded by the 2010 start),
and unavailable independent Yahoo/NSE cross-checks remain limitations. The source
license allows noncommercial research; no archive-derived model was deployed.

## Substantiated fixes and revised protocol

1. **Unsupported finite quantiles fail.** The generic original implementation
   capped required ranks at `n`. For example, 20 residuals cannot support its
   requested 99% finite bound. It now rejects unattainable ranks. This bug did
   not cause the original 78.75% result: rank 37 of 40 was supported.
2. **Baseline preference reflects uncertainty.** Original expanding 2016–2017
   candidate predictions are retained as development evidence. Feature candidates
   must have a supported paired improvement; no model complexity is forced.
3. **Longer, separate calibration.** Point parameters refit on matured 2010–2020
   development labels, explicitly including the spent 2019–2020 period. Calibration
   uses 2021–2023, and future evaluation uses 2024–2025. Preparation crops inputs
   before constructing targets, so it does not even construct evaluation labels.
4. **Causal heteroscedastic widths.** Scale is the maximum of past 20/60-row daily
   volatility times square-root 30, floored at the development-only fifth percentile
   (5.5510 pp). Each security gets a separate finite rank on standardized absolute
   residuals. No future returns enter interval bounds. Twenty-four non-overlapping
   residuals per security give rank 23 of 24; temporal exchangeability is still
   unsupported, so nominal coverage is an empirical target, not a guarantee.
5. **Fair width/coverage comparisons.** Declare pooled absolute, security absolute
   and date-max joint standardized alternatives before scoring. Each point
   baseline has its own residuals on the identical calibration dates, using the
   same scale/floor rule. Report width and the proper interval score, which
   penalizes width and missed outcomes; simply inflating bounds cannot be called
   an unqualified improvement.
6. **Spent-period protection.** The selection freezes model, source, implementation
   and runtime identities. An exclusive shared evaluation-start ledger is written
   before consuming evaluation outcomes, including on interruptions. A different
   run directory cannot make that period fresh again.
7. **Complete groups for joint coverage.** A post-evaluation reporting error had
   treated partial stock groups as simultaneous five-stock coverage. The fix
   counts only complete origins, records the denominator and exclusions, and
   returns unavailable when no complete group exists. Its correction is labelled
   exploratory; original scores/predictions remain preserved.

## Once-only 2024–2025 result and identical-row comparisons

The revised fit uses **13,105 overlapping daily labels / 2,621 shared origins**,
all matured by 2020-12-31. Calibration is **120 residuals / 24 shared dates**;
each security has 24. The frozen point model predicts up probability 0.61906 and
mean adjusted return 2.2582% for this target; neither has feature discrimination.
Evaluation has **80 observations**, cutoffs 2024-01-01 through 2025-10-29, final
outcome 2025-12-11. Each security contributes 16; target-row exclusions produce
22 distinct origin dates, rather than 16 complete cross-sections.

| Same evaluation rows | Brier | Return MAE | Return RMSE |
|---|---:|---:|---:|
| Selected prior + mean / identical prior-mean baseline | 0.246316 | 5.4825 pp | 7.0657 pp |
| Constant 50% + unchanged price | 0.250000 | 5.3371 pp | 6.8973 pp |
| Train-fitted momentum-label probabilities/mean returns | 0.245280 | 5.5070 pp | 7.0756 pp |
| Original frozen prior + ridge, transferred to these rows | 0.245915 | 5.5762 pp | 7.1016 pp |

All methods classify up on these rows: accuracy 57.5%, balanced accuracy 50%.
Probability ties use `>= 0.5`; a 50% probability is not a sampled random signal.
The prior-minus-half Brier difference is -0.003684, with approximate paired 95%
interval **[-0.024519, +0.014175]**. Mean-minus-zero MAE is +0.1454 pp, interval
**[-0.1349, +0.5106 pp]**. No predictive advantage is established. The slightly
better zero-return result does not trigger selection on this spent evaluation.

| Same rows, interval method | Marginal coverage | Mean full width | Interval score (lower better) |
|---|---:|---:|---:|
| Original frozen 2018 interval + original point model | 86.25% | 23.82 pp | 29.85 pp |
| Selected mean, refreshed pooled absolute | 87.50% | 24.05 pp | 29.84 pp |
| Selected mean, refreshed security absolute | 93.75% | 26.65 pp | 31.38 pp |
| **Predeclared primary: selected mean, security volatility-scaled** | **91.25%** | **27.36 pp** | **34.15 pp** |
| Selected mean, date-max joint volatility-scaled | 98.75% | 42.78 pp | 44.06 pp |

Primary marginal coverage is **73/80**, with approximate shared-quarter 95%
interval **84.70–98.46%**. It gains 5.0 coverage points against the transferred
original method (paired interval 0–12.50 pp), with widths **3.54 pp larger** and
interval score **4.30 pp worse**, whose interval spans -1.05 to +9.41 pp.
That before/after comparison changes both point refitting and calibration.

The matched-point comparison isolates uncertainty: primary vs refreshed pooled
absolute gains **3.75 coverage points**, interval **[-2.50, +12.86 pp]**, widens
**3.32 pp** (interval 1.78–4.45), and worsens interval score **4.32 pp**, interval
**[-0.70, +8.78 pp]**. Marginal coverage is closer to the nominal 90% target, but
neither a coverage gain nor superior interval quality is established. Simpler
security absolute intervals are competitive; they were a declared comparator,
not a post-test replacement. No method was promoted or tuned after these results.

| Fresh-period subgroup | N | Primary coverage | Mean width | Interval score | Selected MAE / zero-return MAE |
|---|---:|---:|---:|---:|---:|
| 2024 | 45 | 86.67% | 27.98 pp | 39.35 pp | 6.00 / 5.87 pp |
| 2025 | 35 | 97.14% | 26.57 pp | 27.47 pp | 4.82 / 4.65 pp |
| HDFCBANK | 16 | 87.50% | 20.31 pp | 43.40 pp | 6.16 / 6.28 pp |
| INFY | 16 | 100.00% | 38.37 pp | 38.37 pp | 6.75 / 6.68 pp |
| ITC | 16 | 87.50% | 24.15 pp | 26.91 pp | 5.03 / 4.51 pp |
| RELIANCE | 16 | 87.50% | 30.42 pp | 36.56 pp | 5.10 / 5.40 pp |
| TCS | 16 | 93.75% | 23.57 pp | 25.53 pp | 4.38 / 3.81 pp |

INFY's 100% coverage has particularly wide bounds. HDFCBANK has severe misses
despite narrower bounds. Three securities remain below 90% empirical coverage,
and 2024 undercovers. Sixteen observations per stock and eight total quarters are
too few to declare stable conditional coverage; the marginal bootstrap does not
certify each stock/year or future crises.

## Exploratory calendar and joint-denominator correction

On 2025-03-18, RELIANCE, TCS, INFY and HDFCBANK contain zero-volume flat OHLC equal
to the previous close, without a corporate action. ITC has positive volume and
varying OHLC that day. These are security-specific stale vendor placeholders,
not a uniform exchange holiday. The predeclared exclusion avoids stale inputs but
shifts subsequent vendor-row sampling and one common origin's target-end date.
No values were invented and no evaluation rows were retrospectively realigned.

The saved results contain **ten complete five-security origins plus twelve
partial origins**. The old reporting expression counted all available groups,
which overstated simultaneous coverage. Corrected primary simultaneous coverage
is **6/10 = 60%**, rather than 17/22 = 77.27%. Corrected joint-method coverage is
**9/10 = 90%**, rather than 21/22 = 95.45%. Those ten complete origins span only
five quarters, mostly 2024; they do not represent all of 2025. No precise joint
coverage uncertainty or full-period joint claim is supported. Marginal coverage,
widths, scores and their eight-quarter intervals remain unchanged.

## Evidence, checks and remaining review

- Original results: `.runtime/forecast/{selection,report,policies}.json` and original
  review summaries. All original hashes remain unchanged.
- Frozen follow-up: `.runtime/forecast-followup/fresh/{selection,report}.json`,
  its once-only start ledger and matching implementation snapshot. The recorded
  uncorrected joint statistic is retained for traceability, not endorsed.
- Corrected, labelled exploratory view:
  `.runtime/forecast-followup/exploratory-report.json` and
  [review summary](assets/forecast-followup-summary.json), including source hashes.
- Revised manifest/protocol: `data/forecast_followup_{manifest,protocol}.json`.
- CLI: `scripts/forecast_followup.py prepare`, then `test`; existing runs/ledger
  refuse another purported fresh evaluation. `scripts/forecast_followup_exploratory.py`
  derives the correction from saved rows, without refitting or rescoring a model.
- Local report review can set `VIBEFINANCE_FORECAST_REPORT` to the corrected
  exploratory file. Default artifact location and Render configuration are unchanged.

Safeguards, original simulations, dependency lockfiles and portfolio actions stay
intact. The model remains research-only with a failed admission check. Independent
data/calendar verification, more time regimes and another predeclared future
replication would be needed before stronger claims. This pass does not select a
new winner from the now-spent 2024–2025 results or establish deployment readiness.

Final verification: **296 tests passed**, one existing upstream deprecation warning.
API smoke, both dashboard scripts and an actual API/rendered dashboard load of
the corrected exploratory report passed in isolated state. Reconnection preserved
files and the original result hashes. Changes remain local and uncommitted;
Render and its private access settings were not changed.
