# VibeFinance XAI HTML frontend

`index.html`, `styles.css`, `app.js`, and `favicon.svg` replace the offline demo's
Streamlit frontend and follow the uploaded dark, two-column analyst-terminal
reference. **Do not open `index.html` with `file://`**: start the FastAPI service
and open `http://127.0.0.1:8501/` using `make demo` (or `make dashboard`).

Everything is local: system fonts, authored CSS, no remote dependencies.
The browser calls the same-origin `/profiles`, `/analyze`, `/compare`, `/evaluation`,
`/history/{user_id}`, `/sessions/{id}`, and `/sessions/{id}/decision` endpoints.
No backend request or Pydantic contract was changed for this UI. Every figure
is derived from the response to those existing endpoints. The old dashboard is
kept for hosted OAuth/Supabase compatibility while managed sign-in is developed.

## Test path

1. Open Overview with Arjun / RELIANCE, confirm 5 agents and ACCUMULATE.
2. Scenarios → TCS, confirm HOLD and conflict warnings.
3. Audit Trail → click a source to view an exact highlighted passage when present.
4. Compare → see Meera REDUCE, Arjun ACCUMULATE, Rohan BUY on RELIANCE.
5. Scenarios → ITC/outage or HDFCBANK/missing filing, confirm clear degraded status.
6. Metrics → Load evaluation, check both baselines and disclosed simulation limits.
7. Change investor, edit profile, save a follow/watch/skip decision and refresh History.

The old HTML's NVDA valuations, citation counts, inference prices, and proprietary
model names were mock numbers, not part of VibeFinance's data. They were removed.
