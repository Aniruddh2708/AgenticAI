"""Real Streamlit reruns and API routes with fixture-only account providers.

The temporary per-account SQLite stores substitute for PostgreSQL in these UI
checks. They do not establish remote Supabase sign-in or database acceptance.
JWT verification and database isolation are covered by their integration suites.
"""
from dataclasses import replace
from pathlib import Path
import time
from urllib.parse import urlsplit

import httpx
import pytest
import streamlit as st
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from vibefinance import api, auth
from vibefinance.auth import AuthenticationError, AuthSession, Principal, account_identifier
from vibefinance.profiles.store import Store


def widget(elements, label):
    return next(element for element in elements if element.label == label)


class FixtureAccounts:
    """No live secrets or external network; responses model provider outcomes."""
    def __init__(self):
        self.sessions = {}
        self.password_removed = []
        self.refreshes = []
        self.signouts = []
        self.fail_validation = False
        self.fail_signout = False
        self.fail_refresh = False
        self.refresh_as = None
        self.initial_lifetime = 300
        self.signup_session = False
        self.settings = None

    def issue(self, name, lifetime=300):
        number = len(self.sessions) + 1
        principal = Principal(account_identifier(self.settings.issuer, name), self.settings.issuer,
                              name, "supabase")
        session = AuthSession(f"fixture-{name}-access-{number}", f"fixture-{name}-refresh-{number}",
                              int(time.time()) + lifetime, principal)
        self.sessions[session.access_token] = session
        return session

    def sign_in(self, email, password):
        self.password_removed.append("account_password" not in st.session_state)
        if password != "fixture-password-long-enough":
            raise AuthenticationError("fixture private provider error")
        return self.issue(email.split("@")[0], self.initial_lifetime)

    def sign_up(self, email, password):
        self.password_removed.append("account_password" not in st.session_state)
        return self.issue(email.split("@")[0]) if self.signup_session else None

    def validate_session(self, session):
        if (self.fail_validation or not isinstance(session, AuthSession)
                or session.expires_at <= time.time()
                or session.access_token not in self.sessions):
            raise AuthenticationError("fixture private provider error")
        return session.principal

    def refresh(self, token):
        self.refreshes.append(token)
        if self.fail_refresh:
            raise AuthenticationError("fixture private refresh error")
        old = next(value for value in self.sessions.values() if value.refresh_token == token)
        return self.issue(self.refresh_as or old.principal.subject)

    def sign_out(self, token):
        self.signouts.append(token)
        if self.fail_signout:
            raise AuthenticationError("fixture private sign-out error")

    def close(self):
        pass


@pytest.fixture
def accounts_dashboard(monkeypatch, tmp_path):
    monkeypatch.setenv("VIBEFINANCE_AUTH_MODE", "supabase")
    monkeypatch.setenv("VIBEFINANCE_SUPABASE_URL", "https://abcdefghijklmnopqrst.supabase.co")
    monkeypatch.setenv("VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_fixtureonlytestkey")
    monkeypatch.setenv("VIBEFINANCE_API_TOKEN", "fixture-old-shared-demo-token")
    monkeypatch.setenv("VIBEFINANCE_EMBEDDINGS", "0")
    monkeypatch.setenv("VIBEFINANCE_FORECAST_REPORT", str(
        Path(__file__).resolve().parents[1] / "docs/assets/forecast-followup-summary.json"))
    provider = FixtureAccounts()
    provider.settings = auth.AuthSettings.from_env()
    stores, calls = {}, []

    def account_store(account):
        if account not in stores:
            store = Store(tmp_path / (account + ".sqlite3"))
            # Same profile IDs in separate stores exercise UI account changes.
            for profile in store.profiles():
                profile.name = account[:8] + " " + profile.name
                store.save_profile(profile)
            stores[account] = store
        return stores[account]

    class FixtureVerifier:
        def __init__(self, settings):
            pass

        def authenticate(self, authorization, **kwargs):
            token = authorization.removeprefix("Bearer ")
            if not authorization.startswith("Bearer ") or token not in provider.sessions:
                raise AuthenticationError("Fixture request is not authorized")
            return provider.validate_session(provider.sessions[token])

        def close(self):
            pass

    monkeypatch.setattr(auth, "SupabaseAuth", lambda settings: provider)
    monkeypatch.setattr(api, "OIDCVerifier", FixtureVerifier)
    monkeypatch.setattr(api, "initialize_production_storage", lambda: None)
    monkeypatch.setattr(api, "production_storage_health", lambda: None)
    monkeypatch.setattr(api, "create_production_store", account_store)
    st.cache_resource.clear()
    with TestClient(api.create_app()) as client:
        def request(method, url, **kwargs):
            path = urlsplit(url).path
            calls.append((method, path, kwargs.get("headers", {}).get("Authorization")))
            kwargs.pop("timeout", None)
            return client.request(method, path, **kwargs)
        monkeypatch.setattr(httpx, "request", request)
        app = AppTest.from_file("vibefinance/dashboard.py", default_timeout=60).run()
        assert not app.exception
        yield app, provider, calls, stores
    st.cache_resource.clear()


def sign_in(app, name="alice", password="fixture-password-long-enough"):
    widget(app.text_input, "Email").set_value(name + "@example.test")
    widget(app.text_input, "Password").set_value(password)
    widget(app.button, "Sign in").click().run()
    assert not app.exception


def visible_text(app):
    return "\n".join(element.value for elements in
                     (app.info, app.error, app.caption, app.markdown) for element in elements)


def seed_private_cache(app):
    app.session_state["opened_sources"] = {"old-account": {"document_text": "private fixture"}}
    app.session_state["comparison"] = ["old-account-private"]
    app.session_state["comparison_key"] = ["old-account-private"]
    app.session_state["forecast_audit"] = {"private-fixture": True}
    app.session_state["policy_replay"] = {"private-fixture": True}
    app.session_state["prior-account-form"] = "private fixture"


def assert_private_cache_cleared(app):
    state = app.session_state.filtered_state
    for key in ("opened_sources", "comparison", "comparison_key", "forecast_audit",
                "policy_replay", "prior-account-form"):
        assert key not in state


def test_shared_demo_token_does_not_bypass_individual_login(accounts_dashboard):
    app, _, calls, _ = accounts_dashboard
    assert not calls
    assert {item.label for item in app.text_input} == {"Email", "Password"}
    assert "Demo access token" not in {item.label for item in app.text_input}
    assert "personal account" in visible_text(app)


def test_sign_in_uses_personal_bearer_and_removes_password_before_provider(accounts_dashboard):
    app, provider, calls, _ = accounts_dashboard
    sign_in(app)
    assert provider.password_removed == [True]
    assert "account_password" not in app.session_state.filtered_state
    assert "fixture-password" not in visible_text(app)
    session = app.session_state["individual_session"]
    assert calls and all(header == "Bearer " + session.access_token for _, _, header in calls)
    assert "fixture-old-shared-demo-token" not in str(calls)
    assert "Compare my profiles" in {item.label for item in app.button}
    assert "Run point-in-time policy replay" not in {item.label for item in app.button}
    assert app.session_state["analysis"]["recommendation"]["user_id"] == "arjun"


def test_rejected_password_is_not_retained_or_sent_to_api(accounts_dashboard):
    app, provider, calls, _ = accounts_dashboard
    sign_in(app, password="rejected-fixture-password")
    assert provider.password_removed == [True]
    assert not calls
    assert "individual_session" not in app.session_state.filtered_state
    assert "rejected-fixture-password" not in str(app.session_state.filtered_state)
    assert "private provider error" not in visible_text(app)


def test_signup_confirmation_does_not_claim_active_account(accounts_dashboard):
    app, provider, calls, _ = accounts_dashboard
    widget(app.text_input, "Email").set_value("alice@example.test")
    widget(app.text_input, "Password").set_value("fixture-password-long-enough")
    widget(app.button, "Create free account").click().run()
    assert not app.exception
    assert provider.password_removed == [True]
    assert not calls
    assert "An active account has not been confirmed" in visible_text(app)
    assert "individual_session" not in app.session_state.filtered_state


def test_logout_clears_all_private_state_even_provider_failure(accounts_dashboard):
    app, provider, calls, _ = accounts_dashboard
    sign_in(app)
    seed_private_cache(app)
    provider.fail_signout = True
    before = len(calls)
    widget(app.button, "Sign out").click().run()
    assert not app.exception
    assert len(calls) == before
    assert provider.signouts
    assert_private_cache_cleared(app)
    assert "individual_session" not in app.session_state.filtered_state
    assert "analysis" not in app.session_state.filtered_state
    assert "Signed out of this app" in visible_text(app)
    assert "private sign-out error" not in visible_text(app)


@pytest.mark.parametrize("remaining", [20, -20])
def test_near_expiry_and_expired_stored_session_renew_once(accounts_dashboard, remaining):
    app, provider, calls, _ = accounts_dashboard
    sign_in(app)
    original = app.session_state["individual_session"]
    expired = replace(original, expires_at=int(time.time()) + remaining)
    provider.sessions[original.access_token] = expired
    app.session_state["individual_session"] = expired
    before = len(calls)
    app.run()
    assert not app.exception
    assert provider.refreshes == [original.refresh_token]
    renewed = app.session_state["individual_session"]
    assert renewed.principal.account_id == original.principal.account_id
    assert renewed.access_token != original.access_token
    assert all(header == "Bearer " + renewed.access_token for _, _, header in calls[before:])
    app.run()
    assert provider.refreshes == [original.refresh_token]


@pytest.mark.parametrize("failure", ["refresh_failure", "wrong_account", "validation_failure"])
def test_renewal_or_verification_failure_clears_private_page(accounts_dashboard, failure):
    app, provider, calls, _ = accounts_dashboard
    sign_in(app)
    seed_private_cache(app)
    original = app.session_state["individual_session"]
    if failure == "validation_failure":
        provider.fail_validation = True
    else:
        app.session_state["individual_session"] = replace(original, expires_at=int(time.time()) - 1)
        provider.fail_refresh = failure == "refresh_failure"
        provider.refresh_as = "bob" if failure == "wrong_account" else None
    before = len(calls)
    app.run()
    assert not app.exception
    assert len(calls) == before
    assert_private_cache_cleared(app)
    assert "individual_session" not in app.session_state.filtered_state
    assert "analysis" not in app.session_state.filtered_state
    assert "expired or could not be verified" in visible_text(app)


def test_account_change_replaces_analysis_and_clears_open_documents(accounts_dashboard):
    app, provider, calls, stores = accounts_dashboard
    sign_in(app)
    first = app.session_state["individual_session"]
    old_session_id = app.session_state["analysis"]["session_id"]
    seed_private_cache(app)
    second = provider.issue("bob")
    app.session_state["individual_session"] = second
    before = len(calls)
    app.run()
    assert not app.exception
    assert_private_cache_cleared(app)
    assert app.session_state["individual_account"] == second.principal.account_id
    assert app.session_state["analysis"]["session_id"] != old_session_id
    assert all(header == "Bearer " + second.access_token for _, _, header in calls[before:])
    assert len(stores) == 2
    assert len(stores[first.principal.account_id].history("arjun")) == 1
    assert len(stores[second.principal.account_id].history("arjun")) == 1


def test_fragment_audit_request_rechecks_identity(accounts_dashboard):
    app, provider, calls, _ = accounts_dashboard
    sign_in(app)
    provider.fail_validation = True
    before = len(calls)
    widget(app.button, "Load real-history forecast audit").click().run()
    assert not app.exception
    assert len(calls) == before
    assert "analysis" not in app.session_state.filtered_state
    assert "Sign in" in {item.label for item in app.button}


def test_new_account_can_create_first_profile_without_seeded_users(accounts_dashboard, tmp_path):
    app, provider, calls, stores = accounts_dashboard
    first = provider.issue("alice")
    store = Store(tmp_path / "empty-account.sqlite3")
    for profile in store.profiles():
        store.delete_profile(profile.user_id)
    stores[first.principal.account_id] = store
    sign_in(app)
    assert "analysis" not in app.session_state.filtered_state
    assert widget(app.button, "Run analysis").disabled
    widget(app.radio, "Profile operation").set_value("Create profile").run()
    widget(app.text_input, "Profile ID").set_value("my_profile")
    widget(app.text_input, "Investor name").set_value("Fixture First Investor")
    widget(app.button, "Save investor profile").click().run()
    assert not app.exception
    assert [profile.user_id for profile in store.profiles()] == ["my_profile"]
    assert app.session_state["analysis"]["recommendation"]["user_id"] == "my_profile"
    assert "Compare my profiles" in {item.label for item in app.button}
    assert any(method == "PUT" and path == "/profiles/my_profile" for method, path, _ in calls)


def test_missing_individual_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("VIBEFINANCE_AUTH_MODE", "supabase")
    monkeypatch.delenv("VIBEFINANCE_SUPABASE_URL", raising=False)
    monkeypatch.setenv("VIBEFINANCE_API_TOKEN", "fixture-shared-token-is-not-a-fallback")
    calls = []
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: calls.append(args))
    app = AppTest.from_file("vibefinance/dashboard.py").run()
    assert not app.exception
    assert not calls
    assert "Account configuration is unavailable" in visible_text(app)
    assert not app.text_input


def configure_oidc(monkeypatch, **claim_overrides):
    monkeypatch.setenv("VIBEFINANCE_AUTH_MODE", "oidc")
    monkeypatch.setenv("VIBEFINANCE_OIDC_ISSUER", "https://identity.example.test/tenant")
    monkeypatch.setenv("VIBEFINANCE_OIDC_AUDIENCE", "fixture-api")
    monkeypatch.setenv("VIBEFINANCE_OIDC_UI_CLIENT_ID", "fixture-ui")
    monkeypatch.setenv("VIBEFINANCE_INTERNAL_AUTH_KEY", "fixture-internal-key-not-live-" * 3)
    now = int(time.time())
    claims = {"is_logged_in": True, "iss": "https://identity.example.test/tenant",
              "aud": "fixture-ui", "sub": "alice", "iat": now - 100,
              "exp": now + 300, **claim_overrides}
    monkeypatch.setattr(st, "user", claims)
    return auth.AuthSettings.from_env()


def test_native_oidc_bridge_matches_decoded_api_source_path(monkeypatch):
    pytest.importorskip("jwt")
    settings = configure_oidc(monkeypatch)
    paths = []
    verifier = auth.OIDCVerifier(settings)
    try:
        def request(method, url, **kwargs):
            assert url.endswith("/sessions/fixture/sources/filing%3Aannual%3A0")
            principal = verifier.authenticate(kwargs["headers"]["Authorization"],
                method=method, path="/sessions/fixture/sources/filing:annual:0")
            paths.append(principal.subject)
            return httpx.Response(200, json={"excerpt": "fixture passage"},
                                  request=httpx.Request(method, url))
        monkeypatch.setattr(httpx, "request", request)
        app = AppTest.from_string(
            "from vibefinance.dashboard import call\n"
            "call('GET', '/sessions/fixture/sources/filing%3Aannual%3A0')\n").run()
    finally:
        verifier.close()
    assert not app.exception
    assert paths == ["alice"]


def test_native_oidc_expiry_clears_state_and_requests_logout(monkeypatch):
    configure_oidc(monkeypatch, exp=int(time.time()) - 1)
    calls, logouts = [], []
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(st, "logout", lambda: logouts.append(True))
    app = AppTest.from_file("vibefinance/dashboard.py")
    app.session_state["analysis"] = {"private": "fixture prior account"}
    app.session_state["individual_account"] = "fixture-prior-account"
    app.run()
    assert not app.exception
    assert not calls
    assert logouts == [True]
    assert "analysis" not in app.session_state.filtered_state


def test_native_oidc_login_uses_configured_provider_and_no_shared_token(monkeypatch):
    configure_oidc(monkeypatch, is_logged_in=False)
    monkeypatch.setenv("VIBEFINANCE_API_TOKEN", "fixture-shared-token-is-not-a-fallback")
    calls, logins = [], []
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(st, "login", lambda provider: logins.append(provider))
    app = AppTest.from_file("vibefinance/dashboard.py").run()
    assert not app.exception
    widget(app.button, "Sign in with your account").click().run()
    assert not app.exception
    assert not calls
    assert logins == ["oidc"]
