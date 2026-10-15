# Development v2 validation — 15 October 2026

Started from clean main `ed7a5f4602fa2b241847b366f91e2ff2229500eb`, with working
terminal and remote Git access. Changes are on `codex/credible-forecast-development`.
See [research evidence](FORECAST_DEVELOPMENT_V2.md) and
[ingestion/retrieval scope](AUTHENTIC_RETRIEVAL.md). Earlier counts/release markers
below remain historical and are not current verification.

| New check | Actual result / limit |
|---|---|
| Application suite | **795 passed, 14 skipped, 2 upstream deprecation warnings**, Linux CPython 3.11.17, 38.96 s; all 14 skips require real disposable databases |
| Disposable PostgreSQL | **121 passed**, verified TLS PostgreSQL 17 with restricted roles; 10.35 s. Includes account isolation, signed-identity fixtures, restart durability, encrypted recovery and forced RLS; not live Supabase |
| Final research reporting | **13 targeted tests passed**, plus actual hash-pinned development reproduction after preserving calibration rows; no spent evaluation rerun |
| API smoke | Passed personalized actions, conflict/outage/missing filing, safeguards, exact sources, supported claims, persistence and synthetic evaluation on isolated running state |
| Dashboard scripts | Both `check_dashboard.py` and `check_dashboard_extended.py` passed with the actual local API/isolated test state |
| Real Chromium | Analysis, saved historical research, baseline/coverage/no-admission/staleness disclosures and exact source highlight passed; no observed page errors. An initial automation selector matched two buttons; the corrected unique selector passed without app changes |
| Temporal/mathematical controls | Exact 30-row target, future mutation and price-unit invariance, missing peer exclusion, training-only transforms, finite calibration, matured residual updates, complete joint denominator, baseline arithmetic and multiplicity screens passed |
| Ingestion/provenance | Generated format fixtures verify no-overwrite import, byte/hash/span preservation, explicit rights/identity declarations, intraday availability, tampering refusal and missing relevance judgments. No authentic corpus acceptance claimed |
| Neural packages | Separate Linux CPU hash lock installed; all 120 optional packages compatible; core 60 packages compatible. Core/auth/storage locks remain unchanged |
| Real Chroma | Actual persisted query using explicitly labelled fixture vectors passed; does not establish neural semantics |
| MiniLM | Local-only checker exits **2**: no model weights; fallback mode BM25, `real_model_verified=false`. Runtime HTTPS to Hugging Face is blocked; no verification disabled |
| Local performance | Five declared warmed workloads, seven repeats/mode, alternating order and identical-output checks; immutable snapshot reduces redundant indicator arithmetic. See versioned timings; no hosted-throughput claim |
| Preserved evidence | Fifteen original specification/protocol/summary/lock/seed files checked byte-identical to base. Raw archive files remain hash-identical; old frozen forecast modules, artifacts and studies are not rewritten |
| Hosted Supabase/Render | **Not run**. Owner confirms no Supabase project exists; no authenticated provisioning connection or real confirmed operator account. Current runtime blocks public hosted requests. No existing Render configuration/service change |
| Remote CI | First candidate run passed Ubuntu/PostgreSQL and failed Windows on synthetic CRLF compatibility; original assertion retained and a source fix/regression added. Final rerun required; see preserved initial failure evidence |

The [initial Windows failure](assets/ci-development-v2-initial-failure.json) is
preserved. Raw-byte ingestion changed the legacy synthetic universal-newline
contract on Windows; synthetic documents now keep that LF contract, while authentic
imports preserve original CRLF/hash/span evidence. The existing test was not
weakened. A new explicit CRLF regression reproduces the problem on Linux.
This correction does not change any market-data, model, calibration or evaluation
artifact. Remote reruns must pass before claiming cross-platform acceptance.

Full current-run JUnit/logs, browser screenshot, profiling and complete model/
calibration rows are retained under ignored `.runtime/`. Tracked versioned summaries
include reproducible identities. Tests validate implementation, not predictive value.
The development selection retains baselines and admission is false. No new market
outcome, genuine prospective registration, source permission, off-service hosted
recovery, project creation or deployment is inferred from local test success.

The [local container receipt](assets/container-development-v2.json) verifies
image `sha256:4af8420cb2100b4a9914e90dcd29c6bc740cf5a8ecc2a412a3ddc682a45a6abd`, all **50 packaged Python files**, UID 10001,
assigned port, temporary authentication gate, BM25, the packaged historical report,
concentration priority and exact-session persistence after restart, against
implementation `e09878900ee739ade9f18320feba5dd50a020ba1`. The checker rediscovered an
ephemeral Docker host port after restart; two earlier harness attempts are preserved
as failed/interrupted logs and were not application/storage failures. Owned containers
and volumes were removed. Image not published; production/provider acceptance remains
unperformed. Original deployment Dockerfiles and Render settings are unchanged.

Reproduce this core-only container with the existing supported offline build after
hash-verifying wheel downloads, then run `scripts/check_development_container.py
--output .runtime/container-check-NEW.json`. The new checker refuses remote daemons
and image pulls, uses a fresh gate credential only in process environment, verifies
actual packaged hashes separately from the supplied revision marker, and removes only
its own test resources. See [combined sanitized evidence](assets/development-v2-verification.json).

---

# Current free-account candidate — 15 October 2026

The latest work starts at `459669b` and is delivered on
`codex/free-accounts-and-data-verification` for review, preserving the existing
Render demo. It implements the zero-budget Supabase/PostgreSQL route; no real
project, paid resource, production migration or live account acceptance is claimed.
See [FREE_PRODUCTION_STATUS.md](FREE_PRODUCTION_STATUS.md) for activation steps
and [the machine-readable evidence](assets/free-production-verification.json).

Implementation `f7a2358` is pushed. Native Git confirmed identical local/remote
branch heads and unchanged main at `459669b`. The public Render checker returned
health 200/`ok`, the matching `459669b5fb88` marker and enabled password gate with
normal verified TLS and no credentials. See
[current Render preservation evidence](assets/render-free-candidate-preservation.json).
This is a check of the existing demo, not deployment or account acceptance.

| Current check | Actual result and scope |
|---|---|
| Final `make test` | **760 passed, 14 skipped**, 38.70 seconds, Linux Python 3.11; Starlette/AnyIO and optional Authlib deprecation warnings |
| Real PostgreSQL checks | **121 passed**, 7.82 seconds, disposable PostgreSQL 17 with TLS `verify-full`; includes all 14 normal-suite database skips |
| Isolation and guards | Genuine asymmetric signed JWT fixtures; two accounts sharing IDs cannot cross profile/session/decision/source boundaries; forced row security, public-role denial, restart persistence, no SQLite fallback and concentration-first REDUCE passed |
| Account UI | Real Streamlit AppTest checks sign-in/confirmation, refresh/expiry, logout, account changes, cache clearing and empty-account profile creation against explicit local fixtures; not live provider acceptance |
| Operator commands | Bootstrap, migration and encrypted-backup subprocesses work with isolated import paths from outside the checkout; help/invalid/missing configuration fail safely before database access |
| Recovery | Actual TLS PostgreSQL all-account encrypted backup and empty-application restore preserve provider schemas, table ownership, sequences and restricted runtime writes; no live hosted recovery drill |
| Extended dashboard | `VIBEFINANCE_AUTH_MODE=demo VIBEFINANCE_EMBEDDINGS=0 .venv/bin/python scripts/check_dashboard_extended.py` passed |
| Production container | Non-root UID 10001, private API, BM25 21 chunks, actual PostgreSQL TLS, wrong-CA rejection, restart durability and browser account-login gate passed on owned local fixtures; no real provider credential submitted |
| Final production image | Exact parity for all **48 Python files and three locks**; all three packaged operator helps pass from `/tmp` with `PYTHONPATH` removed |
| Original demo image | All **52 core dependencies**, optional auth/database modules absent, imports/startup/private API/browser gate/three profiles/five agents/SQLite persistence and portfolio safeguard passed |
| Dependency check | Separately hash-locked optional install and `uv pip check` passed for 60 installed packages; original core/live/RAG locks unchanged |
| Independent-source evidence | Two real official NSE files reviewed; four stale vendor rows on 18 March 2025 confirmed. Three older corporate-action basis differences remain unresolved. Full F1 is unapproved |
| Prospective operations | Intent-before-write, partial recovery, idempotency, witnessed-registration and complete-cohort readiness checked on fixtures; no genuine registration, issuance or new market outcome |
| Protected hosted checker | 23 mode/credential/empty-account/sanitization tests passed; real Supabase/Render protected acceptance pending actual secure account settings |
| Manual backup workflow | Nine offline success/failure guard checks passed; manual-only, authenticated ciphertext, 10 MiB cap, one-day artifact. Not dispatched; quota review and live recovery pending |
| Research preservation | Original blueprint, five frozen artifact hashes, corrected follow-up summary, source/simulations/seeds and portfolio/forecasting modules unchanged; no spent experiment rerun |
| New implementation CI | All three real jobs passed at `f7a2358`: Ubuntu, Windows and TLS PostgreSQL 17. Public canonical GitHub pages establish outcomes; exact remote test counts were not exposed |

Final production image:
`sha256:a1ec5bbc4b4018f74bac4b660e510117642f6dc0e349fc17b60918bcb4dbd7b1`.
The real TLS/browser/restart run used
`sha256:40b4e67285aa75133e06ed7ab2777a0870158d8da6b74225a2257b44997e364e`;
only three administrative script imports/parser changed afterward. Web modules
and dependencies are byte-identical; final packaging and isolated operator
checks cover those script changes. The original core-only demo image is
`sha256:cb3b13b97efda392fad7092f87fa472eeaa72c11d45902b4fc9ef9d74b60d92d`.
Images were not published. All owned test containers/networks were removed.

Normal HTTPS/proxy/CA trust was retained for source requests. Actual official
copyright/terms review did not establish full automated-pipeline rights;
further requests stopped and acquisition now requires scoped permission evidence.
Two daily raw files do not validate adjusted multiyear history, calendars,
corporate actions or the selected universe. **Predictive advantage is unproven.**

The cloud install/start instructions were saved as a configuration draft,
including optional hashed packages and these limitations. Saving does not apply
or publish the configuration; review/save/publish in environment settings is
required for future-task activation. No domain or secret for an unknown Supabase
project was invented. Actual free-project setup, secure credentials, confirmed
accounts, two-account hosted acceptance and off-service recovery remain open.

The [successful implementation CI run](https://github.com/Aniruddh2708/AgenticAI/actions/runs/38714395220)
is preserved in [the current CI record](assets/ci-free-production-verification.json).
Later evidence-only documentation commits do not change the tested source,
locks, workflows or container parity. No Windows count is inferred from the
local Linux result.

# Earlier remaining-priorities implementation — 15 October 2026

The implementation started at `2ce7719` on main, preserving the previous
uncommitted documentation. The original blueprint, simulations, dependency
locks, seed profiles, frozen manifests/protocols and recorded research summaries
remain unchanged. Neither spent market experiment was rerun or tuned.

| Current check | Actual result |
|---|---|
| Complete suite `make test` | **418 passed**, one existing Starlette/AnyIO deprecation warning; final run 26.22 seconds |
| Transcript tone | Dated news/transcript queries, complete quoted sentences, overlap/mirror deduplication, canonical citation scores, future exclusion, partial-input/outage behavior and forged-classification rejection passed |
| Portfolio/demos | Existing seeded profile actions, conflict/outage/missing-filing paths and concentration-before-missing-evidence guards passed unchanged |
| Default UI transparency | Real-API AppTest and actual Chromium show evidence strength, decision basis, full reasoning/evidence/trace in both modes; explicit probability disclaimers retained |
| Saved-report fragment | Actual protected local browser loaded/reloaded corrected audit while Metrics stayed selected; fragment checks authentication |
| Reconciliation tooling | Strict metadata, basis/vintage, lineage, dates, prices, calendar/actions, hash/path confinement and no repairs; actual F1 report binds prospective fixture rows/calendar and rejects changed inputs |
| Real independent data | **Not validated**: official NSE spent-date request returned proxy 403; no independent exchange export obtained |
| Prospective workflow | Registration freeze, actual F1 gate, deterministic cadence, missed/missing cohort reporting, same-origin baselines, mature targets, same-vintage split/dividend arithmetic, path/lineage checks and sparse-support withholding passed on explicit fixtures |
| Real prospective study | **Not registered**; no new market observations, evaluation scores or model admission |
| Recovery | Online committed-WAL backup, exact profile/session/decision restoration, invalid-source cleanup, no-overwrite races and platform handling passed; actual running native state restored to a new path |
| Native acceptance | Real isolated launcher, shared token, protected API/report, full API smoke and backup/restore passed; owned launcher stopped |
| Extended rendered checks | `scripts/check_dashboard_extended.py` passed profile/cache/input/source/login/storage-failure interactions |
| Container | Verified offline-wheel build, pinned base; 19 actual Render-style runtime/browser/restart/packaged-backup checks passed |
| Exact image parity | Rebuilt final image matches all 42 packaged Python files and corrected report; quick port10000/health/BM25/auth/UID/helper/import checks passed; owned containers/volumes removed |
| Current visual delivery | 16 actual screenshots, 120.9-second recording from 341 Chromium frames, zero observed page errors; original assets preserved |
| Public Render implementation release | Reusable TLS-verified checker passed health200, password-type gate and latest checked revision `19ed8e55a996` without credentials; later corrective pushes need their own revision check |
| Protected hosted acceptance | **Not run**: existing demo credential is not available/requested; local equivalent passed; optional operator checker explicitly acknowledges login's saved session |
| CI | Actual Ubuntu and Windows jobs passed application tests and extended dashboard checks at `19ed8e5`; no Windows test count inferred from private logs |

Final locally built verification image:
`sha256:aea8608a39c51c51f0e64f0af12e183e03367747de3ef696a40b1bdb839296ca`.
Nineteen web/browser/recovery checks first ran on the preceding local image;
the offline prospective module and packaged backup helper changed afterward.
The final image matches all 42 Python files/report. Actual packaged backup and
restore preserved all four tables, a customized profile, session and decision;
permissions, no-overwrite and writable-flush checks passed, alongside quick
Render-mode health/authentication/BM25 and portfolio-guard checks. Later
Markdown/capture changes do not alter these implementation hashes. Images were
not published to a registry. Local evidence is under
`.runtime/remaining-priorities/{native-acceptance,docker-verification,docker-verification-final,docker-verification-dated-source,docker-verification-windows-backup}.json`.
The [current capture manifest](assets/demo-current/manifest.json) is tracked.

Two official NSE domains were saved to a new configuration draft, preserving
Render access and package presets. They require environment review/save and
publication before applying. No source-rights approval or data validity is
implied by opening access. A protected hosted check remains separate from public
release verification, and new release verification follows the pushed commit.
`api.github.com` was added to the same draft after `gh run list` was denied;
Canonical GitHub HTML verified the
[complete green Linux/Windows run](https://github.com/Aniruddh2708/AgenticAI/actions/runs/38694432124)
for `19ed8e55a996fe10c0b9e6250e81ced21abedb1d`: Ubuntu 1m18s, Windows 3m12s.
Both mandatory pytest and extended-dashboard steps passed. Full remote logs and
exact remote test counts were not exposed; do not substitute the local 418 count
for a Windows count. One POSIX directory-fsync test is explicitly platform-scoped.
The [CI evidence record](assets/ci-remaining-priorities-verification.json) preserves
actual outcomes, including earlier failures.

The run closed three substantiated issues: invalid job-level `runner.temp`,
pytest's missing Windows Colorama dependency, and backup flushes using a
read-only handle. The unchanged application lock is supplemented by the hashed
Windows-only CI pin. Backups now flush a writable handle without changing data;
its zero-byte-write regression fails with the old handle. The startup regression
test now asserts the requested 60-second initialization and 10 ms agent budgets
directly, instead of depending on real 10 ms OS scheduling. A mutation check
confirmed that a regressed 10 ms initialization budget fails that assertion.
Production budgets, simulations and portfolio safeguards were not relaxed.

The [public platform-fix deployment evidence](assets/render-platform-fix-verification.json)
verifies the same application commit on Render with TLS, health200/ok and the
password gate, without credentials. A subsequent documentation-only push needs
its own revision check; it changes no application, workflow or dependency files.

# Earlier blueprint review and access — 15 October 2026

The [updated blueprint](BLUEPRINT_UPDATED.md) compares the unchanged original
upload, actual code/tests and recorded evidence at `2ce7719`. Local main and
GitHub main match; the initial checkout was clean. No application code or frozen
forecast artifacts were changed, and no spent experiment was rerun. The last
complete application suite remains **305 passed**, not a new test run here.

New read-only evidence supersedes the older access blocker below:

- Runtime observations are current; Render host policy is enforced.
- Optional `RENDER_API_KEY` binding is skipped, so API deployment control is not ready.
- Public homepage and `/_stcore/health` returned HTTP 200, with health body `ok`,
  after the first health request timed out.
- Chromium's exact public revision check failed with
  `ERR_CERT_AUTHORITY_INVALID` for proxy CA trust. TLS verification was retained.
  A subsequent public Streamlit websocket connection with inherited proxy/CA
  trust and verified TLS returned `Deployed revision: 2ce77198feb5`, matching
  the pushed release, at 09:07:06 IST on 15 October 2026.
- Authenticated hosted behavior and Render control-plane deployment metadata were
  not checked. The public check needed neither the demo password nor a Render key.

Public evidence: [render-release-verification.json](assets/render-release-verification.json).
Local transport detail: `.runtime/blueprint-review/public-release.json`.
Documentation review also found the news-only sentiment input and beginner-mode
visibility differences described in the updated blueprint. The original document
hash and research summaries remain unchanged. Native macOS/fresh restoration,
live Yahoo and independent cloud MiniLM success were not newly established.

# Recorded Render release validation — 15 October 2026

The user authorized updating the existing Render service after the forecasting
work was committed and pushed as `e0b67fd`. This section records release
preparation; it does not claim that the public service runs the new commit.

| Latest release check | Actual result |
|---|---|
| Terminal/repository | Working at `/workspace/AgenticAI`, main; clean starting HEAD `e0b67fd` matched origin/main |
| Complete suite `make test` | **305 passed**, one existing Starlette/AnyIO deprecation warning |
| Render startup regressions | Assigned `PORT`, public dashboard binding, explicit overrides, invalid-port rejection, pre-login revision marker and valid health revision passed |
| Packaged forecast report | Render loads the tracked corrected summary; missing explicit overrides stay unavailable; no automatic training/download or model promotion |
| Actual native Render-style launch | Assigned port 18531, isolated state, API authentication, release marker, corrected 80-row report and five-agent analysis passed |
| Standard Docker build | Pinned base fetched, but package installation blocked by this workspace's build-container DNS; no TLS/hash verification bypassed |
| Verified offline-wheel Docker build | Succeeded with all 52 hash-pinned core dependencies and the pinned base |
| Actual Render-style container | UID 10001, assigned `PORT=10000`/Docker healthcheck, loopback API authentication, 21 BM25 chunks, corrected report, five agents and concentration-first REDUCE with missing filings passed |
| Container browser/restart | Chromium login gate, public test-injected revision, rendered audit with spent/exploratory labels and exact saved session across restart passed; owned containers/volumes removed |
| Original forecasting evidence | All five original artifact/summary hashes unchanged; spent evaluations were not rerun |
| Live Render control/verification | **Blocked/unverified**: no `RENDER_API_KEY`; Render/API requests denied by cloud proxy HTTP 403 |

The built image is `sha256:581759f7f93cf6a5e1612db7d72321a1f80c6a7ea3eead3360d6dfb6a27d6679`;
later release documentation edits do not change runtime code or forecast artifacts.
Local machine-readable evidence is `.runtime/render-setup/docker-verification.json`.
Only owned isolated local services/state were used. The existing Render service's
password, plan and storage were not changed. A push may trigger its existing
auto-deploy policy; exact live revision still needs Render deployment evidence
and the public pre-login revision marker. See [RENDER.md](RENDER.md).

The cloud environment draft now lists `api.render.com`,
`vibefinance.onrender.com` and a secure `RENDER_API_KEY` binding. It has been saved
for review, not published/applied. No private demo password was requested.

# Follow-up research validation — 15 October 2026

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
| Deployment/dependencies at that research stage | Render, simulation, synthesis safeguards and lockfiles unchanged; later commit/push and release preparation recorded above |

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
