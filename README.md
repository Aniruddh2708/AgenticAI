# VibeFinance

A runnable hackathon MVP for personalized, cited investment intelligence for Indian
retail investors. Five agents analyze independent dimensions in parallel and return
typed evidence; a deterministic synthesizer resolves conflicts and applies profile
constraints. FastAPI serves a Streamlit + Plotly dashboard. SQLite retains profiles,
recommendations, metrics and demo decisions.

**All default prices are seeded simulations. All 21 company documents are synthetic.**
They do not describe actual company performance or actual SEBI filings. No keys, paid
services, network requests, model downloads or LLM are needed during the default demo.

> Educational/simulated, not investment advice (SEBI-registered advice required).

## Run

Python 3.11+, `uv`, and GNU Make are needed. The cloud instance has Python 3.11.17
and a prepared `.venv`. From `/workspace/AgenticAI`:

```sh
make setup       # install Python 3.11 and checksum-verified pinned dependencies
make demo        # starts API on port 8000 and dashboard on port 8501
```

Open the dashboard using your local browser or your development platform's supported
port forwarding. The onboarding UI does not provide web previews. Ctrl-C stops only
the services created by this launcher. `make api` and `make dashboard` start each
service separately. The demo refuses to take over occupied ports.

Outside the cloud container, choose a writable interpreter location:

```sh
make setup UV_PYTHON_INSTALL_DIR="$PWD/.runtime/python"
make demo
```

Installation downloads verified packages; running the default workflow is offline.
`requirements.lock` pins all 52 transitive packages with artifact hashes. Use the
repository root as your working directory; activation is optional because Make uses
`.venv/bin/python` directly. For plain Python commands, `source .venv/bin/activate`.

## Verify

```sh
make test       # scenarios, indicators, validation, actual overlap, failures, API, SQLite
make evaluate   # reproducible walk-forward results as JSON
make smoke      # functional requests against a running API
```

Dashboard interaction checks are available separately while `make demo` is running:

```sh
.venv/bin/python scripts/check_dashboard.py
```

## Demo scenarios

| Selection | Observable result |
|---|---|
| RELIANCE, compare users | Identical signals: Meera REDUCE, Arjun ACCUMULATE, Rohan BUY |
| TCS, Arjun | Bullish momentum vs cautionary filings; HOLD and confidence penalty |
| ITC | Sentiment unavailable by default; warning, other evidence remains available |
| HDFCBANK | No filing in corpus; UNKNOWN filings, WATCH, no invented fundamentals |
| INFY | Rising price with declining participation; SPIKE_DOWN divergence warning |
| ITC, Meera | 45% position exceeds 15% limit; gradual rebalance nudge |
| Sentiment outage + missing filing toggles | Pipeline finishes with lower confidence and WATCH |

The recommendation leads the UI. Tabs expose agent evidence, verifiable passages,
portfolio charts and what-if, profile comparison, metrics and history. Watchlist
scans show a cross-ticker disagreement matrix and alerts filtered through this user's
action policy. The beginner/analyst toggle changes the level of explanation. The
decision controls record a choice; they never place trades or mutate holdings.

## Configuration and optional enhancements

| Variable | Default / purpose |
|---|---|
| `VIBEFINANCE_STATE_DIR` | `.runtime/`; SQLite and optional Chroma index |
| `VIBEFINANCE_API_URL` | Local API on port 8000; dashboard backend |
| `VIBEFINANCE_EMBEDDINGS` | Unset; `1` opts into local embedding + BM25 hybrid |

The default BM25 retriever is implemented locally and needs no trained model.
`requirements-optional.txt` contains opt-in dependencies, separate from the tested
core lock. Installing it is not required for the demo. For hybrid retrieval, provision
a verified local `sentence-transformers/all-MiniLM-L6-v2` model in the standard model
cache, then set `VIBEFINANCE_EMBEDDINGS=1` before API startup. Loading is local-only;
missing dependencies/models or a query failure transparently fall back to BM25.
The optional embedding branch needs separate integration validation with a real
model; the failure fallback is tested in the core suite.

The API accepts `live: true` for optional yfinance ingestion; failures return seeded
prices with a warning. The dashboard intentionally stays simulated so the chart,
agents and cross-user comparison use the same inputs. Live feed success has not been
validated, and synthetic filings remain synthetic even with live prices. Configure
Yahoo destinations in environment settings only if you enable that path. Optional
LLM rewriting is deferred: explanations currently come from deterministic templates
and cannot change actions, numbers or sources.

## API

Endpoints: `GET /health`, `/profiles`, `/profiles/{id}`, `PUT /profiles/{id}`,
`DELETE /profiles/{id}`, `POST /analyze`, `/compare`, `/watchlist`, `GET /evaluation`,
`/history/{user_id}`, `/sessions/{id}`, `/sessions/{id}/sources/{chunk_id}`,
`POST /sessions/{id}/decision`, `GET /sessions/{id}/decisions`.
The generated OpenAPI documentation describes request bodies and constraints.

Holdings are **fractions of total portfolio value**, not rupee amounts: e.g. `0.45`
means 45%. Unallocated weight is cash. Invalid, negative, nonfinite or overallocated
profiles are rejected. Profiles are seeded using INSERT OR IGNORE so rerunning setup
preserves edits. State is local SQLite; this demo has no authentication or multi-tenant
security and binds to loopback by default.

## Evaluation limits

The backtest evaluates technical **direction**, not recommended investments. At each
date it uses only the historical prefix, then checks the next 30 trading sessions.
Windows do not overlap within a ticker. Neutral observations are excluded and sample
size is reported. Random and always-up baselines use the same dates. Mean forward
returns are descriptive, not strategy returns. The calibration chart converts trend
strength to a heuristic up-direction probability; the Brier score is measured, not a
claim of validated calibration. Prices are artificial, the sample is small, and no
investment edge is claimed. Recommendation confidence is a rule-based score rather
than a calibrated probability of profit.

See [ARCHITECTURE.md](ARCHITECTURE.md) for formulas and degradation rules,
[DEMO.md](DEMO.md) for the walkthrough and [docs/BUSINESS.md](docs/BUSINESS.md) for
the commercial concept.
