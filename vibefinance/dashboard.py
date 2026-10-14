import os

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from vibefinance.config import DISCLAIMER, TICKERS
from vibefinance.data.market_sim import generate_market

API = os.getenv("VIBEFINANCE_API_URL", "http://127.0.0.1:8000")


def call(method, path, **kwargs):
    response = httpx.request(method, API + path, timeout=60, **kwargs)
    response.raise_for_status()
    return response.json()


def signal_table(session):
    rows = [{"Dimension": a["dimension"].title(), "Signal": a["label"],
             "Confidence": a["confidence"], "Status": a["status"]} for a in session["recommendation"]["agent_outputs"]]
    colors = {"BULLISH": "#c8e6c9", "POSITIVE": "#c8e6c9", "SUPPORTIVE": "#c8e6c9", "SPIKE_UP": "#c8e6c9",
              "BEARISH": "#ffcdd2", "NEGATIVE": "#ffcdd2", "CAUTIONARY": "#ffcdd2", "RISK_HIGH": "#ffcdd2"}
    style = pd.DataFrame(rows).style.map(lambda value: f"background-color: {colors.get(value, '#fff3cd')}; color: #151515", subset=["Signal"])
    st.dataframe(style, hide_index=True, use_container_width=True,
                 column_config={"Confidence": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1)})


def render_sources(session):
    st.caption("Filings/news are fabricated. Market and profile citations are input snapshots, not external documents. Relevance is a retrieval score, not a probability.")
    for citation in session["recommendation"]["citations"]:
        with st.expander(citation["doc_title"]):
            st.caption(f"{citation['source_id']} · {citation['date']} · relevance {citation['score']:.3f}")
            st.write(citation["excerpt"])
            if st.button("Show source passage", key=f"passage-{session['session_id']}-{citation['chunk_id']}"):
                source = call("GET", f"/sessions/{session['session_id']}/sources/{citation['chunk_id']}")
                st.markdown("**Exact registered source passage**")
                st.code(source["excerpt"], language=None)
                st.success("Displayed excerpt matches the session source registry.")


def main():
    st.set_page_config(page_title="VibeFinance", page_icon="📈", layout="wide")
    st.title("VibeFinance")
    st.caption("Explainable market intelligence · Indian retail investor demo")
    st.info("Demo uses seeded simulated prices and synthetic company documents. Every figure is computed; no LLM or API key is required.")
    st.caption(DISCLAIMER)
    try:
        profiles = call("GET", "/profiles")
    except (httpx.HTTPError, ValueError):
        st.error("API unavailable. Start both services with `make demo` from the repository root.")
        st.stop()
    if not profiles:
        st.warning("Create a profile through the API to begin.")
        st.stop()
    labels = {p["user_id"]: p["name"] for p in profiles}
    with st.sidebar:
        st.header("Analysis controls")
        user = st.selectbox("Investor", list(labels), format_func=labels.get, index=list(labels).index("arjun") if "arjun" in labels else 0)
        ticker = st.selectbox("NSE ticker", TICKERS)
        sentiment_outage = st.toggle("Simulate sentiment feed outage")
        missing_filing = st.toggle("Missing filing for ticker")
        beginner = st.toggle("Plain-language mode", value=True)
        run = st.button("Run analysis", type="primary", use_container_width=True)
        st.caption("ITC always simulates a sentiment outage. HDFCBANK has no filing in the corpus.")
    profile = next(p for p in profiles if p["user_id"] == user)
    request = {"user_id": user, "ticker": ticker, "sentiment_outage": sentiment_outage, "missing_filing": missing_filing}
    key = (user, ticker, sentiment_outage, missing_filing)
    if run or st.session_state.get("analysis_key") != key:
        try:
            with st.spinner("Retrieving sources and running five agents…"):
                st.session_state.analysis = call("POST", "/analyze", json=request)
                st.session_state.analysis_key = key
        except (httpx.HTTPError, ValueError) as exc:
            st.error(f"Analysis request failed ({type(exc).__name__}). Check the API logs and retry.")
            st.stop()
    session = st.session_state.analysis
    rec = session["recommendation"]
    if session["warnings"]:
        st.warning(" · ".join(session["warnings"]))
    left, right = st.columns([3, 1])
    with left:
        st.subheader(f"{ticker.removesuffix('.NS')} · {rec['action']}")
        st.write(" ".join(rec["personalization_notes"][:2]))
    with right:
        st.metric("Signal confidence", f"{rec['confidence']:.0%}")
        st.caption("Formula-based signal strength; not a calibrated probability of profit.")
    tabs = st.tabs(["Analysis", "Sources", "Portfolio & watchlist", "Compare users", "Metrics", "History"])
    with tabs[0]:
        if beginner:
            readable = {"BUY": "Directional demo signal; check your limits before acting.",
                        "ACCUMULATE": "Consider staged entries rather than a single large trade.",
                        "HOLD": "Wait while the evidence or profile constraints settle.",
                        "REDUCE": "Review a gradual reduction in exposure.", "AVOID": "Evidence does not support new exposure.",
                        "WATCH": "Important evidence is missing; gather more information."}
            st.write(readable[rec["action"]])
        signal_table(session)
        # The dashboard currently exposes only simulated mode, so chart and agents share this exact frame.
        frame = generate_market(ticker)
        fig = px.line(frame, x="date", y="close", title="Seeded simulated price · INR")
        fig.add_trace(go.Scatter(x=[frame.date.iloc[-1]], y=[frame.close.iloc[-1]], mode="markers",
                                marker={"size": 12}, name=rec["action"]))
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("Decision explanation", expanded=True):
            for step in rec["reasoning_chain"]:
                st.write(step)
        if rec["conflicts"]:
            st.subheader("Agent disagreement")
            for conflict in rec["conflicts"]:
                st.warning(conflict)
        with st.expander("Agent evidence and latency"):
            for agent in rec["agent_outputs"]:
                st.markdown(f"**{agent['dimension'].title()} · {agent['label']} · {agent['latency_ms']:.2f} ms**")
                for bullet in agent["evidence"]:
                    st.write("• " + bullet)
        st.subheader("Pipeline trace")
        for index, step in enumerate(session["trace"], 1):
            st.write(f"{index}. **{step['step']}** — {step['detail']}")
    with tabs[1]:
        render_sources(session)
    with tabs[2]:
        metrics = session["metrics"]
        holdings = metrics["holdings_before"]
        chart = pd.DataFrame({"Holding": list(holdings), "Weight": list(holdings.values())})
        st.plotly_chart(px.pie(chart, names="Holding", values="Weight", title="Portfolio allocation including cash"), use_container_width=True)
        st.write(f"Single-stock limit: {profile['max_single_stock_pct']:.0%}; risk tolerance: {profile['risk_tolerance']}.")
        st.subheader("Portfolio what-if")
        st.write(f"Illustrative {metrics['trade_weight']:+.1%} portfolio-weight trade in {ticker}, funded from cash.")
        a, b = st.columns(2)
        a.metric("HHI before → after", f"{metrics['hhi_before']:.3f} → {metrics['hhi_after']:.3f}")
        b.metric("Largest equity holding", f"{metrics['top_holding_before']:.0%} → {metrics['top_holding_after']:.0%}")
        st.caption("What-if changes are illustrative only; profiles and holdings are not modified.")
        watched = st.multiselect("Watchlist tickers", TICKERS, default=[t for t in profile["holdings"] if t in TICKERS])
        if st.button("Scan personalized watchlist", disabled=not watched):
            st.session_state.watchlist = call("POST", "/watchlist", json={"user_id": user, "tickers": watched})
            st.session_state.watchlist_key = (user, tuple(watched))
        if st.session_state.get("watchlist_key") == (user, tuple(watched)):
            scan = st.session_state.watchlist
            matrix = [{"Ticker": s["recommendation"]["ticker"], **{a["dimension"]: a["label"] for a in s["recommendation"]["agent_outputs"]},
                       "Action": s["recommendation"]["action"]} for s in scan["sessions"]]
            st.dataframe(matrix, hide_index=True, use_container_width=True)
            for alert in scan["alerts"]:
                st.info(f"{alert['ticker']} · {alert['action']} · " + " ".join(alert["reason"]))
            if not scan["alerts"]:
                st.write("No actionable alerts pass this profile's policy and confidence threshold.")
    with tabs[3]:
        st.caption("All users receive the identical market frame and corpus. Only the profile changes.")
        if st.button("Compare all three profiles"):
            st.session_state.comparison = call("POST", "/compare", json=request)
            st.session_state.comparison_key = key[1:]
        if st.session_state.get("comparison_key") == key[1:]:
            results = st.session_state.comparison
            columns = st.columns(len(results))
            for column, item in zip(columns, results):
                recommendation = item["recommendation"]
                with column:
                    st.subheader(labels.get(recommendation["user_id"], recommendation["user_id"]))
                    st.metric(recommendation["action"], f"{recommendation['confidence']:.0%}")
                    for note in recommendation["personalization_notes"]:
                        st.write(note)
            st.caption("Shared input: " + results[0]["market_fingerprint"])
    with tabs[4]:
        metrics = session["metrics"]
        a, b, c = st.columns(3)
        a.metric("Compute latency", f"{metrics['total_latency_ms']:.1f} ms")
        b.metric("Degraded / failed agents", f"{metrics['degraded_agent_count']} / {metrics['failed_agent_count']}")
        c.metric("Evidence with provenance", f"{metrics['citation_coverage']:.0%}" if metrics["citation_coverage"] is not None else "N/A")
        latency = pd.DataFrame({"Agent": list(metrics["agent_latency_ms"]), "ms": list(metrics["agent_latency_ms"].values())})
        st.plotly_chart(px.bar(latency, x="Agent", y="ms", title="Observed agent latency"), use_container_width=True)
        st.write(f"Parallel wall time {metrics['parallel_agents_ms']:.2f} ms; sum of observed agent times {metrics['sum_agent_latency_ms']:.2f} ms; estimated overlap ratio {metrics['estimated_parallel_speedup']:.2f}×.")
        st.caption("The sum is not a measured sequential benchmark: wrapper timings include thread scheduling. Compute latency excludes persistence/HTTP; provenance coverage does not verify semantic truth.")
        evaluation = call("GET", "/evaluation")
        st.subheader("Walk-forward technical direction evaluation")
        st.dataframe([{ "Method": "Momentum", "Hit rate": evaluation["hit_rate"]},
                      {"Method": "Seeded random", "Hit rate": evaluation["random_hit_rate"]},
                      {"Method": "Always up / buy-and-hold", "Hit rate": evaluation["buy_hold_hit_rate"]}], hide_index=True)
        st.write(f"N = {evaluation['sample_size']} · Brier score {evaluation['brier_score']:.4f}")
        st.write("Average 30-session forward return by signal label:", evaluation["mean_forward_return_by_label"])
        calibration = pd.DataFrame([b for b in evaluation["calibration"] if b["count"] > 0])
        fig = px.scatter(calibration, x="mean_probability_up", y="realized_up_rate", size="count", hover_data=["bucket", "count"],
                         title="Up-direction probability calibration (heuristic probabilities)")
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration"))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(evaluation["limitations"])
    with tabs[5]:
        history = call("GET", f"/history/{user}", params={"ticker": ticker, "limit": 10})
        st.dataframe([{ "Session": s["session_id"][:8], "Action": s["recommendation"]["action"],
                      "Confidence": s["recommendation"]["confidence"], "Warnings": len(s["warnings"])} for s in history], hide_index=True)
        prior = [s for s in history if s["session_id"] != session["session_id"]]
        if prior:
            old = prior[0]["recommendation"]
            changes = [f"{a['dimension']}: {old_a['label']} → {a['label']}" for a, old_a in zip(rec["agent_outputs"], old["agent_outputs"]) if a["label"] != old_a["label"]]
            st.write(f"Previous action {old['action']} → {rec['action']}. " + ("; ".join(changes) if changes else "Agent labels are unchanged; profile or evidence availability may still differ."))
        choice = st.selectbox("Record your demo decision", ["watch", "follow", "skip"])
        if st.button("Save decision"):
            call("POST", f"/sessions/{session['session_id']}/decision", json={"decision": choice})
            st.success("Decision saved. No trade is placed.")
        decisions = call("GET", f"/sessions/{session['session_id']}/decisions")
        if decisions:
            st.dataframe(decisions, hide_index=True)
    st.divider()
    st.caption("Commercial concept: free watchlist → paid personalization → B2B research API. Production needs licensed data, audited models, security controls and appropriate SEBI compliance.")


if __name__ == "__main__":
    main()
