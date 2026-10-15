"""Public hackathon entry, real analysis and preservation of protected demo data."""
import hashlib
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from vibefinance import api
from vibefinance.auth import AuthConfigurationError, public_demo_enabled
from vibefinance.profiles.store import Store


@pytest.mark.parametrize("settings, expected", [
    ({}, False),
    ({"RENDER": "true"}, True),
    ({"RENDER": "true", "VIBEFINANCE_PUBLIC_DEMO": "0"}, False),
    ({"VIBEFINANCE_PUBLIC_DEMO": "1"}, True),
    ({"RENDER": "true", "VIBEFINANCE_AUTH_MODE": "supabase", "VIBEFINANCE_PUBLIC_DEMO": "1"}, False),
    ({"RENDER": "true", "VIBEFINANCE_AUTH_MODE": "oidc", "VIBEFINANCE_PUBLIC_DEMO": "1"}, False),
])
def test_public_access_is_only_for_demo_mode(settings, expected):
    assert public_demo_enabled(settings) is expected


def test_mistyped_public_flag_fails_closed():
    with pytest.raises(AuthConfigurationError):
        public_demo_enabled({"VIBEFINANCE_PUBLIC_DEMO": "yes"})


@pytest.fixture
def public_render(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("VIBEFINANCE_AUTH_MODE", "demo")
    monkeypatch.delenv("VIBEFINANCE_PUBLIC_DEMO", raising=False)
    # Existing private password stays configured and is never needed by visitors.
    monkeypatch.setenv("VIBEFINANCE_API_TOKEN", "synthetic-private-test-token")


def test_public_visitor_can_analyze_and_read_citations_without_token(public_render, tmp_path):
    with TestClient(api.create_app(tmp_path / "state.sqlite3")) as client:
        assert client.get("/").status_code == 200
        health = client.get("/health").json()
        assert health["public_demo"] is True
        assert health["authentication_enabled"] is False
        assert len(client.get("/profiles").json()) == 3
        response = client.post("/analyze", json={"user_id": "meera", "ticker": "RELIANCE.NS"})
        assert response.status_code == 200
        session = response.json()
        assert session["persistence"]["status"] == "saved"
        assert session["recommendation"]["action"] == "REDUCE"
        assert session["recommendation"]["decision_basis"] == "portfolio_policy"
        saved = session["session_id"]
        source = session["sources"][0]
        passage = client.get(f"/sessions/{saved}/sources/{source['chunk_id']}")
        assert passage.status_code == 200
        assert passage.json()["excerpt"] == source["excerpt"]
        assert client.post(f"/sessions/{saved}/decision", json={"decision": "watch"}).status_code == 200
        assert client.get("/history/meera").json()[0]["session_id"] == saved


def test_public_storage_preserves_and_never_exposes_private_demo(public_render, tmp_path, monkeypatch):
    original = tmp_path / "vibefinance.sqlite3"
    private = Store(original)
    profile = private.profile("arjun").model_copy(update={"user_id": "private-investor", "name": "Private investor"})
    private.save_profile(profile)
    private.save_session({"session_id": "private-session", "recommendation": {
        "user_id": "private-investor", "ticker": "TCS.NS"}, "metrics": {}})
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    monkeypatch.setattr(api, "STATE_DIR", tmp_path)
    # Default startup path must be isolated, including the storage-retry path.
    with TestClient(api.create_app()) as client:
        assert client.get("/profiles/private-investor").status_code == 404
        assert client.get("/sessions/private-session").status_code == 404
        public_profile = client.get("/profiles/arjun").json()
        public_profile["name"] = "Public demo edit"
        assert client.put("/profiles/arjun", json=public_profile).status_code == 200
        client.app.state.store = None
        public_profile["name"] = "Public retry edit"
        assert client.put("/profiles/arjun", json=public_profile).status_code == 200
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before
    with TestClient(api.create_app()) as client:
        assert client.get("/profiles/arjun").json()["name"] == "Public retry edit"
    # Operator can restore the private gate and original data without a migration.
    monkeypatch.setenv("VIBEFINANCE_PUBLIC_DEMO", "0")
    with TestClient(api.create_app(original)) as client:
        assert client.get("/profiles").status_code == 401
        headers = {"Authorization": "Bearer synthetic-private-test-token"}
        assert client.get("/profiles/private-investor", headers=headers).status_code == 200
        assert client.get("/sessions/private-session", headers=headers).status_code == 200


def test_legacy_dashboard_opens_without_password_or_token_header(public_render, tmp_path, monkeypatch):
    with TestClient(api.create_app(tmp_path / "legacy.sqlite3")) as client:
        def bridge(method, url, **kwargs):
            assert "Authorization" not in kwargs.get("headers", {})
            kwargs.pop("timeout", None)
            return client.request(method, urlsplit(url).path, **kwargs)

        monkeypatch.setattr("httpx.request", bridge)
        app = AppTest.from_file("vibefinance/dashboard.py", default_timeout=30).run()
        assert not app.exception
        assert not any(field.label == "Demo access token" for field in app.text_input)
        assert any("Public hackathon demo" in caption.value for caption in app.caption)
        assert any(metric.label == "Evidence strength" for metric in app.metric)
