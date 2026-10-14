"""Functional smoke check against a running API; exits nonzero on broken demo paths."""
import httpx


def main():
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
        def post(path, payload):
            response = client.post(path, json=payload)
            response.raise_for_status()
            return response.json()

        health = client.get("/health")
        health.raise_for_status()
        assert health.json()["corpus_chunks"] >= 15
        compare = post("/compare", {"ticker": "RELIANCE.NS"})
        actions = {s["recommendation"]["user_id"]: s["recommendation"]["action"] for s in compare}
        assert actions == {"meera": "REDUCE", "arjun": "ACCUMULATE", "rohan": "BUY"}, actions
        assert len({s["market_fingerprint"] for s in compare}) == 1
        for ticker in ("TCS.NS", "ITC.NS", "HDFCBANK.NS", "INFY.NS"):
            session = post("/analyze", {"ticker": ticker})
            rec = session["recommendation"]
            assert len(rec["agent_outputs"]) == 5 and rec["citations"]
            if ticker == "TCS.NS":
                assert rec["conflicts"] and rec["action"] == "HOLD"
            if ticker in {"ITC.NS", "HDFCBANK.NS"}:
                assert session["metrics"]["degraded_agent_count"] >= 1
            if ticker == "INFY.NS":
                assert next(a for a in rec["agent_outputs"] if a["dimension"] == "volume")["label"] == "SPIKE_DOWN"
            for citation in rec["citations"]:
                source = client.get(f"/sessions/{session['session_id']}/sources/{citation['chunk_id']}")
                source.raise_for_status()
                assert source.json()["excerpt"] == citation["excerpt"]
        session = post("/analyze", {"sentiment_outage": True, "missing_filing": True})
        assert session["recommendation"]["action"] == "WATCH"
        assert session["metrics"]["degraded_agent_count"] == 2
        evaluation = client.get("/evaluation")
        evaluation.raise_for_status()
        assert evaluation.json()["sample_size"] > 0
        print("API smoke passed: personalized actions, conflict, outages, missing filings, divergence, sources and evaluation.")


if __name__ == "__main__":
    main()
