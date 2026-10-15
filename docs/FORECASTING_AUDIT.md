# Forecasting audit and implementation — 14 October 2026

**Follow-up, 15 October:** see [FORECASTING_FOLLOWUP.md](FORECASTING_FOLLOWUP.md)
for the prior-selection diagnosis, uncertainty fixes, once-only 2024–2025
evaluation and labelled exploratory joint-coverage correction. Both evaluation
periods are now spent. The original results below remain a historical record.

**Implementation follow-through:** independent-source reconciliation and a
baseline-only prospective ledger now enforce exact verified rows, complete
cohorts, missed origins and same-vintage corporate-action returns. See
[DATA_VERIFICATION.md](DATA_VERIFICATION.md),
[PROSPECTIVE_EVALUATION.md](PROSPECTIVE_EVALUATION.md) and the
[updated blueprint](BLUEPRINT_UPDATED.md). Genuine source approval and real
registration remain blocked; no new market score or trained-model advantage is
claimed. Application tests, recovery and hosted release evidence are in
[VALIDATION.md](VALIDATION.md); they do not establish predictive validity.

The application is a cited, personalized research demo. Its five-agent action is
a deterministic portfolio policy, not a trained price forecaster. This pass adds
a reproducible historical forecasting experiment and rejects promotion when it
does not beat appropriate baselines. It does not establish investment alpha.

## Access and specification

Working terminal and HTTPS Git reads were verified before edits. The starting
checkout was clean at `161d4f42760919c1732102b98fe9da4010d0f102`, identical to
GitHub `main`. Its local branch `work` was switched to tracking `main`, without
a reset or worktree. There were no pre-existing tracked/untracked changes to
overwrite. The attached original blueprint is byte-identical to
`docs/BLUEPRINT.md` (SHA-256
`9b31bebebc7a44b0b2c89187863cac1e8aec13ff6fbcaba06fcd8617fdb3af42`).
The blueprint was audited as specification/context; its embedded handoff prompts
did not replace the user's request.

## Blueprint compliance

| Requirement | Actual implementation | Limit |
|---|---|---|
| Typed outputs, five concurrent agents | `agents/base.py`, `orchestrator.py`; existing barrier/contract tests | Concurrency is tested, speedup is not promised |
| Momentum/volume/news/filings/risk dimensions | Indicator votes, lexicon/templates, portfolio arithmetic | Heuristics, not learned five-agent forecast probabilities |
| Retrieval and provenance | Ticker/type/date filters, BM25, optional MiniLM/Chroma, exact source spans | 21 default documents remain fictional; general semantic truth is not certified |
| Hybrid retrieval | User reports real local MiniLM+BM25 with 21 chunks, remaining hybrid after analysis | Not rerun in this core-only cloud environment |
| Personalized synthesis | Same market input, profile-dependent decisions and explanations | Fixed policy weights/thresholds; no action-success calibration |
| Portfolio guards | Concentration precedence, cash/sector/equity guards, missing evidence, horizon/behavior checks | No portfolio optimizer or complete prospective HHI model |
| Failure handling/storage | Bounded stages, failed/UNKNOWN outputs, atomic SQLite, explicit unsaved results | Timed-out threads cannot be forcibly terminated |
| Required demo/dashboard/persistence | Core functional and rendered checks repeated in this pass | Default scenarios stay synthetic and unchanged |
| Metrics/calibration/backtest | Original synthetic technical benchmark retained; new real-history report added | Technical direction, price-return research and policy compliance are separate targets |
| Full-agent evaluation | Existing synthetic dated replay; new real-price replay with unavailable historical documents | Neither is a historical investment-effectiveness or profitability test |
| Deployment | User reports working BM25 Render service | This pass did not log into, deploy or request its password |
| LLM narration/real documents/production privacy | Not implemented | These are still gaps; price data does not authenticate filings |

## Why the old forecasts were poor

`momentum_agent.analyze` combines 20-session return, moving-average ratio, MACD
and RSI using fixed weights and thresholds. It classifies recent trend; no
training objective links those weights to future returns. The indicators largely
reuse the same price series, so four terms do not supply four independent sources
of predictive information.

`evaluation.backtest._synthetic_market` uses independent future lognormal
increments, without the application's injected demo trends. Conditional on the
simulation parameters, past momentum contains no information about the next
increment. Positive drift favors always-up. Small per-path, label-conditioned
up-rate estimates have sampling variance and can worsen Brier loss compared with
50%. The old 45.52% accuracy / 0.2734 Brier are honest evidence of no demonstrated
advantage, not a reason to change the simulation until the model wins.

Neutral windows are separate abstentions; all comparisons must use the same
scored mask. Recommendation confidence measures evidence strength. Portfolio
REDUCE can be correct because of concentration even when a price rises; action
success cannot be measured as momentum direction accuracy.

## Implemented improvement plan

1. **Reproduce access and audit.** Done before coding; preserve the original
   simulations, contracts, evidence validation and portfolio rules.
2. **Freeze authentic dated inputs.** Five existing tickers, common 2010–2020
   window, pinned archive commit and SHA-256 artifact hashes. No live-to-synthetic
   fallback is allowed in research. Reject missing/invalid/duplicate/unordered
   data inside the study window. Use Yahoo's distinct adjusted close, and scale
   OHLC by adjusted/raw close. Exclude zero-volume placeholders uniformly before
   counting sessions; retain traded Muhurat weekends.
3. **Define the target before training.** Adjusted close-to-close return and
   probability of a strictly positive return over the next 30 actual traded
   sessions, after observing today's close. These are adjusted-return research
   targets, not nominal cash price forecasts or executable trading P&L.
4. **Build causal, modest models.** Ten dimensionless price/volume features;
   L2 logistic probability candidates (penalties 0.01/0.1/1), ridge return
   candidates (0.1/1/10), and simpler constant/prior candidates. Fit scaling and
   coefficients using matured training labels only. No price-level R-squared,
   ticker identity fitting, LLM numeric forecasts or test-driven feature search.
5. **Validate chronologically.** Initial train 2010–2015; expanding 2016 and 2017
   validation folds. Purge labels crossing each boundary. Select probability
   by validation Brier, returns by validation MAE. Refit using eligible earlier
   train/validation labels, stopping before calibration. Daily training targets
   overlap; evaluation samples every 30 sessions per ticker.
6. **Calibrate uncertainty separately.** 2018 supplies a 90% absolute-residual
   interval, without refitting or selecting on calibration outcomes. Report
   empirical reliability bins for probabilities; do not claim a post-hoc
   probability calibration model was fitted. Market regimes do not satisfy the
   exchangeability assumption needed for a conformal coverage guarantee.
7. **Freeze before test.** `selection.json` records protocol, model coefficients,
   source and normalized-frame hashes, implementation hashes, software versions
   and selection identity. A separate command verifies this state and evaluates
   2019–2020. Exclusive output files refuse accidental overwrite; no automatic
   retuning. Every test prediction, label, baseline and interval is retained.
8. **Compare fairly and admit conservatively.** Same-row constant 50%/unchanged
   price, historical prior/mean, always-up and train-fitted momentum-label
   baselines. Original momentum direction separately reports abstentions and
   its same-mask always-up comparison. Report return MAE/RMSE, direction accuracy
   and balanced accuracy, Brier/log loss, empirical interval coverage, ticker/year
   breakdowns and paired calendar-quarter cluster intervals across stocks.
   Promotion requires learned candidates and statistically supported improvement
   over both simple baselines, adequate time blocks and interval coverage. Even
   a pass would remain research-only pending independent replication.
9. **Expose and preserve.** Authenticated API and analyst dashboard load saved
   summaries only. They never download, train, modify actions or reset profiles.
   Historical policy replay uses the real price prefix and no invented historical
   news/filings. Update evidence/handoff, and report failed gates plainly.

## Frozen experiment result

The documented third-party Yahoo archive is
[aswinv90/indian-market-historical-data](https://github.com/aswinv90/indian-market-historical-data)
at `5dffc0832c63d1558930510d081e076929608d82`. Its fetch code explicitly uses
`auto_adjust=False` and preserves `Adj Close`. The five files each supply 2,713
rows within the predeclared study; after excluding two nontraded placeholders,
2,711 sessions remain. Hashes and lineage are in
[`data/forecast_manifest.json`](../data/forecast_manifest.json).
Direct Yahoo/NSE access returned proxy HTTP 403; provenance is documented but the
mirror could not be independently cross-checked against the provider here.
Its license permits noncommercial research only. Raw data stays ignored, and no
archive-derived model was deployed to Render.

Validation used 80 windows; separate calibration used 40. It selected the
historical up-rate **baseline**, rather than logistic features, and ridge penalty
1 for returns. The final fit uses 9,255 overlapping matured training rows; this
is not 9,255 independent experiments. Original frozen test evaluation used 80 windows
from cutoffs 2019-01-01 through 2020-10-29, with final target 2020-12-11.

| Same-row test method | Brier | Accuracy | Return MAE | Return RMSE |
|---|---:|---:|---:|---:|
| Selected prior probability + ridge return | 0.223067 | 67.50% | 9.3424 pp | 13.4943 pp |
| Historical prior + mean return | 0.223067 | 67.50% | 9.3050 pp | 13.5240 pp |
| Constant 50% + zero return | 0.250000 | 67.50%* | 9.7611 pp | 13.8347 pp |
| Always-up + zero return | 0.325000 | 67.50% | 9.7611 pp | 13.8347 pp |
| Train-fitted momentum-label probability/mean return | 0.225396 | 67.50% | 9.3197 pp | 13.5913 pp |

`pp` means percentage points of return. *Probability ties use `>= 0.5`, so the
50% classifier also predicts up; this is not a sampled random strategy. A fair
coin's expected directional accuracy is 50%. All these probability classifiers
have balanced accuracy 50%. The original bullish/bearish momentum rule scored
54.6875% on 64 non-neutral windows, against 68.75% always-up on that exact mask;
16 neutral windows abstained.

The selected model's return MAE difference versus mean return is +0.0374 pp;
its approximate paired 95% quarter-block interval is -0.5602 to +0.5379 pp.
No improvement is established. The nominal 90% interval covered **78.75%** of
test outcomes. The admission gate **failed**. Better Brier than constant 50%
comes from historical class prevalence, not learned predictive information.
These real-history metrics are not directly comparable to the synthetic scores.

The 2019–2020 test is now spent. Do not adjust this model and advertise another
score on those periods as untouched. Future research should use a fresh,
predeclared period/universe, sufficient market regimes, audited corporate-action
data and genuinely point-in-time filing/news availability. Add richer features
only inside new training/validation folds. Independent action-effectiveness
research needs an explicit strategy, execution timing, costs, portfolio revaluation
and appropriate portfolio baselines; the five-agent replay does not provide it.

## Artifacts and checks

- Reproduction: `.venv/bin/python scripts/forecast.py download`, then `prepare`,
  then `test`, from the repository root. Existing frozen/spent runs are preserved.
- Complete local artifact: `.runtime/forecast/report.json`; frozen model:
  `.runtime/forecast/selection.json`; raw files and source license:
  `.runtime/forecast/data/`.
- Reviewable summary: [`assets/forecast-summary.json`](assets/forecast-summary.json),
  including source/model identities and the complete-report SHA-256.
- `/evaluation/forecast` returns a validated summary; malformed/absent reports
  are disclosed. Analyst Metrics → **Load real-history forecast audit**.
- Tests exercise future-mutation invariance, exact target alignment, purging,
  declared train gaps, snapshot integrity, manual baseline arithmetic, numerical
  stability, API auth and rendered UI. Generated test fixtures are not research
  data. See [VALIDATION.md](VALIDATION.md) for final run evidence.

The real-price full-agent replay executed 240 profile decisions over 80 historical
price windows: 80 concentration-driven REDUCE and 160 missing-evidence WATCH.
All listed date/source/agent/concentration/cash/persistence/confidence checks had
zero violations. These are correlated static-profile checks, not 240 independent
forecasts. The complete suite passed 197 tests. API smoke, both dashboard scripts
and an actual dashboard load of the historical report also passed. Run
`.venv/bin/python scripts/historical_policies.py` to reproduce the constraint
replay in an unspent reproduction directory; existing output is preserved.

The latest GitHub startup fixes had been copied into inactive root files while
the package still used 5/30-second defaults. The active package now uses 60-second
retriever initialization and 120-second service readiness; cold initialization is
independent of agent deadlines. Root entrypoints delegate to the package to
prevent another divergence. Neither change relaxes agent evidence checks.
