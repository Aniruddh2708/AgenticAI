# VibeFinance (PS 04) — Build Blueprint

> Paste this whole file into any AI model as context, then say: "We are at Phase X. Build the next file."
> Hackathon MVP. Priority: working end-to-end pipeline, transparent reasoning, source attribution, demonstrable personalization. Simulated data is acceptable if disclosed.

## 1. One-line goal
A multi-agent system that turns market data + filings + user behavior into **personalized, explainable, cited, confidence-scored** investment intelligence for Indian retail investors.

## 2. Judging rubric (optimize for this)
| Criterion | Weight | What we must show |
|---|---|---|
| Signal classification and analytical quality | 20 | 3+ independent dimensions, each with label + confidence + evidence |
| Multi-agent architecture and synthesis | 20 | 3+ agents running in PARALLEL, structured output contracts, coherent synthesis |
| Retrieval and source attribution | 15 | RAG over filings/transcripts; citations visible and verifiable |
| Personalization and risk awareness | 15 | SAME market input, DIFFERENT output for different user profiles |
| Engineering and reliability | 10 | Persistence, reproducibility, graceful degradation |
| Performance and evaluation | 10 | 3+ metrics logged per session |
| Explainability and commercial relevance | 10 | Visible reasoning chain, clear UI, retail-relevant |

## 3. Tech stack (keep it simple, all free)
- Python 3.11, **FastAPI** (backend API), **Streamlit** (dashboard, fastest to build), **SQLite** (profiles, sessions, metrics), `asyncio` (parallel agents)
- Data: **simulated OHLCV** generator (seeded for reproducibility) + optional `yfinance` for NSE tickers (`RELIANCE.NS`, `TCS.NS`, `INFY.NS`, `HDFCBANK.NS`, `ITC.NS`) with simulated fallback
- RAG: synthetic filings/transcripts as .txt/.md, chunked; **ChromaDB** + sentence-transformers (`all-MiniLM-L6-v2`), with a **TF-IDF/BM25 fallback** if embeddings fail
- LLM: Claude/any LLM API for agent narration, **with deterministic rule-based fallback** so the demo never breaks. All numeric signals are computed in code, the LLM only explains.
- Charts: Plotly

## 4. Repo structure
```
vibefinance/
├── README.md
├── ARCHITECTURE.md              # required deliverable for judges
├── requirements.txt
├── config.py                    # tickers, seeds, thresholds, feature flags
├── data/
│   ├── market_sim.py            # seeded OHLCV + injected anomalies
│   ├── market_live.py           # optional yfinance, falls back to sim
│   ├── corpus/                  # synthetic SEBI filings, earnings transcripts, news (15-30 docs)
│   └── users.json               # seed profiles
├── rag/
│   ├── ingest.py                # chunk + embed + store with metadata
│   └── retriever.py             # retrieve(query, ticker, k) -> [Chunk]
├── agents/
│   ├── base.py                  # AgentOutput schema, timing wrapper
│   ├── momentum_agent.py
│   ├── volume_agent.py
│   ├── sentiment_agent.py
│   ├── filings_agent.py         # RAG-grounded
│   └── risk_agent.py            # portfolio-aware
├── synthesis/
│   └── synthesizer.py           # conflict resolution + personalization
├── profiles/
│   └── store.py                 # SQLite CRUD for users, holdings, behavior
├── orchestrator.py              # runs agents in parallel, handles failures
├── evaluation/
│   ├── metrics.py               # per-session metrics logging
│   └── backtest.py              # 30-day forward return accuracy
├── api.py                       # FastAPI endpoints
├── dashboard.py                 # Streamlit app
└── tests/
```

## 5. Core data contracts (build these FIRST, everything depends on them)

```python
# agents/base.py
from pydantic import BaseModel
from typing import Literal, Optional

class Citation(BaseModel):
    source_id: str        # e.g. "RELIANCE_Q2FY26_transcript"
    doc_title: str
    chunk_id: str
    excerpt: str          # short supporting text
    score: float

class AgentOutput(BaseModel):
    agent: str
    ticker: str
    dimension: Literal["momentum","volume","sentiment","filings","risk"]
    label: str            # e.g. BULLISH / BEARISH / NEUTRAL, SPIKE / NORMAL, RISK_HIGH ...
    confidence: float     # 0..1
    evidence: list[str]   # human-readable bullet reasons with numbers
    citations: list[Citation] = []
    status: Literal["ok","degraded","failed"] = "ok"
    degraded_reason: Optional[str] = None
    latency_ms: float = 0.0

class UserProfile(BaseModel):
    user_id: str
    name: str
    risk_tolerance: Literal["conservative","moderate","aggressive"]
    horizon_months: int
    holdings: dict[str, float]      # ticker -> weight or value
    max_single_stock_pct: float     # concentration limit
    behavior: dict                  # e.g. {"panic_sell_count":3,"avg_hold_days":20,"chases_momentum":True}

class Recommendation(BaseModel):
    user_id: str
    ticker: str
    action: Literal["BUY","ACCUMULATE","HOLD","REDUCE","AVOID","WATCH"]
    confidence: float
    reasoning_chain: list[str]      # step by step, visible in UI
    citations: list[Citation]
    agent_outputs: list[AgentOutput]
    conflicts: list[str]            # disagreements between agents, explained
    personalization_notes: list[str]
    disclaimer: str
```

## 6. Agents (all run in parallel via `asyncio.gather`)
| Agent | Dimension | Method (computed in code) | Labels |
|---|---|---|---|
| Momentum | price momentum | RSI(14), MACD, 20/50 DMA crossover, 1M return | BULLISH / BEARISH / NEUTRAL |
| Volume | volume anomaly | z-score of volume vs 30d mean, price-volume divergence | SPIKE_UP / SPIKE_DOWN / NORMAL |
| Sentiment | news/transcript sentiment | lexicon or LLM score on news headlines + transcript tone | POSITIVE / NEGATIVE / MIXED |
| Filings (RAG) | fundamentals/regulatory | retrieve top-k chunks for ticker, summarize risks/guidance, **must cite** | SUPPORTIVE / CAUTIONARY / UNKNOWN |
| Risk | portfolio | concentration (HHI), sector exposure, position vs user limit | RISK_LOW / MED / HIGH |

Rules:
- Confidence derived from signal strength (e.g. normalized distance from threshold), never hardcoded.
- Every agent returns `AgentOutput` even on failure (`status="failed"`, `confidence=0`). Never raise to the orchestrator.
- Each agent wrapped in timeout (e.g. 5s) and latency timing.

## 7. Synthesis layer
1. Collect all `AgentOutput`s; drop `failed`, down-weight `degraded`.
2. Weighted vote across dimensions → raw score and raw confidence.
3. **Conflict detection**: if momentum BULLISH but filings CAUTIONARY (or any opposing pair), add an entry to `conflicts` with explanation, and lower confidence.
4. **Personalization**: adjust using the profile:
   - conservative: higher bar for BUY, penalize volatile signals, cap action at ACCUMULATE/HOLD
   - aggressive: tolerates momentum, lower bar
   - concentration: if ticker weight > `max_single_stock_pct`, force REDUCE/HOLD regardless of signal
   - behavior: e.g. `chases_momentum=True` → add warning "momentum signal may match your FOMO pattern, wait for confirmation"; `panic_sell_count` high → soften SELL language
5. Output `Recommendation` with full `reasoning_chain` (numbered steps) and merged citations.
6. LLM (optional) rewrites the chain into readable prose but **cannot change action/confidence or invent citations**. Validate that every cited `source_id` exists in the retrieved set; otherwise strip the output or mark it "uncited".

## 8. Required demos (build the seed data to guarantee these)
- **Personalization demo**: ticker X with identical market input → 3 users (conservative retiree, moderate salaried, aggressive trader) produce different actions + notes. Show side by side.
- **Degraded-data demo**: toggle in the sidebar: "Simulate sentiment feed outage" and "Missing filing for ticker". Pipeline still completes, UI shows a warning banner, confidence lowered, nothing uncited.
- **Conflict demo**: a seeded ticker where momentum says BULLISH and filings say CAUTIONARY; synthesis explains the disagreement.
- **End-to-end workflow**: raw data ingest → 5 agents → synthesis → recommendation, with a step trace visible in the UI.

## 9. Dashboard (Streamlit) — required panels
1. Sidebar: user selector, ticker selector, failure-simulation toggles, "Run analysis" button
2. Market signals table: ticker | momentum | volume | sentiment | confidence (color-coded labels)
3. Price chart with signal markers (Plotly)
4. Synthesized recommendation card: action, confidence, reasoning chain, conflicts
5. Sources panel: each citation with doc title, excerpt, relevance score
6. Portfolio/watchlist panel: holdings, concentration pie, risk score
7. Compare-users tab (personalization demo)
8. Metrics tab: latency per agent, total latency, concentration score, signal accuracy
9. Pipeline trace: the ordered step log

## 10. Metrics (log per session to SQLite; need at least 3)
- Per-agent latency and end-to-end latency (show parallel vs sequential speedup)
- Portfolio concentration score (HHI) before and after recommendation
- Signal accuracy vs 30-day forward return (run backtest on simulated history, report hit rate)
- Citation coverage (% of claims with citations)
- Degraded-agent count
- Optional: confidence calibration (bucket confidence vs realized hit rate)

## 11. Synthetic corpus guidelines (disclose it's synthetic)
15-30 short documents across 5-6 tickers: quarterly results transcripts, SEBI-style disclosure summaries, management commentary, risk-factor sections, a few news items. Include some deliberate contradictions and one ticker with **no** filing (for the missing-document test). Each doc has metadata: `source_id, ticker, doc_type, date, title`.

## 12. Build order (phases; each ends with something runnable)
1. **Contracts + config + profiles store** (schemas, SQLite, 3 seed users)
2. **Market data sim** (seeded, injected anomalies, 5 tickers x 1 year) + indicator functions with unit tests
3. **3 signal agents** (momentum, volume, sentiment) + parallel orchestrator
4. **Corpus + RAG ingest/retriever + Filings agent** with citations
5. **Risk agent + synthesizer** (conflicts + personalization)
6. **Failure handling** (timeouts, fallbacks, toggles)
7. **Metrics + backtest**
8. **Streamlit dashboard** wired to the orchestrator
9. **ARCHITECTURE.md, README, demo script**, full run-through, polish

## 13. Non-negotiables
- Numbers come from code; LLM only explains.
- Every recommendation shows reasoning + sources + confidence.
- No uncited claims in output. Strip or flag them.
- Seeded randomness so demos are reproducible.
- Pipeline never crashes on bad data; it degrades and says so.
- Disclaimer: "Educational/simulated, not investment advice (SEBI-registered advice required)."
- Disclose simulated data and synthetic documents in UI and README.

## 13A. WINNING EDGE: score-maximizing requirements (treat as mandatory)

### Rubric-to-feature map (every point must be demonstrable on screen)
| Criterion (weight) | Concrete feature that earns the points | Where it shows |
|---|---|---|
| Signal quality (20) | 3 independent dimensions + a 4th (filings); per-signal confidence derived from signal strength; evidence bullets WITH numbers ("RSI 74.2 > 70 threshold") | Signals table + evidence expander |
| Multi-agent (20) | `asyncio.gather` of 5 agents; typed output contracts; synthesis consumes only contracts; latency chart parallel vs sequential | Trace + Metrics tab |
| Retrieval/attribution (15) | Hybrid retrieval (embedding + BM25), ticker metadata filter, citation with doc, date, excerpt, score; **citation validator** rejects any source_id not retrieved; "Show source passage" highlight | Sources panel |
| Personalization (15) | Compare-users tab: same ticker, same signals, 3 profiles, different action + reasons; concentration override; behavioral nudge | Compare tab |
| Engineering (10) | Seeded sim, one-command run (`make demo`), pytest for indicators/synthesizer/validator, SQLite persistence, timeouts, fallbacks, failure toggles | Sidebar toggles + tests |
| Performance/eval (10) | Metrics per session: per-agent latency, e2e latency, HHI before/after, citation coverage, backtest hit rate vs baselines, **calibration curve** | Metrics tab |
| Explainability/commercial (10) | Numbered reasoning chain, plain-language labels, conflicts explained, SEBI-aware disclaimer, business-model slide | Rec card + deck |

### Differentiators (build in this priority order after the MVP is solid)
1. **Confidence calibration chart**: bucket past signal confidences (0-0.2 ... 0.8-1.0), plot realized hit rate vs stated confidence. Report Brier score. Most teams skip this.
2. **Honest backtest**: 30-day forward returns on the simulated history; compare against (a) random signal, (b) buy-and-hold; report hit rate, avg forward return per label, and sample size. State limitations plainly (simulated data, small N). Never claim edge that isn't there.
3. **Agent disagreement panel**: matrix of agent labels per ticker; when opposing, show "Conflict: momentum BULLISH vs filings CAUTIONARY -> resolved as HOLD (confidence reduced 0.74 -> 0.52) because ..."
4. **Behavioral nudge engine**: rules over `behavior` (panic-sell history, momentum chasing, short average holding period) that add a personalized, specific warning or encouragement.
5. **Portfolio what-if**: "If you act on this recommendation, HHI goes 0.31 -> 0.24, top holding 38% -> 29%." Concrete before/after.
6. **Personalized watchlist alerts**: alert only when a signal is relevant to THIS user's risk profile and holdings.
7. **Persistent sessions**: store prior recommendations and user decisions; show "last time you were advised X; the signal has changed because Y".
8. **Plain-language mode toggle**: beginner view (words) vs analyst view (numbers).

### Scoring traps to avoid
- Any recommendation without citations or reasoning on screen.
- Hardcoded or fake-looking confidence values (use formulas; document them in ARCHITECTURE.md).
- Claiming accuracy numbers not produced by the code in the demo.
- LLM output that changes action/confidence or invents sources (validator must block it).
- Demo paths that depend on a live API. Everything must work offline with the deterministic fallback.
- Dashboard clutter. Lead with the recommendation card, details one click deeper.

### Seed scenarios (build the data so these work every time)
- **RELIANCE**: bullish momentum + volume spike + supportive filing -> clean BUY-type signal, different actions per user.
- **TCS**: bullish momentum but cautionary filing (guidance cut/attrition) -> CONFLICT demo.
- **ITC**: sentiment feed unavailable -> DEGRADED demo.
- **HDFCBANK**: no filing in corpus -> MISSING DOCUMENT demo, filings agent returns UNKNOWN with `degraded_reason`, no uncited claims.
- **INFY**: bearish divergence (price up, volume falling) -> volume agent warning.
- **Users**: Meera (62, conservative, retiree, 45% in ITC -> concentration override), Arjun (32, moderate, salaried SIP investor), Rohan (24, aggressive, chases momentum, panic-sold twice -> behavioral nudge).

### ARCHITECTURE.md required contents (judges read it)
Agent roster and output contract; confidence formulas per agent; synthesis weights and conflict rules; personalization rules table; degradation matrix (failure -> behavior); metrics definitions; data and corpus disclosure; known limitations.

## 13B. Demo script (5 minutes, rehearse twice)
1. **0:00-0:30 Problem**: retail investors drown in feeds; tools are siloed, generic and unexplained.
2. **0:30-1:30 End-to-end**: pick RELIANCE as Arjun. Click Run. Walk the trace: ingest -> 5 agents in parallel (show latencies) -> synthesis -> recommendation. Click a citation, source passage highlights.
3. **1:30-2:30 Personalization**: Compare-users tab, same inputs, three different outputs. Point out Meera's concentration override and Rohan's behavioral nudge.
4. **2:30-3:15 Conflict**: switch to TCS. Show the disagreement panel and the lowered confidence.
5. **3:15-4:00 Resilience**: toggle sentiment-feed outage on ITC and open HDFCBANK (missing filing). Pipeline completes, banner explains, nothing uncited.
6. **4:00-4:40 Evidence**: Metrics tab: latency (parallel vs sequential), HHI before/after, backtest vs baselines, calibration curve. Mention limitations honestly.
7. **4:40-5:00 Business**: freemium watchlist, paid personalized tier, B2B API for fintechs/advisors/wealth managers; SEBI-aware framing.

Backup plan: pre-recorded 2-minute screen capture, plus screenshots of each tab, in case of a live failure.

## 14. Handoff prompt (copy to a new AI model)
```
I'm building "VibeFinance" for a hackathon. The attached blueprint is the full spec.
Follow its repo structure, data contracts (section 5) and build order (section 12).
Also obey section 13A (winning-edge requirements, seed scenarios, scoring traps) and 13B (demo script).
Everything must run offline with deterministic fallbacks; numbers come from code, never from the LLM.
Current phase: <PHASE N>. Files already done: <list>.
Write complete, runnable code for the next files only, with brief tests.
Don't change the data contracts without telling me. Keep the code simple and well-commented.
```

## 15. Progress tracker (update as you go and re-paste to the next AI)
- [ ] Phase 1  - [ ] Phase 2  - [ ] Phase 3  - [ ] Phase 4  - [ ] Phase 5
- [ ] Phase 6  - [ ] Phase 7  - [ ] Phase 8  - [ ] Phase 9
Notes / deviations: ...
