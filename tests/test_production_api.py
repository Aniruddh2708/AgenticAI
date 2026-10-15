"""Real signed identities and account-scoped routes, including optional TLS PostgreSQL."""
import json
import os
import time
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from vibefinance import api
from vibefinance.auth import OIDCVerifier
from vibefinance.config import ROOT
from vibefinance.profiles.production_store import StorageUnavailableError


@pytest.fixture
def individual_api(monkeypatch):
    jwt = pytest.importorskip("jwt")
    ec = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ec")
    project = "https://abcdefghijklmnopqrst.supabase.co"
    monkeypatch.setenv("VIBEFINANCE_AUTH_MODE", "supabase")
    monkeypatch.setenv("VIBEFINANCE_SUPABASE_URL", project)
    monkeypatch.setenv("VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_public-test-value-only")
    monkeypatch.setenv("VIBEFINANCE_API_TOKEN", "shared-demo-token-is-not-account-auth")
    key = ec.generate_private_key(ec.SECP256R1())
    public = {**json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key())),
              "kid": "account-test-key", "alg": "ES256", "use": "sig", "key_ops": ["verify"]}

    def jwks(request):
        assert str(request.url) == project + "/auth/v1/.well-known/jwks.json"
        return httpx.Response(200, json={"keys": [public]})

    clients = []

    def verifier(settings):
        client = httpx.Client(transport=httpx.MockTransport(jwks))
        clients.append(client)
        return OIDCVerifier(settings, client=client)

    monkeypatch.setattr(api, "OIDCVerifier", verifier)

    def headers(subject, **overrides):
        now = int(time.time())
        claims = {"iss": project + "/auth/v1", "aud": "authenticated", "sub": subject,
                  "role": "authenticated", "is_anonymous": False, "iat": now - 5,
                  "exp": now + 300, **overrides}
        return {"Authorization": "Bearer " + jwt.encode(claims, key, algorithm="ES256",
                                                          headers={"kid": public["kid"]})}

    yield headers
    for client in clients:
        client.close()


def test_managed_routes_reject_demo_token_forged_account_and_expired_identity(individual_api, monkeypatch, tmp_path):
    monkeypatch.setattr(api, "initialize_production_storage", lambda: None)
    monkeypatch.setattr(api, "production_storage_health", lambda: False)
    monkeypatch.setattr(api, "Store", lambda *a, **k: pytest.fail("Managed startup must never seed a demo store"))
    with TestClient(api.create_app(tmp_path / "must-not-exist.sqlite3")) as client:
        health = client.get("/health").json()
        assert health["status"] == "degraded" and health["storage_available"] is False
        assert health["auth_mode"] == "supabase" and "profiles" not in health
        for headers in ({}, {"Authorization": "Bearer shared-demo-token-is-not-account-auth"},
                        {"X-User-ID": "alice", "X-Account-ID": "a" * 64},
                        individual_api("alice", iat=int(time.time()) - 300, exp=int(time.time()) - 120),
                        individual_api("alice", role="service_role")):
            for path in ("/profiles", "/sessions/unknown", "/evaluation/forecast", "/docs"):
                assert client.get(path, headers=headers).status_code == 401
        assert client.get("/benchmark", headers=individual_api("alice")).status_code == 403
        assert client.get("/evaluation/policies", headers=individual_api("alice")).status_code == 403
    assert not (tmp_path / "must-not-exist.sqlite3").exists()


def test_managed_storage_failure_is_503_without_shared_profile_fallback(individual_api, monkeypatch, tmp_path):
    monkeypatch.setattr(api, "initialize_production_storage", lambda: None)

    def unavailable(account):
        raise StorageUnavailableError("Private database details must not appear")

    monkeypatch.setattr(api, "create_production_store", unavailable)
    with TestClient(api.create_app(tmp_path / "must-not-exist.sqlite3")) as client:
        headers = individual_api("alice")
        for method, path, options in (
            ("get", "/profiles", {}), ("get", "/profiles/meera", {}),
            ("post", "/analyze", {"json": {"user_id": "meera"}}),
            ("get", "/history/meera", {}), ("get", "/sessions/unknown", {})):
            response = getattr(client, method)(path, headers=headers, **options)
            assert response.status_code == 503
            assert "Private database" not in response.text
            assert "Meera" not in response.text
    assert not (tmp_path / "must-not-exist.sqlite3").exists()


@pytest.mark.skipif(not os.getenv("VIBEFINANCE_TEST_POSTGRES_URL"),
                    reason="Requires the disposable real TLS PostgreSQL integration fixture")
def test_signed_accounts_cannot_access_each_others_profiles_sessions_or_decisions(individual_api, monkeypatch, tmp_path):
    monkeypatch.setenv("VIBEFINANCE_DATABASE_URL", os.environ["VIBEFINANCE_TEST_POSTGRES_URL"])
    monkeypatch.delenv("VIBEFINANCE_ALLOW_INSECURE_LOCAL_DATABASE", raising=False)
    alice = individual_api("alice-" + uuid.uuid4().hex)
    bob = individual_api("bob-" + uuid.uuid4().hex)
    profile = json.loads((ROOT / "data/users.json").read_text())[0]
    profile.update(user_id="same-profile-id", name="Alice private profile")
    profile["holdings"] = {"ITC.NS": .45, "CASH": .55}
    profile["max_single_stock_pct"] = .15
    application = api.create_app(tmp_path / "must-not-exist.sqlite3")
    with TestClient(application) as client:
        assert client.get("/profiles", headers=alice).json() == []
        assert client.get("/profiles", headers=bob).json() == []
        assert client.put("/profiles/same-profile-id", headers=alice, json=profile).status_code == 200
        assert client.get("/profiles/same-profile-id", headers=bob).status_code == 404
        assert client.get("/history/same-profile-id", headers=bob).status_code == 404
        bob_profile = {**profile, "name": "Bob private profile"}
        assert client.put("/profiles/same-profile-id", headers=bob, json=bob_profile).status_code == 200
        request = {"user_id": "same-profile-id", "ticker": "ITC.NS", "missing_filing": True}
        result = client.post("/analyze", headers=alice, json=request)
        assert result.status_code == 200
        session = result.json()
        assert session["persistence"]["status"] == "saved"
        assert session["recommendation"]["action"] == "REDUCE"
        assert session["recommendation"]["decision_basis"] == "portfolio_policy"
        saved = session["session_id"]
        for path in (f"/sessions/{saved}", f"/sessions/{saved}/decisions",
                     f"/sessions/{saved}/sources/profile:same-profile-id:snapshot"):
            assert client.get(path, headers=bob).status_code == 404
        assert client.post(f"/sessions/{saved}/decision", headers=bob, json={"decision": "watch"}).status_code == 404
        assert client.post(f"/sessions/{saved}/decision", headers=alice, json={"decision": "watch"}).status_code == 200
        assert client.get(f"/sessions/{saved}/decisions", headers=alice).json()[0]["decision"] == "watch"
        assert client.get("/history/same-profile-id", headers=bob).json() == []
        assert client.get("/profiles/same-profile-id", headers=bob).json()["name"] == "Bob private profile"
    # Independent API startup reconnects to the same durable account data.
    with TestClient(api.create_app(tmp_path / "still-must-not-exist.sqlite3")) as client:
        assert client.get(f"/sessions/{saved}", headers=alice).status_code == 200
        assert client.get(f"/sessions/{saved}", headers=bob).status_code == 404
        assert client.get("/profiles", headers=alice).json()[0]["name"] == "Alice private profile"
    assert not list(tmp_path.glob("*.sqlite3"))
