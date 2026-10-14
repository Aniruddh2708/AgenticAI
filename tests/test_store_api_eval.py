import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from vibefinance.agents.base import UserProfile
from vibefinance.api import create_app
from vibefinance.evaluation.backtest import backtest
from vibefinance.profiles.store import Store


def test_store_repeatability_and_profile_update(store):
    profile = store.profile("arjun")
    profile.name = "Arjun updated"
    store.save_profile(profile)
    reopened = Store(store.path)
    assert len(reopened.profiles()) == 3
    assert reopened.profile("arjun").name == "Arjun updated"
    profile.user_id = "new"
    reopened.save_profile(profile)
    reopened.delete_profile("new")
    with pytest.raises(KeyError):
        reopened.profile("new")
    reopened.delete_profile("meera")
    assert "meera" not in {p.user_id for p in Store(store.path).profiles()}


@pytest.mark.parametrize("behavior", [{"panic_sell_count": "unknown"}, {"avg_hold_days": float("nan")}, {"chases_momentum": "yes"}])
def test_profile_rejects_invalid_behavior(store, behavior):
    payload = store.profile("arjun").model_dump()
    payload["behavior"] = behavior
    with pytest.raises(ValidationError):
        UserProfile.model_validate(payload)


@pytest.mark.parametrize("holdings", [{"X": -1}, {"X": float("nan")}, {"X": .8, "Y": .8}])
def test_profile_rejects_invalid_weights(store, holdings):
    payload = store.profile("arjun").model_dump()
    payload["holdings"] = holdings
    with pytest.raises(ValidationError):
        UserProfile.model_validate(payload)


def test_api_functional_round_trip(tmp_path):
    with TestClient(create_app(tmp_path / "api.db")) as client:
        assert client.get("/health").json()["corpus_chunks"] >= 15
        assert len(client.get("/profiles").json()) == 3
        response = client.post("/analyze", json={"ticker": "RELIANCE.NS", "user_id": "arjun"})
        assert response.status_code == 200
        session = response.json()
        assert session["recommendation"]["action"] == "ACCUMULATE"
        session_id = session["session_id"]
        assert client.get(f"/sessions/{session_id}").json() == session
        assert client.post(f"/sessions/{session_id}/decision", json={"decision": "watch"}).json()["saved"]
        assert client.get(f"/sessions/{session_id}/decisions").json()[0]["decision"] == "watch"
        citation = session["recommendation"]["citations"][0]
        assert client.get(f"/sessions/{session_id}/sources/{citation['chunk_id']}").json()["excerpt"] == citation["excerpt"]
        assert client.get(f"/sessions/{session_id}/sources/fabricated").status_code == 404
        assert client.get("/history/arjun").json()[0]["session_id"] == session_id
        assert client.post("/analyze", json={"ticker": "BAD"}).status_code == 422
        assert client.post("/analyze", json={"user_id": "nobody"}).status_code == 404
        assert client.post(f"/sessions/{session_id}/decision", json={"decision": "trade"}).status_code == 422
        assert client.get("/evaluation").json()["sample_size"] > 0
        scan = client.post("/watchlist", json={"user_id": "meera", "tickers": ["ITC.NS"]}).json()
        assert scan["alerts"][0]["action"] == "REDUCE"


def test_backtest_sample_baselines_and_calibration():
    result = backtest()
    assert result == backtest()
    assert result["sample_size"] == len(result["rows"]) > 0
    assert 0 <= result["brier_score"] <= 1
    assert sum(bucket["count"] for bucket in result["calibration"]) == result["sample_size"]
    assert result["hit_rate"] == pytest.approx(sum(row["hit"] for row in result["rows"])/len(result["rows"]))
    for ticker in {row["ticker"] for row in result["rows"]}:
        dates = sorted(row["as_of"] for row in result["rows"] if row["ticker"] == ticker)
        assert len(dates) == len(set(dates))
