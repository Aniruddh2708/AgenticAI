"""Opt-in individual identity; no trust in email, user IDs or unverified JWT claims.

Demo mode deliberately keeps the existing shared-demo boundary. OIDC mode uses
RS256 access tokens for API clients, or a separate short-lived assertion issued
by the trusted Streamlit server after its native OIDC login.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx


class AuthConfigurationError(ValueError):
    """Non-secret, operator-actionable configuration failure."""


class AuthenticationError(ValueError):
    """Public, deliberately generic authentication failure."""


def auth_mode(environ=None):
    value = (os.environ if environ is None else environ).get("VIBEFINANCE_AUTH_MODE", "demo")
    if value not in {"demo", "oidc", "supabase"}:
        raise AuthConfigurationError("VIBEFINANCE_AUTH_MODE must be demo, oidc or supabase.")
    return value


def _https_url(value):
    """Only administrator-configured remote HTTPS endpoints; never token URLs."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise ValueError("Invalid HTTPS endpoint")
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.fragment or parts.query
            or parts.hostname.lower() in {"localhost", "localhost.localdomain"}
            or parts.hostname.lower().endswith((".localhost", ".local"))
            or any(character.isspace() for character in value)):
        raise ValueError("Invalid HTTPS endpoint")
    try:
        if not ipaddress.ip_address(parts.hostname).is_global:
            raise ValueError("Non-public HTTPS endpoint")
    except ValueError as exc:
        if str(exc) == "Non-public HTTPS endpoint":
            raise
    # Accessing port also validates its syntax and range.
    return (parts.hostname.lower(), parts.port or 443)


@dataclass(frozen=True)
class AuthSettings:
    mode: str = "demo"
    issuer: str = ""
    audience: str = ""
    ui_client_id: str = ""
    internal_key: str = field(default="", repr=False)
    supabase_url: str = ""
    publishable_key: str = field(default="", repr=False)

    @classmethod
    def from_env(cls, environ=None):
        values = os.environ if environ is None else environ
        mode = auth_mode(values)
        if mode == "demo":
            return cls()
        if mode == "supabase":
            url = values.get("VIBEFINANCE_SUPABASE_URL", "").rstrip("/")
            key = values.get("VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY", "")
            if (not re.fullmatch(r"https://[a-z0-9]{20}\.supabase\.co", url)
                    or not re.fullmatch(r"sb_publishable_[A-Za-z0-9_-]{16,256}", key)):
                raise AuthConfigurationError(
                    "Supabase mode requires its HTTPS project URL and a new sb_publishable_ public key. "
                    "Secret, service-role and legacy JWT API keys are not accepted."
                )
            return cls(mode=mode, issuer=url + "/auth/v1", audience="authenticated",
                       supabase_url=url, publishable_key=key)
        issuer = values.get("VIBEFINANCE_OIDC_ISSUER", "")
        audience = values.get("VIBEFINANCE_OIDC_AUDIENCE", "")
        ui_client_id = values.get("VIBEFINANCE_OIDC_UI_CLIENT_ID", "")
        internal_key = values.get("VIBEFINANCE_INTERNAL_AUTH_KEY", "")
        try:
            _https_url(issuer)
            if (not audience.strip() or not ui_client_id.strip() or audience == ui_client_id
                    or len(internal_key.encode("utf-8")) < 32):
                raise ValueError("Incomplete identity configuration")
        except (ValueError, TypeError):
            raise AuthConfigurationError(
                "OIDC mode requires a remote HTTPS issuer, distinct API audience and UI client ID, "
                "and a server-only internal key of at least 32 bytes."
            ) from None
        return cls(mode, issuer, audience, ui_client_id, internal_key)


@dataclass(frozen=True)
class Principal:
    account_id: str
    issuer: str
    subject: str
    mechanism: str


def account_identifier(issuer, subject):
    """Stable across email/name changes; issuer namespaces provider subjects."""
    return hashlib.sha256(json.dumps([issuer, subject], ensure_ascii=True,
                                    separators=(",", ":")).encode()).hexdigest()


def _principal(issuer, subject, mechanism):
    if not isinstance(subject, str) or not subject or len(subject) > 512:
        raise AuthenticationError("A valid individual sign-in is required.")
    return Principal(account_identifier(issuer, subject), issuer, subject, mechanism)


def _times(claims, now, leeway=0):
    for name in ("iat", "exp"):
        if type(claims.get(name)) is not int:
            raise ValueError("Missing numeric time")
    if (claims["iat"] < 0 or claims["exp"] <= claims["iat"]
            or claims["iat"] > now + leeway or claims["exp"] <= now - leeway):
        raise ValueError("Invalid token lifetime")
    if "nbf" in claims and (type(claims["nbf"]) is not int
                            or claims["nbf"] > now + leeway
                            or claims["nbf"] >= claims["exp"]):
        raise ValueError("Invalid token start")


def verified_dashboard_identity(claims: Mapping, settings: AuthSettings, *, now=None):
    """Use ONLY immutable st.user from native st.login, never request JSON/headers.

    This is not a JWT verifier. Streamlit/Authlib performs signature, state and
    nonce verification at login. Its cookie can outlive the identity token, so we
    explicitly enforce the original identity-token lifetime on every request.
    """
    try:
        if (settings.mode != "oidc" or claims.get("is_logged_in") is not True
                or claims.get("iss") != settings.issuer
                or claims.get("aud") != settings.ui_client_id):
            raise ValueError("Wrong identity context")
        _times(claims, time.time() if now is None else now)
        return _principal(settings.issuer, claims.get("sub"), "dashboard")
    except (ValueError, TypeError, AttributeError):
        raise AuthenticationError("A valid individual sign-in is required.") from None


def _request_context(method, path):
    if (not isinstance(method, str) or not re.fullmatch(r"[A-Z]{3,12}", method)
            or not isinstance(path, str) or not path.startswith("/")
            or "?" in path or "#" in path or len(path) > 4096):
        raise ValueError("Invalid request context")


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Invalid assertion encoding")
    decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if _b64(decoded) != value:
        raise ValueError("Non-canonical assertion encoding")
    return decoded


def dashboard_authorization(claims, settings, *, method, path, now=None):
    """Server-to-server header; never expose it in UI, browser storage or logs."""
    now = int(time.time() if now is None else now)
    principal = verified_dashboard_identity(claims, settings, now=now)
    _request_context(method, path)
    if len(settings.internal_key.encode("utf-8")) < 32:
        raise AuthConfigurationError("The server-only internal authentication key is missing.")
    payload = {"iss": "vibefinance-dashboard", "aud": "vibefinance-api",
               "provider_issuer": principal.issuer, "sub": principal.subject,
               "iat": now, "nbf": now, "exp": min(now + 60, claims["exp"]),
               "method": method, "path": path}
    encoded = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    message = "v1." + encoded
    signature = hmac.new(settings.internal_key.encode(), message.encode(), hashlib.sha256).digest()
    return "VibeInternal " + message + "." + _b64(signature)


class OIDCVerifier:
    """Bounded HTTPS discovery/JWKS, strict RS256, fail-closed key rotation.

    Metadata and keys expire after five minutes. An unknown kid can trigger one
    refresh per 15 seconds across all tokens, limiting attacker-induced traffic.
    Expired cache is never accepted after a failed refresh. Requests use normal
    configured proxy and CA verification, with no redirects or token-supplied URL.
    """
    def __init__(self, settings, *, client=None, clock=time.time, monotonic=time.monotonic):
        if settings.mode not in {"oidc", "supabase"}:
            raise AuthConfigurationError("The identity verifier requires an individual-account mode.")
        try:
            _https_url(settings.issuer)
            if not settings.audience:
                raise ValueError("Missing audience")
            import jwt
            from jwt.algorithms import ECAlgorithm, RSAAlgorithm
        except (ValueError, ImportError):
            raise AuthConfigurationError(
                "OIDC configuration or optional identity dependencies are unavailable. "
                "Install requirements-auth.lock and check the issuer and audience."
            ) from None
        self.settings, self._jwt, self._rsa = settings, jwt, RSAAlgorithm
        self._ec = ECAlgorithm
        self._clock, self._monotonic = clock, monotonic
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=httpx.Timeout(5, connect=3),
                                             follow_redirects=False)
        self._lock = threading.Lock()
        self._keys = {}
        self._expires = 0.0
        self._last_refresh = float("-inf")

    def close(self):
        if self._owns_client:
            self._client.close()

    def _json(self, url, maximum):
        started = time.monotonic()
        with self._client.stream("GET", url, headers={"Accept": "application/json"},
                                 timeout=httpx.Timeout(5, connect=3), follow_redirects=False) as response:
            response.raise_for_status()
            data = bytearray()
            for block in response.iter_bytes(chunk_size=16384):
                data.extend(block)
                if len(data) > maximum or time.monotonic() - started > 10:
                    raise ValueError("Identity metadata too large")
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ValueError("Invalid identity metadata")
            return result

    def _refresh(self):
        self._last_refresh = self._monotonic()
        if self.settings.mode == "supabase":
            url = self.settings.issuer + "/.well-known/jwks.json"
        else:
            metadata = self._json(self.settings.issuer.rstrip("/") + "/.well-known/openid-configuration", 131072)
            if metadata.get("issuer") != self.settings.issuer:
                raise ValueError("Unexpected discovery issuer")
            url = metadata.get("jwks_uri")
        if _https_url(url) != _https_url(self.settings.issuer):
            raise ValueError("JWKS must use the configured issuer origin")
        document = self._json(url, 524288)
        keys = document.get("keys")
        if not isinstance(keys, list) or not 1 <= len(keys) <= 32:
            raise ValueError("Invalid JWKS")
        parsed = {}
        for key in keys:
            if not isinstance(key, dict):
                raise ValueError("Invalid signing key")
            # Supabase defaults to P-256 asymmetric signing; generic OIDC stays RS256.
            if key.get("use", "sig") != "sig":
                continue
            algorithm = key.get("alg", "RS256" if self.settings.mode == "oidc" else None)
            if algorithm not in ({"RS256", "ES256"} if self.settings.mode == "supabase" else {"RS256"}):
                continue
            if ((algorithm == "RS256" and key.get("kty") != "RSA")
                    or (algorithm == "ES256" and (key.get("kty") != "EC" or key.get("crv") != "P-256"))):
                continue
            kid = key.get("kid")
            if (not isinstance(kid, str) or not kid or len(kid) > 256 or kid in parsed
                    or any(name in key for name in ("d", "p", "q", "dp", "dq", "qi"))
                    or ("key_ops" in key and key["key_ops"] != ["verify"])):
                raise ValueError("Invalid signing key metadata")
            public = (self._rsa if algorithm == "RS256" else self._ec).from_jwk(key)
            if algorithm == "RS256" and not 2048 <= public.key_size <= 8192:
                raise ValueError("Unsupported signing key size")
            parsed[kid] = (public, algorithm)
        if not parsed:
            raise ValueError("No supported signing keys")
        self._keys = parsed
        self._expires = self._monotonic() + 300

    def _key(self, kid):
        with self._lock:
            now = self._monotonic()
            refreshed = False
            if now >= self._expires:
                # Also rate-limit repeated failures during an identity outage.
                if now - self._last_refresh < 15:
                    raise ValueError("Identity refresh unavailable")
                self._refresh()
                refreshed = True
            if kid not in self._keys and not refreshed and now - self._last_refresh >= 15:
                self._refresh()
            if kid not in self._keys:
                raise ValueError("Unknown signing key")
            return self._keys[kid]

    def _internal(self, value, method, path):
        if len(self.settings.internal_key.encode()) < 32:
            raise ValueError("Internal authentication disabled")
        version, encoded, signature = value.split(".")
        if version != "v1":
            raise ValueError("Unknown assertion version")
        expected = hmac.new(self.settings.internal_key.encode(),
                            (version + "." + encoded).encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(signature), expected):
            raise ValueError("Bad assertion signature")
        claims = json.loads(_unb64(encoded))
        if not isinstance(claims, dict):
            raise ValueError("Invalid assertion")
        _request_context(method, path)
        _times(claims, self._clock())
        if (claims.get("iss") != "vibefinance-dashboard" or claims.get("aud") != "vibefinance-api"
                or claims.get("provider_issuer") != self.settings.issuer
                or claims.get("method") != method or claims.get("path") != path
                or type(claims.get("nbf")) is not int or claims["nbf"] != claims["iat"]
                or claims["exp"] - claims["iat"] > 60):
            raise ValueError("Wrong assertion context")
        return _principal(self.settings.issuer, claims.get("sub"), "dashboard")

    def authenticate(self, authorization, *, method, path):
        try:
            if not isinstance(authorization, str) or len(authorization) > 16384:
                raise ValueError("Invalid authorization")
            scheme, token = authorization.split(" ", 1)
            if scheme == "VibeInternal":
                if self.settings.mode != "oidc":
                    raise ValueError("Internal bridge is not used for Supabase accounts")
                return self._internal(token, method, path)
            if scheme.lower() != "bearer" or not token or len(token.split(".")[0]) > 2048:
                raise ValueError("Invalid bearer token")
            header = self._jwt.get_unverified_header(token)
            allowed = {"RS256", "ES256"} if self.settings.mode == "supabase" else {"RS256"}
            if (header.get("alg") not in allowed or header.get("typ", "JWT") not in {"JWT", "at+jwt"}
                    or any(name in header for name in ("jku", "jwk", "x5u", "x5c", "crit", "b64"))
                    or not isinstance(header.get("kid"), str)
                    or not 1 <= len(header["kid"]) <= 256):
                raise ValueError("Invalid bearer header")
            key, algorithm = self._key(header["kid"])
            if header["alg"] != algorithm:
                raise ValueError("Signing algorithm does not match the configured key")
            claims = self._jwt.decode(token, key, algorithms=[algorithm],
                                      issuer=self.settings.issuer, audience=self.settings.audience,
                                      leeway=30, options={"require": ["iss", "sub", "aud", "iat", "exp"],
                                                          "strict_aud": True})
            _times(claims, self._clock(), leeway=30)
            # An explicit provider token-use claim must identify an access token.
            if "token_use" in claims and claims["token_use"] != "access":
                raise ValueError("An access token is required")
            if self.settings.mode == "supabase" and (claims.get("role") != "authenticated"
                                                       or claims.get("is_anonymous", False) is not False):
                raise ValueError("A non-anonymous user access token is required")
            return _principal(self.settings.issuer, claims.get("sub"), self.settings.mode)
        except Exception:
            # Do not echo token, provider body, URLs, subjects or exception text.
            raise AuthenticationError("A valid individual sign-in is required.") from None


@dataclass(frozen=True)
class AuthSession:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: int
    principal: Principal


class SupabaseAuth:
    """Public-key Auth REST client; passwords are used once and never retained.

    The caller keeps access/refresh credentials only in its private server-side
    session, clears password widgets immediately, and refreshes at most once per
    attempted renewal. Service-role/secret keys are deliberately unsupported.
    """
    def __init__(self, settings, *, client=None, verifier=None):
        if settings.mode != "supabase" or not settings.publishable_key.startswith("sb_publishable_"):
            raise AuthConfigurationError("Supabase account configuration is unavailable.")
        self.settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=httpx.Timeout(10, connect=3), follow_redirects=False)
        self._owns_verifier = verifier is None
        self._verifier = verifier or OIDCVerifier(settings)

    def close(self):
        if self._owns_client:
            self._client.close()
        if self._owns_verifier:
            self._verifier.close()

    def _request(self, path, data=None, access_token=None):
        headers = {"apikey": self.settings.publishable_key, "Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = "Bearer " + access_token
        try:
            with self._client.stream("POST", self.settings.supabase_url + "/auth/v1/" + path,
                                     json=data, headers=headers, timeout=httpx.Timeout(10, connect=3),
                                     follow_redirects=False) as response:
                response.raise_for_status()
                data = bytearray()
                started = time.monotonic()
                for block in response.iter_bytes(chunk_size=16384):
                    data.extend(block)
                    if len(data) > 131072 or time.monotonic() - started > 15:
                        raise ValueError("Auth response exceeded limits")
                result = json.loads(data) if data else {}
                if not isinstance(result, dict):
                    raise ValueError("Invalid Auth response")
                return result
        except Exception:
            raise AuthenticationError("Account operation could not be completed. Check the credentials or confirmation email and retry.") from None

    def _session(self, response):
        try:
            access, refresh = response["access_token"], response["refresh_token"]
            if (not isinstance(access, str) or not access or not isinstance(refresh, str)
                    or not refresh or len(refresh) > 16384):
                raise ValueError("Invalid credentials")
            principal = self._verifier.authenticate("Bearer " + access, method="GET", path="/profiles")
            # Verified decode with the same pinned key, never trust the REST body's expiry.
            header = self._verifier._jwt.get_unverified_header(access)
            key, algorithm = self._verifier._key(header["kid"])
            claims = self._verifier._jwt.decode(access, key, algorithms=[algorithm],
                issuer=self.settings.issuer, audience=self.settings.audience,
                options={"require": ["exp", "iat", "sub", "iss", "aud"], "strict_aud": True})
            return AuthSession(access, refresh, claims["exp"], principal)
        except Exception:
            raise AuthenticationError("A valid individual sign-in is required.") from None

    def sign_in(self, email, password):
        if not isinstance(email, str) or not isinstance(password, str) or not email or not password:
            raise AuthenticationError("Email and password are required.")
        return self._session(self._request("token?grant_type=password", {"email": email, "password": password}))

    def validate_session(self, session):
        if not isinstance(session, AuthSession) or session.expires_at <= time.time():
            raise AuthenticationError("Sign in again to renew your session.")
        principal = self._verifier.authenticate("Bearer " + session.access_token,
                                              method="GET", path="/profiles")
        if principal.account_id != session.principal.account_id:
            raise AuthenticationError("A valid individual sign-in is required.")
        return principal

    def refresh(self, refresh_token):
        if not isinstance(refresh_token, str) or not refresh_token or len(refresh_token) > 16384:
            raise AuthenticationError("Sign in again to renew your session.")
        return self._session(self._request("token?grant_type=refresh_token", {"refresh_token": refresh_token}))

    def sign_up(self, email, password):
        if not isinstance(email, str) or not isinstance(password, str) or not email or len(password) < 12:
            raise AuthenticationError("A valid email and a password of at least 12 characters are required.")
        response = self._request("signup", {"email": email, "password": password})
        # With confirmation enabled no session is returned; don't claim the
        # account was activated or reveal whether an existing address was used.
        return self._session(response) if response.get("access_token") else None

    def sign_out(self, access_token):
        self._request("logout?scope=local", access_token=access_token)
