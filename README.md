# VibeFinance

An offline hackathon MVP for personalized, explainable investment intelligence for
Indian retail investors. Five typed agents run concurrently, document claims are
checked against registered sources, and portfolio policies govern the final action.

**Default prices are seeded simulations; all 21 company documents are synthetic.**
Optional live prices do not make synthetic filings authentic.

> Educational/simulated, not investment advice (SEBI-registered advice required).

## Run locally

Install Python 3.11+ tooling and uv. From the repository root:

```sh
make setup
make demo
```

Make installs Python into the ignored project `.runtime/python`, creates `.venv`,
and installs the complete `requirements.lock` with required artifact hashes.
It works with a writable checkout on macOS or Linux; the cloud instance was tested
on Linux/Python 3.11.17. A native macOS run has not been independently tested.

The launcher starts the API on local port 8000 and Streamlit on local port 8501.
Use your browser or supported port forwarding. The onboarding UI does not supply
web previews. Ctrl-C stops only the launcher's children; occupied ports are refused.
Retriever initialization allows 60 seconds; the launcher allows 120 seconds for
service readiness. These limits are active in the package implementation.

## Validate and evaluate

```sh
make test
make smoke                                      # requires running API
.venv/bin/python scripts/check_dashboard.py       # requires running API
.venv/bin/python scripts/check_dashboard_extended.py
make evaluate                                   # technical direction evaluation
make policies                                   # all-agent point-in-time policy replay
make benchmark                                  # real sequential/parallel timing
```

The extended dashboard checks exercise the real API in an isolated temporary database.
They cover profile forms, cache refresh, beginner/analyst visibility, highlighted
sources, failed requests, unsaved results and shared-token login. See
[VALIDATION.md](docs/VALIDATION.md) for actual results and limitations.

## Guaranteed synthetic demo paths

| Selection | Expected behavior |
|---|---|
| RELIANCE, compare original profiles | Same inputs: Meera REDUCE, Arjun ACCUMULATE, Rohan BUY |
| TCS, Arjun | Bullish trend vs cautionary filing; HOLD, conflicts and lower strength |
| ITC | Seeded sentiment outage; remaining agents and portfolio policy continue |
| HDFCBANK | Missing filing; UNKNOWN, no invented fundamentals; WATCH for normal exposure |
| INFY | Rising prices with falling volume participation; divergence warning |
| ITC, Meera + missing filing | 45% holding exceeds 15% limit; REDUCE despite missing market evidence |

Edited profiles can change these outputs. Do not reset a user's edits merely to
reproduce the original seeds.

The dashboard supports profile creation/editing, watchlist scans, source-document
highlighting, risk/portfolio what-if, profile comparison, technical evaluation,
full-agent policy replay, measured timing and persistent decisions/history.
Both modes show heuristic evidence strength and expandable full reasoning, agent
evidence and processing trace. Analyst mode adds expert indicators and quantitative
evaluation panels. Sentiment uses dated news and transcript quotations, with repeated
passages counted once. What-if trades never alter holdings or place orders.

## What the evidence checks mean

Each emitted agent evidence statement has an EvidenceClaim and explicit citation
IDs. Validation checks an exact quotation, re-extracts a known financial fact
template, or recomputes a supported market/profile statement. Classifications and
confidence are compared with deterministic recomputation. Unsupported, duplicated,
or uninformative substitute statements are removed and lower evidence strength.

These checks do not prove arbitrary semantic entailment, complete financial
interpretation or real-world truth. Synthetic sources remain fictional.
Recommendation confidence is market evidence strength, not a probability of profit
or certainty that a portfolio rule is appropriate.

## Configuration

| Variable | Purpose |
|---|---|
| VIBEFINANCE_STATE_DIR | SQLite and optional Chroma state; default `.runtime` |
| VIBEFINANCE_API_URL | Dashboard API destination; launcher derives it automatically |
| VIBEFINANCE_API_TOKEN | Optional shared demo password/Bearer token; never commit values |
| VIBEFINANCE_API_HOST / VIBEFINANCE_API_PORT | Default 127.0.0.1 / 8000 |
| VIBEFINANCE_DASHBOARD_HOST / VIBEFINANCE_DASHBOARD_PORT | Default 127.0.0.1 / 8501 |
| VIBEFINANCE_EMBEDDINGS | Set 1 for opt-in local MiniLM + BM25 retrieval |
| VIBEFINANCE_EMBEDDING_MODEL_PATH | Optional local verified model directory |
| VIBEFINANCE_CORPUS_PATH | Optional corpus directory override; invalid/missing documents degrade explicitly |
| VIBEFINANCE_FORECAST_REPORT | Saved research report override; local default `VIBEFINANCE_STATE_DIR/forecast/report.json`, Render default tracked corrected summary |

External bindings require the shared access token. The API checks Bearer access and
the dashboard asks for the same token. This is shared demonstration access, not
individual accounts, authorization isolation or a production privacy system.
Keep real investor information out of a shared demo.

Holdings are fractions, e.g. 0.45 means 45%; unallocated weight is cash. Invalid or
overallocated profiles are rejected. Seed initialization preserves edits/deletions.
Storage failures return an explicitly unsaved result, retain inline sources, and
disable decision writes. The API discloses read-only seed fallback if stored profiles
cannot be read; saved customized profiles are not silently replaced.

## Optional integrations

The default BM25 path works without a model, keys or runtime network access.
Neural retrieval and Yahoo packages are deliberately separate from the core lock.

An isolated CPU embedding environment was installed using
`requirements-embeddings.txt`; a real Chroma store/query was verified using
explicitly labeled fixture vectors. A previous cloud run could not download MiniLM
from huggingface.co (HTTP 403). That was a limitation of that run: the user later
reported real MiniLM + BM25 retrieval with 21 chunks locally, remaining hybrid after
an analysis. The local result has not been independently repeated in this cloud run.

To verify embeddings in a configured optional environment, run:

```sh
HF_HOME="$PWD/.runtime/huggingface" .runtime/embeddings-venv/bin/python scripts/check_embeddings.py --download
HF_HOME="$PWD/.runtime/huggingface" VIBEFINANCE_EMBEDDINGS=1 make demo PYTHON=.runtime/embeddings-venv/bin/python
```

Application startup never downloads models. Missing model/backend/query support
falls back to BM25 with a warning. Exact optional installation commands are in
[INTEGRATIONS.md](docs/INTEGRATIONS.md). Do not sync the core-only lock into an
optional environment with make setup; it would remove optional packages.

In the previous cloud run, Yahoo's fc.yahoo.com request was denied with HTTP 403.
The optional live-check script validates simulation fallback and exits nonzero when
live mode is required.
The dashboard can try live prices and charts the exact session rows; failed live
access is disclosed. No LLM rewriting has been implemented.

## Evaluation interpretation

Technical evaluation uses 12 independent seeds and 60 artificial price paths
without injected demo trends. Of 1,080 windows, 826 have directional signals and
254 are neutral abstentions. Momentum hit rate is 45.52%, compared with random
52.54% and always-up 57.99%. There is no demonstrated predictive edge.

Up-direction probabilities are empirical estimates fitted only on matured previous
windows on the same path. Their Brier score is 0.2734, worse than constant 0.5
probabilities (0.25). Calibration is measured for that defined target, not the
personalized recommendation's confidence. Seed-cluster uncertainty is reported.

The separate full-agent replay uses dated synthetic publications independent of
future prices. It checks policy constraints in 90 profile decisions over 30 market
windows; it does not simulate a trading strategy or establish profitability.
Measured sequential/parallel timings may show a slowdown for these small agents.
Never treat concurrency itself as a promised speedup.

## Historical price forecasting research

The historical research pipeline is separate from the synthetic momentum check
and the five-agent recommendation. It uses dated prices for the existing five-stock
universe, with raw Parquet hashes and provenance pinned in
[`data/forecast_manifest.json`](data/forecast_manifest.json). The source is
[aswinv90/indian-market-historical-data](https://github.com/aswinv90/indian-market-historical-data),
a third-party archive of Yahoo Finance history with a noncommercial research-only
license. This is not an official exchange feed. Zero-volume placeholders are
excluded by a uniform rule before fitting or scoring; positive-volume weekend
sessions are retained.

From the repository root, run each stage explicitly:

```sh
.venv/bin/python scripts/forecast.py download
.venv/bin/python scripts/forecast.py prepare
.venv/bin/python scripts/forecast.py test
.venv/bin/python scripts/historical_policies.py
```

The fixed protocol uses 2010–2015 initial training, expanding yearly validation
in 2016–2017, separate residual calibration in 2018, and a 2019–2020 test period
untouched until the frozen selection is evaluated. Targets are 30-session adjusted
returns and their up/down direction. Validation, calibration and test outcomes are
purged at period boundaries and do not overlap within each ticker.

The models use ten features derived only from current and past price/volume:
L2 logistic regression for direction probabilities and ridge regression for returns.
Small regularization grids are selected by validation Brier score and return MAE.
Training-prior, constant 50% and mean/zero forecasts can win selection; always-up
and momentum forecasts are also reported as fair baselines on the same test rows.
Model parameters and selection are frozen before testing. Existing selection or
report artifacts are protected from overwrite; a reported holdout cannot become
a tuning set while retaining its test status.

The local default report is `.runtime/forecast/report.json`; Render defaults to
the tracked `docs/assets/forecast-followup-summary.json`. The Metrics tab's
**Load real-history forecast audit** button reads its summary through
`GET /evaluation/forecast`; `VIBEFINANCE_FORECAST_REPORT` can select another report.
Application startup and this endpoint do not download data or train models.
Missing or invalid artifacts produce an unavailable status without invented scores.
Reports expose held-out metrics, uncertainty, calibration and a research acceptance
check, with readiness always marked **research only**. The recorded experiment
failed that check: validation selected prior probability, and the return model
did not beat the historical mean baseline. The historical policy script separately
checks all five agents with real price prefixes and unavailable historical text;
it does not measure recommendation accuracy or P&L.

The five surviving stocks are a narrow retrospective sample, vendor adjustments
may be retrospective, and stocks share market shocks. Historical calibration does
not establish future interval coverage or investment performance. Current price
forecasts are not attached to decisions. Concentration precedence, cash and sector
limits, and missing-evidence safeguards remain unchanged. See
[FORECASTING_AUDIT.md](docs/FORECASTING_AUDIT.md) for the audit, results and remaining
validation requirements.

The [uncertainty follow-up](docs/FORECASTING_FOLLOWUP.md) diagnoses the original
selection and undercoverage, retains prior/mean baselines, and uses longer,
security-specific volatility calibration. Its once-only 2024–2025 evaluation
reached 91.25% marginal coverage, with wider intervals and uncertain quality gains;
no predictive edge or deployment promotion was established. Both evaluation
periods are now spent. Reported joint coverage has a labelled exploratory
complete-universe correction for stale vendor rows.

```sh
.venv/bin/python scripts/forecast_followup.py prepare
.venv/bin/python scripts/forecast_followup.py test
.venv/bin/python scripts/forecast_followup_exploratory.py
```

Existing runs and the shared evaluation-start ledger prevent another purported
fresh score, including after interruption or a different run directory. The
corrected local view is `.runtime/forecast-followup/exploratory-report.json`; set
`VIBEFINANCE_FORECAST_REPORT` explicitly to review it. Default app configuration
and Render remain unchanged. Targets are 30 observed vendor trading rows;
independent price and complete exchange-calendar verification remain limitations.

## Deployment, presentation and handoff

For the existing Render service, see [RENDER.md](docs/RENDER.md). Render startup
uses its assigned port, serves the committed corrected research report, and
shows the deployed commit before demo login. Existing explicit configuration and
the shared password are preserved. No research training runs during deployment.

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for the container, persistent volume, shared
access gate and platform requirements. A Docker image was built through a verified
offline wheel path in a previous cloud run because Docker build networking failed.
The user reports a working BM25 deployment on Render's free tier at
[vibefinance.onrender.com](https://vibefinance.onrender.com). That deployment has not
been independently checked during this cloud audit; its shared access gate remains
the operator's responsibility.

Open [PRESENTATION.html](docs/PRESENTATION.html) for the deck and
[DEMO.md](DEMO.md) for the walkthrough. The delivered assets and their actual
verification are listed in [VALIDATION.md](docs/VALIDATION.md).

[ARCHITECTURE.md](ARCHITECTURE.md) describes the implemented rules;
[BLUEPRINT_UPDATED.md](docs/BLUEPRINT_UPDATED.md) records verified completion,
remaining issues and the prioritized action plan against the preserved original;
[PROGRESS.md](docs/PROGRESS.md) maps the blueprint to current completion;
[HANDOFF_FOR_CLAUDE.md](docs/HANDOFF_FOR_CLAUDE.md) is the honest continuation prompt.

## Data verification, future evaluation and operations

- [Independent-data reconciliation](docs/DATA_VERIFICATION.md): validate authorized
  local price/calendar/action exports without repairs or synthetic fallback.
  A numerical pass still needs genuine provider, rights and universe review.
- [Prospective evaluation](docs/PROSPECTIVE_EVALUATION.md): register first, issue
  fixed baselines on a deterministic schedule, retain missed origins and compare
  matured same-date outcomes. Real registration is blocked until independent
  evidence passes; no new market score is claimed.
- [Hosted acceptance and SQLite recovery](docs/OPERATIONS.md): public release/gate
  checks without a demo password, optional authorized protected checks, and
  consistent backup/restore to new paths. Durable hosting remains a separate task.
- [Current UI evidence](docs/assets/demo-current/manifest.json): actual screenshots
  and a silent browser recording; original captures remain preserved.

The GitHub Actions workflow runs hash-locked tests and rendered dashboard checks
on Linux and Windows. Remote execution must be checked separately; adding the
workflow alone does not establish a passing Windows run.
