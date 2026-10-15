"""Identity attacks use locally generated keys and mocked HTTPS, never live accounts."""
import base64
import hashlib
import hmac
import json
import time
from dataclasses import replace

import httpx
import pytest

from vibefinance.auth import (AuthConfigurationError, AuthenticationError, AuthSettings,
    OIDCVerifier, SupabaseAuth, account_identifier, auth_mode, dashboard_authorization,
    verified_dashboard_identity)


def settings():
    return AuthSettings("oidc", "https://identity.example/tenant", "vibefinance-api",
                        "vibefinance-ui", "test-only-not-a-live-secret-" * 3)


def ui_claims(**overrides):
    now = int(time.time())
    return {"is_logged_in": True, "iss": settings().issuer, "aud": settings().ui_client_id,
            "sub": "alice", "iat": now - 10, "exp": now + 300, **overrides}


def test_settings_default_and_missing_configuration_fail_closed():
    assert AuthSettings.from_env({}).mode == "demo"
    assert "internal_key" not in repr(settings())
    for values in ({"VIBEFINANCE_AUTH_MODE": "other"}, {"VIBEFINANCE_AUTH_MODE": "oidc"}):
        with pytest.raises(AuthConfigurationError):
            AuthSettings.from_env(values)


@pytest.mark.parametrize("issuer", ["http://identity.example", "https://localhost", "https://127.0.0.1",
    "https://[::1]", "https://10.0.0.1", "https://169.254.169.254", "https://identity.local",
    "https://user:pass@identity.example", "https://identity.example?x=y", "https://identity.example#x"])
def test_invalid_issuer_configuration(issuer):
    with pytest.raises(AuthConfigurationError):
        AuthSettings.from_env({"VIBEFINANCE_AUTH_MODE": "oidc", "VIBEFINANCE_OIDC_ISSUER": issuer,
            "VIBEFINANCE_OIDC_AUDIENCE": "api", "VIBEFINANCE_OIDC_UI_CLIENT_ID": "ui",
            "VIBEFINANCE_INTERNAL_AUTH_KEY": "a" * 32})


def test_valid_config_and_distinct_api_audience():
    config = {"VIBEFINANCE_AUTH_MODE": "oidc", "VIBEFINANCE_OIDC_ISSUER": settings().issuer,
        "VIBEFINANCE_OIDC_AUDIENCE": "api", "VIBEFINANCE_OIDC_UI_CLIENT_ID": "ui",
        "VIBEFINANCE_INTERNAL_AUTH_KEY": "a" * 32}
    assert AuthSettings.from_env(config).audience == "api"
    config["VIBEFINANCE_OIDC_AUDIENCE"] = "ui"
    with pytest.raises(AuthConfigurationError):
        AuthSettings.from_env(config)


def test_stable_account_identity_is_issuer_and_subject_not_email():
    first = verified_dashboard_identity(ui_claims(email="old@example.test"), settings())
    second = verified_dashboard_identity(ui_claims(email="new@example.test"), settings())
    assert first.account_id == second.account_id
    assert first.account_id != account_identifier(settings().issuer, "bob")
    assert first.account_id != account_identifier("https://other.example/tenant", "alice")
    expected = hashlib.sha256(json.dumps([settings().issuer, "alice"], ensure_ascii=True,
                                         separators=(",", ":")).encode()).hexdigest()
    assert first.account_id == expected


@pytest.mark.parametrize("override", [{"is_logged_in": False}, {"is_logged_in": "true"},
    {"iss": "https://attacker.example"}, {"aud": "vibefinance-api"}, {"sub": ""}, {"sub": 1},
    {"iat": True}, {"iat": "123"}, {"exp": True}, {"exp": 1}, {"iat": int(time.time()) + 300},
    {"nbf": int(time.time()) + 300}, {"exp": int(time.time()) - 1}])
def test_native_user_claims_checked_every_request(override):
    with pytest.raises(AuthenticationError, match="valid individual sign-in"):
        verified_dashboard_identity(ui_claims(**override), settings())


@pytest.fixture
def identity():
    jwt = pytest.importorskip("jwt", reason="optional requirements-auth.lock is not installed")
    crypto = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.rsa")
    private = crypto.generate_private_key(public_exponent=65537, key_size=2048)
    second = crypto.generate_private_key(public_exponent=65537, key_size=2048)
    def jwk(key, kid):
        return {**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())),
                "kid": kid, "alg": "RS256", "use": "sig"}
    state = {"keys": [jwk(private, "first")], "calls": [], "failure": False,
             "metadata": {"issuer": settings().issuer, "jwks_uri": "https://identity.example/keys"}}
    def handler(request):
        state["calls"].append(str(request.url))
        if state["failure"]:
            return httpx.Response(503, text="provider secret error body")
        return httpx.Response(200, json=state["metadata"] if "openid-configuration" in str(request.url)
                              else {"keys": state["keys"]})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    ticks = [100.0]
    verifier = OIDCVerifier(settings(), client=client, monotonic=lambda: ticks[0])
    def token(overrides=None, *, key=private, kid="first", headers=None):
        now = int(time.time())
        claims = {"iss": settings().issuer, "aud": settings().audience, "sub": "alice",
                  "iat": now - 10, "exp": now + 300, **(overrides or {})}
        if headers and "b64" in headers:
            # PyJWT deliberately removes the default b64=true header on encode;
            # retain it to exercise the actual hostile wire representation.
            def encoded(value):
                return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=")
            message = encoded({"alg": "RS256", "typ": "JWT", "kid": kid, **headers}) + b"." + encoded(claims)
            from cryptography.hazmat.primitives import hashes
            signature = jwt.algorithms.RSAAlgorithm(hashes.SHA256).sign(message, key)
            return (message + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode()
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid, **(headers or {})})
    yield verifier, token, state, ticks, second, jwk, jwt
    client.close()


def authenticate(verifier, token, method="GET", path="/profiles"):
    return verifier.authenticate("Bearer " + token, method=method, path=path)


def test_real_rsa_signature_identity_and_cache(identity):
    verifier, token, state, *_ = identity
    alice = authenticate(verifier, token())
    bob = authenticate(verifier, token({"sub": "bob"}))
    assert alice.account_id != bob.account_id
    assert alice.account_id == verified_dashboard_identity(ui_claims(), settings()).account_id
    assert alice.mechanism == "oidc"
    assert len(state["calls"]) == 2
    assert all(url.startswith("https://identity.example/") for url in state["calls"])


@pytest.mark.parametrize("override", [{"iss": "https://other.example"}, {"aud": "wrong"},
    {"aud": [settings().audience]}, {"sub": ""}, {"sub": 1}, {"exp": 1}, {"exp": True},
    {"iat": True}, {"iat": "123"}, {"iat": int(time.time()) + 300},
    {"nbf": int(time.time()) + 300}, {"token_use": "id"}])
def test_reject_invalid_signed_claims(identity, override):
    verifier, token, *_ = identity
    with pytest.raises(AuthenticationError, match="valid individual sign-in"):
        authenticate(verifier, token(override))


@pytest.mark.parametrize("claim", ["iss", "sub", "aud", "iat", "exp"])
def test_require_all_critical_claims(identity, claim):
    verifier, token, _, _, _, _, jwt = identity
    raw = token()
    # Re-sign missing-claim payload with same generated fixture private key.
    claims = jwt.decode(raw, options={"verify_signature": False})
    del claims[claim]
    # token's default arguments retain the fixture's private key.
    private = token.__kwdefaults__["key"]
    missing = jwt.encode(claims, private, algorithm="RS256", headers={"kid": "first"})
    with pytest.raises(AuthenticationError):
        authenticate(verifier, missing)


@pytest.mark.parametrize("header", [{"jku": "https://attacker.example/keys"}, {"jwk": {}},
    {"x5u": "https://attacker.example/cert"}, {"x5c": []}, {"crit": []},
    {"b64": True}, {"typ": "unsupported"}, {"kid": ""}])
def test_untrusted_header_never_influences_network(identity, header):
    verifier, token, state, *_ = identity
    with pytest.raises(AuthenticationError):
        authenticate(verifier, token(headers=header))
    assert not state["calls"]


def test_none_hs256_signature_forgery_and_unsigned_identity_rejected(identity):
    verifier, token, state, _, second, _, jwt = identity
    now = int(time.time())
    claims = {"iss": settings().issuer, "aud": settings().audience,
              "sub": "alice", "iat": now, "exp": now + 60}
    for raw in (jwt.encode(claims, "", algorithm="none", headers={"kid": "first"}),
                jwt.encode(claims, "attacker" * 8, algorithm="HS256", headers={"kid": "first"}),
                token(key=second), "not-a-token", ""):
        with pytest.raises(AuthenticationError):
            authenticate(verifier, raw)
    assert all("attacker" not in url for url in state["calls"])


@pytest.mark.parametrize("metadata", [
    {"issuer": "https://evil.example", "jwks_uri": "https://identity.example/keys"},
    {"issuer": settings().issuer, "jwks_uri": "http://identity.example/keys"},
    {"issuer": settings().issuer, "jwks_uri": "https://attacker.example/keys"},
    {"issuer": settings().issuer, "jwks_uri": "https://127.0.0.1/keys"}])
def test_metadata_cannot_redirect_key_fetch(identity, metadata):
    verifier, token, state, *_ = identity
    state["metadata"] = metadata
    with pytest.raises(AuthenticationError):
        authenticate(verifier, token())
    assert len(state["calls"]) == 1


def test_key_rotation_refresh_and_outage_fail_closed_without_storm(identity):
    verifier, token, state, ticks, second, jwk, _ = identity
    authenticate(verifier, token())
    state["keys"] = [jwk(second, "second")]
    with pytest.raises(AuthenticationError):
        authenticate(verifier, token(key=second, kid="second"))
    assert len(state["calls"]) == 2  # Rate-limited immediately after initial fetch.
    ticks[0] += 16
    authenticate(verifier, token(key=second, kid="second"))
    assert len(state["calls"]) == 4
    state["failure"] = True
    ticks[0] += 301
    with pytest.raises(AuthenticationError) as error:
        authenticate(verifier, token(key=second, kid="second"))
    assert str(error.value) == "A valid individual sign-in is required."
    calls = len(state["calls"])
    with pytest.raises(AuthenticationError):
        authenticate(verifier, token(key=second, kid="second"))
    assert len(state["calls"]) == calls


def test_oversized_metadata_is_rejected(identity):
    verifier, token, state, *_ = identity
    state["metadata"]["padding"] = "x" * 131072
    with pytest.raises(AuthenticationError):
        authenticate(verifier, token())
    assert len(state["calls"]) == 1


@pytest.mark.parametrize("key_change", [{"kid": ""}, {"d": "private"}, {"key_ops": ["sign"]}])
def test_unsafe_key_metadata_rejected(identity, key_change):
    verifier, token, state, *_ = identity
    state["keys"][0].update(key_change)
    with pytest.raises(AuthenticationError):
        authenticate(verifier, token())


def test_internal_bridge_is_short_lived_request_bound_and_separate_from_jwt(identity):
    verifier, _, state, *_ = identity
    header = dashboard_authorization(ui_claims(), settings(), method="PUT", path="/profiles/alice")
    principal = verifier.authenticate(header, method="PUT", path="/profiles/alice")
    assert principal.account_id == account_identifier(settings().issuer, "alice")
    assert principal.mechanism == "dashboard"
    assert not state["calls"]
    for method, path in (("GET", "/profiles/alice"), ("PUT", "/profiles/bob")):
        with pytest.raises(AuthenticationError):
            verifier.authenticate(header, method=method, path=path)
    with pytest.raises(AuthenticationError):
        verifier.authenticate(header.replace("VibeInternal ", "Bearer "), method="PUT", path="/profiles/alice")
    with pytest.raises(AuthenticationError):
        verifier.authenticate(header[:-1] + ("a" if header[-1] != "a" else "b"), method="PUT", path="/profiles/alice")


def test_expired_internal_and_wrong_server_key_rejected(identity):
    verifier, *_ = identity
    now = int(time.time())
    header = dashboard_authorization(ui_claims(), settings(), method="GET", path="/profiles", now=now)
    verifier._clock = lambda: now + 61
    with pytest.raises(AuthenticationError):
        verifier.authenticate(header, method="GET", path="/profiles")
    verifier._clock = time.time
    wrong = dashboard_authorization(ui_claims(), replace(settings(), internal_key="other" * 12), method="GET", path="/profiles")
    with pytest.raises(AuthenticationError):
        verifier.authenticate(wrong, method="GET", path="/profiles")


def test_native_authlib_integration_imports_when_optional_installed():
    pytest.importorskip("authlib")
    from streamlit.web.server.oidc_mixin import TornadoOAuth
    from authlib.jose import jwt
    from streamlit.auth_util import is_authlib_installed
    assert TornadoOAuth and jwt and is_authlib_installed()


def supabase_settings():
    return AuthSettings.from_env({"VIBEFINANCE_AUTH_MODE": "supabase",
        "VIBEFINANCE_SUPABASE_URL": "https://abcdefghijklmnopqrst.supabase.co",
        "VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY": "sb_publishable_public-test-value-only"})


def test_supabase_settings_derive_fixed_project_issuer_and_public_key_only():
    config = supabase_settings()
    assert config.issuer == "https://abcdefghijklmnopqrst.supabase.co/auth/v1"
    assert config.audience == "authenticated"
    assert "public-test-value" not in repr(config)
    for key in ("sb_secret_this-is-forbidden", "service_role", "eyJhbGciOiJIUzI1NiJ9.payload.signature", ""):
        with pytest.raises(AuthConfigurationError):
            AuthSettings.from_env({"VIBEFINANCE_AUTH_MODE": "supabase",
                "VIBEFINANCE_SUPABASE_URL": config.supabase_url,
                "VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY": key})


@pytest.mark.parametrize("url", ["http://abcdefghijklmnopqrst.supabase.co", "https://localhost",
    "https://abcdefghijklmnopqrst.supabase.co.attacker.example", "https://abcdefghijklmnopqrst.supabase.co/path",
    "https://attacker.example", "https://user@abcdefghijklmnopqrst.supabase.co"])
def test_supabase_project_url_cannot_be_redirected(url):
    with pytest.raises(AuthConfigurationError):
        AuthSettings.from_env({"VIBEFINANCE_AUTH_MODE": "supabase",
            "VIBEFINANCE_SUPABASE_URL": url,
            "VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY": supabase_settings().publishable_key})


@pytest.fixture
def supabase_identity():
    jwt = pytest.importorskip("jwt")
    ec = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ec")
    config = supabase_settings()
    private = ec.generate_private_key(ec.SECP256R1())
    key = {**json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key())),
           "kid": "supabase-signing-key", "alg": "ES256", "use": "sig", "key_ops": ["verify"]}
    def token(**overrides):
        now = int(time.time())
        claims = {"iss": config.issuer, "sub": "alice", "aud": "authenticated",
            "role": "authenticated", "iat": now - 10, "exp": now + 300,
            "is_anonymous": False, **overrides}
        return jwt.encode(claims, private, algorithm="ES256", headers={"kid": key["kid"]})
    state = {"calls": [], "keys": [key], "response": None, "error": False}
    def handler(request):
        state["calls"].append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"keys": state["keys"]})
        if state["error"]:
            return httpx.Response(400, json={"error_description": "private-provider-message"})
        return httpx.Response(200, json=state["response"] if state["response"] is not None else
                              {"access_token": token(), "refresh_token": "private-refresh-token", "expires_at": 0})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    verifier = OIDCVerifier(config, client=client)
    auth = SupabaseAuth(config, client=client, verifier=verifier)
    yield config, auth, verifier, token, state, jwt
    client.close()


def test_supabase_p256_access_signature_and_fixed_jwks_endpoint(supabase_identity):
    config, _, verifier, token, state, _ = supabase_identity
    principal = authenticate(verifier, token())
    assert principal.account_id == account_identifier(config.issuer, "alice")
    assert principal.mechanism == "supabase"
    assert len(state["calls"]) == 1
    assert str(state["calls"][0].url) == config.issuer + "/.well-known/jwks.json"


def test_supabase_rsa_access_signature_uses_published_algorithm(supabase_identity):
    config, _, verifier, _, state, jwt = supabase_identity
    from cryptography.hazmat.primitives.asymmetric import rsa
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    state["keys"] = [{**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key())),
                      "alg": "RS256", "kid": "rsa-project-key", "use": "sig"}]
    now = int(time.time())
    raw = jwt.encode({"iss": config.issuer, "sub": "alice", "aud": "authenticated",
                      "role": "authenticated", "iat": now - 10, "exp": now + 60},
                     private, algorithm="RS256", headers={"kid": "rsa-project-key"})
    assert authenticate(verifier, raw).account_id == account_identifier(config.issuer, "alice")


def test_auth_and_production_store_use_identical_account_namespace():
    from vibefinance.profiles.production_store import account_identifier as storage_identifier
    assert account_identifier("https://identity.example/tenant", "account-\u20b9") == storage_identifier(
        "https://identity.example/tenant", "account-\u20b9")


@pytest.mark.parametrize("claims", [{"role": "service_role"}, {"role": "anon"}, {"role": None},
    {"is_anonymous": True}, {"is_anonymous": "true"}, {"aud": "another-project"},
    {"iss": "https://otherprojectabcdefgh.supabase.co/auth/v1"}, {"exp": 1}])
def test_supabase_rejects_nonuser_or_cross_project_token(supabase_identity, claims):
    _, _, verifier, token, _, _ = supabase_identity
    with pytest.raises(AuthenticationError):
        authenticate(verifier, token(**claims))


def test_supabase_does_not_accept_legacy_hmac_or_internal_assertions(supabase_identity):
    _, _, verifier, token, state, jwt = supabase_identity
    now = int(time.time())
    raw = jwt.encode({"sub": "alice", "iat": now, "exp": now + 60}, "legacy-key" * 8,
                     algorithm="HS256", headers={"kid": "supabase-signing-key"})
    with pytest.raises(AuthenticationError):
        authenticate(verifier, raw)
    with pytest.raises(AuthenticationError):
        verifier.authenticate(dashboard_authorization(ui_claims(), settings(), method="GET", path="/profiles"),
                              method="GET", path="/profiles")
    assert not state["calls"]


def test_supabase_key_algorithm_is_pinned(supabase_identity):
    _, _, verifier, token, state, _ = supabase_identity
    state["keys"][0]["alg"] = "RS256"  # EC key cannot masquerade as RSA.
    with pytest.raises(AuthenticationError):
        authenticate(verifier, token())


def test_supabase_password_login_uses_public_key_and_verified_expiry(supabase_identity):
    config, auth, _, _, state, _ = supabase_identity
    session = auth.sign_in("alice@example.test", "test-password-only")
    request = state["calls"][0]
    assert str(request.url) == config.issuer + "/token?grant_type=password"
    assert request.headers["apikey"] == config.publishable_key
    assert "authorization" not in request.headers
    assert json.loads(request.content) == {"email": "alice@example.test", "password": "test-password-only"}
    assert session.expires_at > time.time()
    assert session.principal.account_id == account_identifier(config.issuer, "alice")
    assert "private-refresh-token" not in repr(session)
    assert session.access_token not in repr(session)
    assert auth.validate_session(session).account_id == session.principal.account_id
    assert not hasattr(auth, "password")


def test_supabase_refresh_rotation_and_local_signout(supabase_identity):
    config, auth, _, token, state, _ = supabase_identity
    state["response"] = {"access_token": token(), "refresh_token": "rotated-private-token"}
    session = auth.refresh("old-private-token")
    request = state["calls"][0]
    assert str(request.url) == config.issuer + "/token?grant_type=refresh_token"
    assert json.loads(request.content) == {"refresh_token": "old-private-token"}
    assert session.refresh_token == "rotated-private-token"
    auth.sign_out(session.access_token)
    logout = state["calls"][-1]
    assert str(logout.url) == config.issuer + "/logout?scope=local"
    assert logout.headers["authorization"] == "Bearer " + session.access_token


def test_supabase_signup_confirmation_and_provider_errors_are_honest(supabase_identity):
    _, auth, _, _, state, _ = supabase_identity
    state["response"] = {"user": {"id": "unactivated"}}
    assert auth.sign_up("alice@example.test", "long-test-password") is None
    state["error"] = True
    with pytest.raises(AuthenticationError) as error:
        auth.sign_in("alice@example.test", "wrong-test-password")
    assert "private-provider-message" not in str(error.value)
    assert "wrong-test-password" not in str(error.value)
    with pytest.raises(AuthenticationError):
        auth.sign_up("alice@example.test", "short")


def test_supabase_forged_rest_session_and_tampered_owner_rejected(supabase_identity):
    _, auth, _, token, state, _ = supabase_identity
    state["response"] = {"access_token": "forged-token", "refresh_token": "private"}
    with pytest.raises(AuthenticationError):
        auth.sign_in("alice@example.test", "long-test-password")
    state["response"] = {"access_token": token(), "refresh_token": "private"}
    session = auth.sign_in("alice@example.test", "long-test-password")
    mismatched = replace(session, principal=replace(session.principal, account_id="b" * 64))
    with pytest.raises(AuthenticationError):
        auth.validate_session(mismatched)
    with pytest.raises(AuthenticationError):
        auth.validate_session(replace(session, expires_at=1))
