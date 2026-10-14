"""Functional smoke check against a running API; exits nonzero on broken demo paths."""
import os

import httpx


def main():
    token = os.getenv("VIBEFINANCE_API_TOKEN", "")
    headers = {"Authorization": "Bearer " + token} if token else {}
    with httpx.Client(base_url=os.getenv("VIBEFINANCE_API_URL", "http://127.0.0.1:8000"), timeout=60, headers=headers) as client:
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
            assert session["persistence"]["status"] == "saved"
            assert session["metrics"]["claim_support_coverage"] == 1
            assert all(len(agent["claims"]) == len(agent["evidence"]) for agent in rec["agent_outputs"])
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
                assert citation["excerpt"] in source.json()["document_text"]
        session = post("/analyze", {"sentiment_outage": True, "missing_filing": True})
        assert session["recommendation"]["action"] == "WATCH"
        assert session["metrics"]["degraded_agent_count"] == 2
        concentrated = post("/analyze", {"ticker": "ITC.NS", "user_id": "meera", "missing_filing": True})
        assert concentrated["recommendation"]["action"] == "REDUCE"
        assert concentrated["recommendation"]["decision_basis"] == "portfolio_policy"
        evaluation = client.get("/evaluation")
        evaluation.raise_for_status()
        assert evaluation.json()["sample_size"] > 0
        assert evaluation.json()["sample_size"] >= 500
        print("API smoke passed: personalized actions, conflict, outages, concentration precedence, divergence, supported claims, exact sources, persistence and evaluation.")


if __name__ == "__main__":
    main()
