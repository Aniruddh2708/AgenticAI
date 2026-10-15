# Five-minute walkthrough

Start `make demo`, run `make smoke`, and use the dashboard in your supported local
development UI. Repeat the walkthrough before presenting. Default local analysis
needs no external API keys; a protected hosted/shared demo keeps its existing gate.

1. **0:00–0:30 — Problem.** Indian retail investors face noisy, disconnected feeds.
   Explain how VibeFinance combines transparent analytical dimensions with
   personal constraints. Shared text is not independent corroboration. Point to
   the simulated/synthetic disclosure.
2. **0:30–1:30 — End to end.** Choose Arjun and RELIANCE. Run analysis. Start with
   ACCUMULATE and the evidence-strength score, then open Full numbered reasoning
   and Pipeline trace in the default mode. Show five typed agents, deduplicated
   news/transcript quotes, measured latencies and evidence. In Sources, open a filing and
   click Show source passage to verify the registered excerpt.
3. **1:30–2:30 — Personalization.** Compare all three profiles. Same frame/corpus,
   Meera REDUCE (22% position exceeds 15%), Arjun ACCUMULATE, Rohan BUY. Point to
   Rohan's FOMO/panic-sale nudges. Switch to ITC/Meera to demonstrate 45% concentration.
4. **2:30–3:15 — Conflict.** Select TCS/Arjun. BULLISH momentum vs CAUTIONARY filings
   produces HOLD. Show opposing pairs and the numeric confidence penalty in step 7.
5. **3:15–4:00 — Resilience.** ITC defaults to sentiment outage. HDFCBANK has no
   filing and returns WATCH. On RELIANCE, enable both failure toggles: the pipeline
   finishes with no invented sentiment/fundamentals, lower confidence and WATCH.
6. **4:00–4:40 — Evidence.** Turn off Plain-language mode. Metrics show supported
   statements, cash/equity HHI, independent-path hit rates and baselines, empirical
   direction calibration and Brier score. Momentum underperforms the baselines.
   Run the full-agent dated policy replay and actual timing benchmark. A benchmark
   ratio below one means slowdown. Distinguish policy checks from profitability
   and direction probabilities from recommendation evidence strength.
7. **4:40–5:00 — Business.** Free watchlist, paid personalization, B2B research API.
   Explain that licensed data, audited models and appropriate SEBI compliance are
   prerequisites to a production investment product. Record a demo decision and
   show it persists in History. No trade is executed.

Optional extra: scan a personalized watchlist to show the cross-ticker agent matrix
and relevant alerts; inspect the illustrative five-percentage-point portfolio what-if.
In Metrics, load the saved historical audit without leaving the tab. Explain its
failed research gate and spent/exploratory labels; 91.25% marginal coverage is
uncertain and wider intervals do not demonstrate better investment decisions.

Use `docs/PRESENTATION.html` for the finished deck. Delivered screenshots, PDF and
silent backup recordings are listed in docs/VALIDATION.md. The current set is
`docs/assets/demo-current/` (16 screenshots, 120.9 seconds); originals are preserved.
The capture script can
regenerate them from the actual running dashboard. They are not a narrated rehearsal.
Practice the five-minute spoken delivery yourself before the event. `make evaluate`,
`make policies` and `make benchmark` provide executable quantitative evidence.
