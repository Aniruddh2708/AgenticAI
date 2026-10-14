"""API failures must distinguish useful analysis from successful persistence."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import vibefinance.api as api
import vibefinance.orchestrator as orchestrator


@pytest.fixture(autouse=True)
def local_api_configuration(monkeypatch):
    # Each test owns its optional synthetic authentication setting. Never depend
    # on or expose a token injected into the real development environment.
    monkeypatch.delenv("VIBEFINANCE_API_TOKEN", raising=False)


def storage_failure(*args, **kwargs):
    raise sqlite3.OperationalError("Synthetic storage failure")


def assert_unsaved(session):
    assert session["persistence"]["status"] == "failed"
    assert "not saved" in session["persistence"]["error"]
    assert any("not saved" in warning for warning in session["warnings"])
    persistence_steps = [step["detail"] for step in session["trace"] if step["step"] == "Persistence"]
    assert persistence_steps and all("not saved" in detail for detail in persistence_steps)
    assert all("saved atomically" not in detail for detail in persistence_steps)
    assert len(session["recommendation"]["agent_outputs"]) == 5


def test_startup_database_failure_uses_disclosed_seed_profiles_without_default_store(tmp_path, monkeypatch):
    class FailedStore:
        def __init__(self, *args, **kwargs):
            storage_failure()

    monkeypatch.setattr(api, "Store", FailedStore)
    unintended_default_store_calls = []

    def unexpected_default_store(*args, **kwargs):
        unintended_default_store_calls.append(True)
        raise AssertionError("Startup failure must not silently switch databases")

    monkeypatch.setattr(orchestrator, "Store", unexpected_default_store)
    with TestClient(api.create_app(tmp_path / "unavailable.sqlite3")) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "degraded"
        assert health.json()["storage_available"] is False
        profiles = client.get("/profiles").json()
        assert {p["user_id"] for p in profiles} == {"meera", "arjun", "rohan"}
        response = client.post("/analyze", json={"user_id": "arjun", "ticker": "RELIANCE.NS"})
        assert response.status_code == 200
        assert response.json()["recommendation"]["action"] == "ACCUMULATE"
        assert_unsaved(response.json())
        assert any("seed profiles" in warning for warning in response.json()["warnings"])
        comparison = client.post("/compare", json={"ticker": "RELIANCE.NS"})
        assert comparison.status_code == 200
        assert {s["recommendation"]["user_id"] for s in comparison.json()} == {"meera", "arjun", "rohan"}
        for session in comparison.json():
            assert_unsaved(session)
        scan = client.post("/watchlist", json={"user_id": "arjun", "tickers": ["RELIANCE.NS"]})
        assert scan.status_code == 200
        assert_unsaved(scan.json()["sessions"][0])
        assert client.get("/history/arjun").status_code == 503
    assert unintended_default_store_calls == []


def test_runtime_database_failure_returns_503_for_storage_operations(tmp_path, monkeypatch):
    application = api.create_app(tmp_path / "runtime.sqlite3")
    with TestClient(application) as client:
        original_profile = client.get("/profiles/arjun").json()
        monkeypatch.setattr(application.state.store, "connect", storage_failure)
        operations = [
            ("put", "/profiles/arjun", {"json": original_profile}),
            ("delete", "/profiles/arjun", {}),
            ("get", "/history/arjun", {}),
            ("get", "/sessions/missing", {}),
            ("post", "/sessions/missing/decision", {"json": {"decision": "watch"}}),
            ("get", "/sessions/missing/decisions", {}),
            ("get", "/sessions/missing/sources/example", {}),
        ]
        for method, path, options in operations:
            response = getattr(client, method)(path, **options)
            assert response.status_code == 503, (method, path, response.status_code)
            assert "unavailable" in response.json()["detail"]
        # Read-only seeded analysis remains available, but must never claim it was saved.
        response = client.post("/analyze", json={"ticker": "RELIANCE.NS", "user_id": "arjun"})
        assert response.status_code == 200
        assert_unsaved(response.json())


def test_first_health_probe_detecting_database_failure_reports_degraded(tmp_path, monkeypatch):
    application = api.create_app(tmp_path / "health.sqlite3")
    with TestClient(application) as client:
        assert client.get("/health").json()["status"] == "ok"
        monkeypatch.setattr(application.state.store, "connect", storage_failure)
        result = client.get("/health").json()
        assert result["storage_available"] is False
        assert result["status"] == "degraded"
        assert result["profiles"] == 3


def test_analysis_write_failure_is_usable_but_not_in_history(tmp_path, monkeypatch):
    application = api.create_app(tmp_path / "write.sqlite3")
    with TestClient(application) as client:
        monkeypatch.setattr(application.state.store, "save_session", storage_failure)
        response = client.post("/analyze", json={"ticker": "RELIANCE.NS", "user_id": "arjun"})
        assert response.status_code == 200
        session = response.json()
        assert session["recommendation"]["action"] == "ACCUMULATE"
        assert_unsaved(session)
        assert client.get("/history/arjun").json() == []
        assert client.get(f"/sessions/{session['session_id']}").status_code == 404


def test_optional_bearer_authentication_preserves_public_health(tmp_path, monkeypatch):
    synthetic_token = "synthetic-test-token"
    monkeypatch.setenv("VIBEFINANCE_API_TOKEN", synthetic_token)
    with TestClient(api.create_app(tmp_path / "auth.sqlite3")) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["authentication_enabled"] is True
        assert client.get("/profiles").status_code == 401
        assert client.get("/docs").status_code == 401
        assert client.post("/analyze", json={}).status_code == 401
        for authorization in ("wrong", "Bearer incorrect", "bearer " + synthetic_token):
            assert client.get("/profiles", headers={"Authorization": authorization}).status_code == 401
        assert client.get("/profiles", headers={"Authorization": b"Bearer \xff"}).status_code == 401
        accepted = client.get("/profiles", headers={"Authorization": "Bearer " + synthetic_token})
        assert accepted.status_code == 200
        assert len(accepted.json()) == 3
        assert "Server-Timing" in accepted.headers


def test_absent_token_retains_local_demo_access(tmp_path):
    with TestClient(api.create_app(tmp_path / "local.sqlite3")) as client:
        assert client.get("/health").json()["authentication_enabled"] is False
        assert client.get("/profiles").status_code == 200


def test_empty_corpus_still_serves_disclosed_degraded_analysis(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBEFINANCE_CORPUS_PATH", str(tmp_path / "missing-corpus"))
    with TestClient(api.create_app(tmp_path / "empty-corpus.sqlite3")) as client:
        health = client.get("/health").json()
        assert health["status"] == "degraded" and health["corpus_chunks"] == 0
        response = client.post("/analyze", json={"user_id": "arjun", "ticker": "RELIANCE.NS"})
        assert response.status_code == 200
        assert response.json()["recommendation"]["action"] == "WATCH"
        assert response.json()["persistence"]["status"] == "saved"
