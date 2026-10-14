# Five-minute walkthrough

Start `make demo`, run `make smoke`, and use the dashboard in your supported local
development UI. Repeat the walkthrough before presenting; every path uses no keys.

1. **0:00–0:30 — Problem.** Indian retail investors face noisy, disconnected feeds.
   Explain that VibeFinance demonstrates how to combine transparent independent
   signals with personal constraints. Point to the simulated/synthetic disclosure.
2. **0:30–1:30 — End to end.** Choose Arjun and RELIANCE. Run analysis. Start with
   ACCUMULATE, then open the decision explanation and trace. Show five typed agents,
   their measured latencies and evidence. In Sources, open a synthetic filing and
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

Use `docs/PRESENTATION.html` for the finished deck. Delivered screenshots, PDF and
silent backup recording are listed in docs/VALIDATION.md; the capture script can
regenerate them from the actual running dashboard. They are not a narrated rehearsal.
Practice the five-minute spoken delivery yourself before the event. `make evaluate`,
`make policies` and `make benchmark` provide executable quantitative evidence.
