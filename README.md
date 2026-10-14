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
Plain-language mode hides expert indicators and confidence numbers; analyst mode
exposes formulas, evidence and evaluation definitions. What-if trades never alter
holdings or place orders.

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
explicitly labeled fixture vectors. **Successful MiniLM retrieval is not verified**:
model access to huggingface.co was denied with HTTP 403.

After supplying a verified local model or restoring network access, run:

```sh
HF_HOME="$PWD/.runtime/huggingface" .runtime/embeddings-venv/bin/python scripts/check_embeddings.py --download
HF_HOME="$PWD/.runtime/huggingface" VIBEFINANCE_EMBEDDINGS=1 make demo PYTHON=.runtime/embeddings-venv/bin/python
```

Application startup never downloads models. Missing model/backend/query support
falls back to BM25 with a warning. Exact optional installation commands are in
[INTEGRATIONS.md](docs/INTEGRATIONS.md). Do not sync the core-only lock into an
optional environment with make setup; it would remove optional packages.

Yahoo's fc.yahoo.com request was denied with HTTP 403. The optional live-check
script validates simulation fallback and exits nonzero when live mode is required.
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

## Deployment, presentation and handoff

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for the container, persistent volume, shared
access gate and platform requirements. A Docker image was built through a verified
offline wheel path because this environment's Docker build networking failed.
A public provider/account has not been provisioned.

Open [PRESENTATION.html](docs/PRESENTATION.html) for the deck and
[DEMO.md](DEMO.md) for the walkthrough. The delivered assets and their actual
verification are listed in [VALIDATION.md](docs/VALIDATION.md).

[ARCHITECTURE.md](ARCHITECTURE.md) describes the implemented rules;
[PROGRESS.md](docs/PROGRESS.md) maps the blueprint to current completion;
[HANDOFF_FOR_CLAUDE.md](docs/HANDOFF_FOR_CLAUDE.md) is the honest continuation prompt.
