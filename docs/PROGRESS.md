# Blueprint implementation status

The original uploaded specification is retained in [BLUEPRINT.md](BLUEPRINT.md).

- [x] Phase 1 — typed contracts, configuration, SQLite and three seed profiles
- [x] Phase 2 — deterministic OHLCV, injected scenarios, indicator tests
- [x] Phase 3 — momentum/volume/sentiment and verified parallel execution
- [x] Phase 4 — 21 synthetic documents, filtered retrieval and cited filings
- [x] Phase 5 — risk, concentration overrides, conflicts and personalization
- [x] Phase 6 — bounded agents, failure/outage/missing-document demonstrations
- [x] Phase 7 — persisted session metrics, technical backtest/baselines/calibration
- [x] Phase 8 — API-connected Streamlit dashboard and exercised interactions
- [x] Phase 9 — architecture, README, demo guide and business slide content

Implemented differentiators include calibration/Brier score, historical-prefix
technical evaluation, watchlist agent matrix, behaviour nudges, cash-funded
portfolio what-if, profile-aware alerts, persistent sessions/decisions and beginner
explanations. Optional live-market success and local neural retrieval are not core
validated capabilities. No optional LLM is enabled; all explanations are templates.

Important refinements from the blueprint:

- Citation has an additional date field; original contract fields are preserved.
- Market/profile input provenance is distinguished from synthetic document citations.
- Default retrieval uses BM25; neural hybrid is opt-in with a local model and explicit
  fallback. Its successful real-model path needs separate validation.
- Latency comparison is labelled as an estimated overlap ratio; no fabricated
  sequential benchmark is claimed.
- Evaluation measures 30 **trading sessions** of technical direction, not the
  personalized strategy. Its sample size and weaker-than-always-up result are shown.
- Profiles use portfolio fractions; the what-if preserves total weight and does not
  mutate holdings. Seed initialization preserves profile edits and deletions.
- Core dependencies are pinned with hashes. Optional integrations have a separate
  dependency file and are not installed by the default environment setup.

Publication and a fresh cloud-task restoration are outside the completed current
instance validation. GitHub publication is not performed by this implementation.
