# Dashboard integration — 15 October 2026

The HTML design provided in `docs/ui-reference/original-dashboard.html`, reference
screenshot, and `DESIGN.md` have been translated into the **primary offline demo
UI** at `vibefinance/web/index.html`. Unlike the source static mockup, the UI is
connected to the existing live FastAPI data-contract endpoints and can operate
without remote fonts, a Tailwind CDN, a paid LLM, or a market API.

## Main files changed

- `vibefinance/web/index.html` — responsive analyst terminal, 6 tabs,
  investor/ticker selectors, outage toggles, data panels and source dialog.
- `vibefinance/web/styles.css` — offline visual translation of the reference.
- `vibefinance/web/app.js` — fetch + render for sessions, cited evidence,
  deterministic price SVG, metrics, baseline comparisons, calibration curve,
  profile editing, decisions/history, watchlist and side-by-side personalization.
- `vibefinance/web/favicon.svg` — local icon.
- `vibefinance/api.py` — serves `/`, `/dashboard`, and `/assets/*`; API request
  and response contracts are unchanged. HTML/assets are public; all data
  endpoints retain bearer/managed identity protections.
- `vibefinance/demo.py` — in **demo auth mode** launch the terminal at the
  configured dashboard port (default 8501) alongside the existing API at 8000.
  In **managed auth mode**, preserve the existing production Streamlit login.
- `Makefile` — `make dashboard` runs HTML frontend + API on 8501;
  `make legacy-dashboard` retains access to Streamlit.
- `pyproject.toml` — bundle local HTML, CSS, JS and SVG assets.
- `README.md` and `vibefinance/web/README.md` — quickstart and caveats.
- `tests/test_web_terminal.py` — route, asset, protection, scenario and typed
  contract smoke coverage.

## Commands

```sh
# Python 3.11+; dependencies need to be installed once
python -m pip install -r requirements.txt
python -m vibefinance.demo
# Open http://127.0.0.1:8501/

# Or, standalone on port 8501:
python -m uvicorn vibefinance.api:app --host 127.0.0.1 --port 8501

# Automated smoke checks:
python -m pytest -q tests/test_web_terminal.py
```

## Browser scenarios

- RELIANCE/Arjun: five real agents, ACCUMULATE, computed confidence and citations.
- RELIANCE/three users: REDUCE, ACCUMULATE, BUY using the same market input.
- TCS: HOLD and explicitly documented opposing signals.
- ITC: sentiment agent degraded (also seeded to be unavailable).
- HDFCBANK: filing output UNKNOWN without invented source passages.
- Audit Trail: click a citation and inspect its exact source passage.
- Metrics: measured agent latency, portfolio HHI what-if, technical hit rate vs
  two baselines, calibration curve, simulation limitations.

## Safety and scope

- **No backend contracts changed.** Existing Python schemas, logic and tests
  are preserved. Static UI only maps response fields to display components.
- Numbers in the uploaded static NVDA/SEC mockup were **placeholders**, so they
  have been removed; this app analyzes the five supported `.NS` tickers.
- Source documents and demo prices are synthetic and labelled; evaluation
  does not establish a predictive advantage.
- New HTML frontend is default for offline demo, **not yet** the managed-account
  production frontend. OAuth/Supabase sign-in and advanced specialized research
  views remain in the legacy Streamlit client until a proper migration is built.
- Browser token prompt holds the optional shared demo token in memory only.
- This is a research tool; no trade execution occurs.

## Validation performed

- `node --check` on the frontend script.
- FastAPI `TestClient` for main HTML, all static files, health, authentication,
  RELIANCE/TCS/HDFCBANK and three-user comparison.
- Headless Chromium DOM/click checks with fixtures collected from actual backend
  responses: agent rendering, ticker switching, opening sources, comparison,
  evaluation; no JavaScript errors.
- Full local `python -m vibefinance.demo` dual-service startup and same-origin
  API/asset GET checks passed on isolated test ports.
- Focused pytest run: **55 passed** (not claimed as a full repository suite).
