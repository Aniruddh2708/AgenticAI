# Actual validation from the corrective pass

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
| Real MiniLM hybrid retrieval | **Not verified**; model host returned HTTP 403; integration check exited 2 |
| Live Yahoo | **Not verified**; fc.yahoo.com returned CONNECT 403; strict check exited 1 |
| Yahoo fallback | Seeded 300-row frame validated successfully |
| Standard online Docker build | Failed at this host's build-container DNS/proxy access |
| Verified offline-wheel Docker build | Succeeded with pinned base image and required artifact hashes |
| Container behavior | Non-root, dashboard health, private API, API/password gate, five agents and persistence across restart passed |
| Public hosted URL | **Not deployed**; user confirmed no hosting account |
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

- Successful real neural/live integrations and public hosting.
- Optional LLM narration, authentic filing/PDF ingestion and licensed real news.
- Comprehensive financial-language interpretation or general semantic entailment.
- Calibrated personalized-action success, real-history strategy evaluation, costs,
  portfolio revaluation, correlation optimization and demonstrated investment edge.
- Individual accounts, privacy isolation, production audit/security/regulatory work.
- Continuous watchlist monitoring/notifications; alerts currently require a scan.
- Hard termination/isolation of timed-out worker threads.
- Native macOS/fresh cloud restoration and a narrated rehearsal.

The complete continuation prompt is [HANDOFF_FOR_CLAUDE.md](HANDOFF_FOR_CLAUDE.md).
