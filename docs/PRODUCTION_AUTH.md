# Individual accounts with managed authentication

The shared Render demo token is a shared access gate. Individual accounts are an
opt-in deployment mode backed by an external identity provider. The code
does not provision a provider tenant, client registration, password database or
subscription. A production release still needs those real resources and a
two-account hosted acceptance test. No live individual account is claimed here.

## Zero-cost candidate: Supabase email/password accounts

The default production candidate uses an operator-created **Supabase free
project**, with no paid Render database, persistent disk or identity-provider
subscription. The repository does not create accounts or enable billing. Free
quotas, inactivity pauses, email delivery limits and provider terms still need
review; there is no promise of unlimited or always-available production service.

Configure these names securely in the host settings:

| Variable | Meaning |
| --- | --- |
| `VIBEFINANCE_AUTH_MODE` | `supabase` for managed individual accounts. |
| `VIBEFINANCE_SUPABASE_URL` | Exact project origin `https://<20-character project ref>.supabase.co`. Custom domains and arbitrary Auth endpoints are not enabled. |
| `VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY` | New `sb_publishable_...` public API key. Secret/service-role/admin keys and legacy JWT API keys are deliberately rejected. |
| `VIBEFINANCE_DATABASE_URL` | Private verified-TLS PostgreSQL URL; see [deployment](PRODUCTION_DEPLOYMENT.md). |

Enable email/password authentication and retain email confirmation in Supabase.
Use an asymmetric signing key: ES256 with P-256 or RS256 with an RSA key of at
least 2048 bits. Legacy shared-HS256 project signing is unsupported; migrate it
in the provider before enabling this mode. The configured project supplies the
fixed issuer `<project origin>/auth/v1` and audience `authenticated`. Keys are
fetched only from `<issuer>/.well-known/jwks.json`; Supabase is not treated as a
native OpenID Connect authorization server and no OIDC discovery is attempted.
Each JWT header algorithm must match its published JWK's explicit algorithm.
Service-role, `anon`, and anonymous-user tokens are rejected even if signed.

The server calls Supabase Auth's password/token, sign-up, refresh and local
logout endpoints with the public publishable key. Passwords are used once and
must be cleared from UI widgets immediately; they are not retained in the Auth
client. Access and rotating refresh tokens belong only in the current user's
private Streamlit server session, never browser storage, URLs, tracked files,
shared caches or logs. JWT signature, issuer, audience, subject and lifetime are
checked before accepting a returned session. The REST response's unverified
expiry and user identity do not determine ownership. The original verified JWT
expiry is checked on each protected interaction; renewal is bounded to a single
refresh attempt and an account mismatch must end the session.

If sign-up returns no access token, the UI must say that email confirmation or
existing-account sign-in may be required; it must not claim the account is
activated. Live confirmation delivery, password reset, abuse/rate limits and
account recovery still require provider acceptance. This first application UI
supports sign-up/sign-in/refresh/logout; it does not implement a password-reset
email/callback workflow. Use a separately reviewed provider recovery process
before inviting users who require self-service recovery.

Logout clears this application's private session even if the provider is
unavailable. Supabase revokes the local refresh session when its logout request
succeeds; already issued access JWTs remain valid until expiration because the
API uses offline signature verification, not a per-request revocation lookup.
Choose a short provider access-token lifetime and never claim immediate global
access-token revocation. This mode needs neither a private demo password nor an
OIDC client secret, native Streamlit cookie secret or internal assertion key.

## Installation and optional native OIDC configuration

Keep the existing offline application lock unchanged; install the additional
hashed identity lock alongside it:

```bash
python -m pip install --require-hashes -r requirements.lock -r requirements-auth.lock
```

The optional lock pins PyJWT, cryptography, Authlib and their dependencies.
Streamlit remains at the application's existing 1.45.1. Its native OIDC integration
imports successfully with this lock; local generated-key and mocked-HTTPS tests
exercise verification without a live provider account.

Configure values securely in the hosting service, never in chat or Git:

| Variable | Meaning |
| --- | --- |
| `VIBEFINANCE_AUTH_MODE` | `demo` by default; `oidc` is an alternative for an existing compatible managed provider. |
| `VIBEFINANCE_OIDC_ISSUER` | Exact issuer string from the provider, including any tenant path and significant trailing slash; remote HTTPS only. |
| `VIBEFINANCE_OIDC_AUDIENCE` | Audience/resource identifier for API **access** tokens. |
| `VIBEFINANCE_OIDC_UI_CLIENT_ID` | Separate confidential web application client ID for native Streamlit login. It must differ from the API audience. |
| `VIBEFINANCE_INTERNAL_AUTH_KEY` | Random server-only key with at least 32 bytes, shared only by the trusted dashboard and API. Generate it securely; string length alone does not establish entropy. |

The launcher also requires `VIBEFINANCE_PUBLIC_URL`,
`VIBEFINANCE_OIDC_UI_CLIENT_SECRET` and `VIBEFINANCE_OIDC_COOKIE_SECRET` for native
Streamlit authentication. The callback must be the exact HTTPS
`<public URL>/oauth2callback` registered with the provider. See
[production deployment](PRODUCTION_DEPLOYMENT.md) for secrets-file generation,
managed PostgreSQL and rollout requirements.

Use an OIDC provider that issues RS256 JWT access tokens with a unique, stable
`sub`, the exact configured issuer and API audience, and integer `iat`/`exp`.
Opaque access tokens require a separate introspection implementation and are not
supported. Providers publishing signing keys on a different origin from the
issuer are not supported by this first release: select a compatible provider or
review an explicit trusted-key-origin extension before enabling it.

## Access-token verification

External API clients send `Authorization: Bearer <access JWT>`. Verification
requires an RS256 signature in native OIDC mode, or pinned ES256/RS256 in
Supabase mode, a nonempty signing-key ID, the exact issuer, a
single exact audience string, subject, issuance time and expiration time. Token
lifetime checks allow at most 30 seconds of API clock skew. A present `nbf` is
enforced; a present `token_use` must be `access`. ID tokens addressed to the UI
client do not satisfy the API audience. Providers that use generic `typ: JWT`
are supported alongside `typ: at+jwt`; audience separation is essential.

In native OIDC mode, only the administrator-configured HTTPS issuer is used to discover metadata.
The discovered issuer must match exactly and its `jwks_uri` must have the same
HTTPS host and effective port. Token-provided `jku`, `jwk`, `x5u`, `x5c`, `crit`
and `b64` headers are rejected. No redirects or unverified TLS connections are
used. Discovery/key documents have size limits; connections and reads have
bounded timeouts and a streaming time budget. Up to 32 published keys are
accepted, with RSA verification keys at least 2048 bits.

Signing keys expire after five minutes. An unknown key ID can trigger a refresh
once every 15 seconds, including after a failed fetch; this can temporarily delay
acceptance of a newly rotated key by up to 15 seconds. An expired cache is not
used when discovery or key refresh fails. Public failures contain a generic
sign-in error, without bearer tokens, provider response bodies or private claims.

The account key is the lowercase SHA-256 hex digest of canonical JSON
`[issuer, subject]`, encoded with `ensure_ascii=True` and `separators=(',', ':')`.
An email, name, editable profile ID, request header or request body cannot choose
an account owner. Subject changes at the identity provider create a new account;
account linking or migration needs a separate reviewed process.

## Native dashboard login and the internal bridge

Streamlit 1.45.1 native `st.login()` validates OIDC state/nonce and the ID token
through Authlib, then exposes identity claims in immutable server-side `st.user`.
It does not expose the access token for forwarding. Its documented identity
cookie can outlive the ID token: the application must validate `is_logged_in`,
issuer, UI audience, subject, integer `iat` and `exp` on every rerun and protected
fragment. Expired identities must sign in again.

After that validation, the trusted server signs a separate `VibeInternal`
assertion containing only issuer/subject identity and the API request context.
The API enforces the fixed internal issuer/audience, exact method and path,
issuance/start/expiration time, and a lifetime of at most 60 seconds, clipped to
the original ID-token expiration. This HMAC mechanism has a separate schema and
authorization scheme from external RS256 JWTs; external HS256 JWTs are rejected.
It does not accept `X-User-ID`, a client-supplied identity JSON object or decoded
unsigned bearer claims.

These assertions are bearer credentials. They may be replayed for the same
method/path during their short lifetime; they are not a one-time transaction
authorization, and request bodies are not signed. Keep them entirely in
server-to-server HTTP over loopback within one trusted service or verified TLS
between services. Do not return them to the browser, log them, or cache them in
shared Streamlit data caches. Compromise of the trusted dashboard or internal key
permits account impersonation; restrict service access and rotate both service
configuration and signing secrets together. Method/path binding prevents reuse
on another route or HTTP operation, not theft within the same operation.

## Acceptance required before enabling a hosted production service

1. Register the real provider application and API resource, restrict callbacks to
   the deployed HTTPS URL, and provision private managed storage and backups.
2. Deploy the opt-in configuration without allowing a demo-token bypass. Missing
   or invalid identity configuration must fail closed.
3. Sign in with two real test accounts. Create separate profiles and analyses;
   verify neither account sees the other's profiles, history, sessions, sources
   or decisions, including guessed IDs and modified request bodies.
4. Verify an expired token, wrong audience, wrong issuer, forged signature,
   shared demo token and spoofed user header cannot access protected API routes.
5. Verify logout and expiry stop protected dashboard interactions, and that
   restarting the service preserves each account's state and ownership.
6. Record provider, deployment revision, test timing and sanitized pass/fail
   evidence. Never record the tokens, callback authorization code or password.

Local cryptographic tests support the implementation. They do not establish
that an unconfigured provider, hosted callback, production database, account
isolation after migration or external backup retention has passed acceptance.

Official behavior checked against the installed Streamlit 1.45.1 `st.user` and
`st.login` documentation and `streamlit.web.server.oidc_mixin` implementation.
The [Streamlit authentication guide](https://docs.streamlit.io/develop/concepts/connections/authentication)
describes native OIDC and identity-cookie lifetime; deployment settings must
match the pinned application version.
