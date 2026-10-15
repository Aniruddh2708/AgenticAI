# Managed accounts and durable storage: zero-cost candidate

The production candidate uses **Render's free web service and an operator-created
Supabase free project** for managed sign-in and PostgreSQL. The existing shared
demo remains unchanged until the candidate passes review. No account, paid plan,
database, disk, billing subscription or remote deployment was created by adding
these files. Do not select a paid plan or enable usage overages.

`deploy/render.production.yaml` is a reviewable candidate with `plan: free`, no
database/disk stanza and automatic deploys disabled. Applying a Blueprint still
creates a remote service; review the provider's current free eligibility and
displayed cost before doing so. Reusing the existing free service after testing
avoids an unnecessary second service. Free providers may sleep, pause inactive
projects, impose connection/email/storage/traffic limits, change their terms or
require manual recovery. This is a constrained hosted application, not a promise
of continuous availability or unlimited production capacity.

## What the repository supplies

- Separate opt-in production image at `deploy/Dockerfile.production`, with the
  original hash-locked application plus separately locked identity/database
  dependencies. It runs as UID 10001, keeps the API on loopback and exposes only
  the dashboard. The existing demo image and shared-password deployment remain
  supported.
- Managed account authentication and a PostgreSQL store bound to verified
  identity. Production must fail closed if identity or database configuration is
  missing; it must not fall back to the shared demo or SQLite.
- A safe local configuration check, `python -m
  vibefinance.production_startup`. It prints missing **names**, sanitized errors
  and whether optional packages are installed. Success proves configuration
  syntax and dependencies only; it does not connect to the provider or database.
- Encrypted application-data backup/restore tooling documented in
  [PRODUCTION_RECOVERY.md](PRODUCTION_RECOVERY.md). Free storage is not a backup;
  an operator must retain encrypted exports outside the running service and test
  restoration.

## Secure configuration for the free candidate

Create/select a **free** Supabase project in the operator's own account. No
Supabase account/session, project URL or credentials are available in the cloud
environment at the time this candidate was prepared. Do not paste passwords,
connection strings, recovery keys or sign-in tokens in chat or tracked files.
Enter values through the providers' secure environment settings.

| Variable | Required value/purpose |
| --- | --- |
| `VIBEFINANCE_AUTH_MODE` | `supabase`; enables individual managed accounts. |
| `VIBEFINANCE_SUPABASE_URL` | Exact project HTTPS origin from the Supabase dashboard. |
| `VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY` | New `sb_publishable_...` public API key. Never use a secret/service-role/admin key. |
| `VIBEFINANCE_DATABASE_URL` | Secret PostgreSQL connection URL for this project's application database, with `sslmode=verify-full`. |
| `VIBEFINANCE_PUBLIC_URL` | Exact deployed HTTPS origin, for example the chosen free Render service origin. No path/query/fragment/userinfo. |

Choose the Supabase dashboard's **session pooler** connection string if the
hosting network does not support the direct database's address family. Keep the
provider-supplied hostname so TLS hostname verification works. Do not switch to
`sslmode=require`, `disable` or a numeric host to get around a connection error.
The production image uses `/etc/ssl/certs/ca-certificates.crt` as libpq's trusted
root bundle (`PGSSLROOTCERT`). Supply an appropriately verified CA path if using
another runtime. Configure a least-privilege database role and keep application
tables inaccessible through Supabase's public API; the application server must
enforce account ownership on every operation.
Use the dedicated non-superuser, non-`BYPASSRLS` role and bootstrap procedure in
[PRODUCTION_STORAGE.md](PRODUCTION_STORAGE.md); the provider's administrative
database role is not an acceptable runtime role.

In Supabase Authentication, enable the intended email/password flow, retain
email confirmation, configure the application's exact HTTPS Site URL/allowed
confirmation redirects and review sign-up/email rate limits. Verify an actual
email-confirmed account before opening registration. Provider email delivery,
abuse prevention, reset/confirmation behavior and quotas require live provider
acceptance; fixture tests cannot establish them.

The Supabase managed mode does not require a private demo password, OIDC client
secret, native Streamlit OIDC cookie secret or service-role key. Session tokens
are private server-session state; they must not be embedded in URLs, logs,
screenshots or saved reports.

## Review and deploy sequence

1. Review current code, candidate configuration and the providers' displayed
   zero-cost terms. Leave the working demo available during setup. Configure
   secrets in Render settings without copying them into the repository.
2. Build the production Dockerfile using the three hash-locked requirement
   files. Run the local configuration CLI inside the same image. Check that a
   missing provider/database refuses startup and that no production database is
   silently substituted.
3. Verify the provider-backed candidate with two disposable confirmed accounts:
   registration/login, expiry/refresh, logout/revocation, profile creation,
   analysis, history and decisions. An account must never read or mutate the
   other's records even when IDs are supplied directly. Check request denials,
   restart persistence and encrypted recovery to an empty database. Preserve
   portfolio guardrails and keep research scores separate from recommendations.
4. Inspect both dashboard and API health, the exact Git revision and logs with
   secret/token redaction. Complete protected hosted acceptance using the
   operator-controlled account session; no private demo password is needed.
5. Only after review, switch the intended free service to the production
   Dockerfile and managed environment. Recheck the visible revision and account
   isolation. Keep a tested backup and a concrete rollback route; reverting to
   the demo does not expose, copy or migrate managed private account records.

Do not seed managed storage from the shared demo automatically. Any migration
must identify the consenting owner and verify a scoped export before importing
it. Preserve the original demo database and historical forecasting artifacts.

## Optional native OIDC mode

An existing organization-managed OIDC provider can be used instead of Supabase;
it is not necessary for the zero-cost route. The optional mode needs
`VIBEFINANCE_AUTH_MODE=oidc`, a trusted HTTPS
`VIBEFINANCE_OIDC_ISSUER`, distinct `VIBEFINANCE_OIDC_AUDIENCE` and
`VIBEFINANCE_OIDC_UI_CLIENT_ID`, a server-only
`VIBEFINANCE_INTERNAL_AUTH_KEY` of at least 32 bytes,
`VIBEFINANCE_OIDC_UI_CLIENT_SECRET` and
`VIBEFINANCE_OIDC_COOKIE_SECRET` of at least 32 bytes. Configure the provider's
callback to the exact `VIBEFINANCE_PUBLIC_URL` plus `/oauth2callback`. The optional
`VIBEFINANCE_PUBLIC_HOSTS` comma-separated list can further restrict that
configured public host. Request Host/forwarded headers never choose a callback.

Installed Streamlit 1.45.1 documents `[auth]` `redirect_uri`/`cookie_secret` and
named `[auth.oidc]` `client_id`/`client_secret`/`server_metadata_url`; it also
supports `--secrets.files`. `prepare_oidc_secrets` writes those values atomically
to a unique mode-0600 file in an owned mode-0700 Linux runtime directory, outside
the checkout. The launcher passes that path and removes its own file at exit.
It never edits operator-owned secrets files. Native Streamlit handles OIDC
state/nonce; the application must still validate the verified identity/expiry
and enforce account ownership on each request. No raw secret values are printed
by the preflight tool.

## Remaining acceptance and research limits

The local production candidate was built with all three hash-locked dependency
files using verified cached wheels and the pinned Python base. The image
`sha256:40b4e67285aa75133e06ed7ab2777a0870158d8da6b74225a2257b44997e364e`
passed disposable runtime checks against real PostgreSQL 17 with
`sslmode=verify-full` and an ephemeral trusted test CA. Checks covered startup,
PostgreSQL/BM25 health (21 chunks), UID 10001, anonymous API rejection, absence of
SQLite fallback, rejection of an untrusted CA, restart persistence, scoped store
fixture isolation and the Chromium managed-account login form with no JavaScript
errors. All 48 packaged Python files matched the tested working tree. The 36
startup unit checks also passed. Only owned test containers/network were removed;
no existing demo or remote provider was changed by these checks.

The final packaging image
`sha256:a1ec5bbc4b4018f74bac4b660e510117642f6dc0e349fc17b60918bcb4dbd7b1`
contains the subsequent administrative argument-parser/standalone-import fixes. All web
application modules/dependencies are identical to the runtime-tested image;
current Python source and dependency-lock hashes match. The backup, role
bootstrap and migration commands all pass `--help` as UID 10001 with `PYTHONPATH`
removed and the working directory set to `/tmp`. Help/invalid arguments stop
before administrative credentials are read or actions run. Separate local
subprocess tests also cover execution with Python's `-I` isolated mode.

The existing demo image was also rebuilt using **only the original 52 locked
dependencies**. Image
`sha256:cb3b13b97efda392fad7092f87fa472eeaa72c11d45902b4fc9ef9d74b60d92d`
passed both-service health, 21-chunk BM25 retrieval, the browser/password gate,
private API rejection, three original seed profiles, five-agent Meera REDUCE
with the concentration safeguard, SQLite session persistence and exact current
Python source parity. `jwt`, `cryptography`, `authlib` and `psycopg` were all
absent; the optional production imports did not break the original demo.

The original extended dashboard check also passed with
`VIBEFINANCE_AUTH_MODE=demo VIBEFINANCE_EMBEDDINGS=0 .venv/bin/python scripts/check_dashboard_extended.py`.
It exercises profile editing/creation, cache refresh, input validation, both
display modes, source highlighting, unsaved sources/disabled decisions, shared
token login and API failure containment in isolated temporary state.

The provider URL/key in that run were synthetic and no credentials were entered
into the browser. It therefore establishes local production runtime behavior,
not a successful real Supabase registration/login or protected Render session.

Local tests and packaging do not create or prove a real Supabase project,
confirmed user, verified database TLS connection, email delivery, hosted session
or provider backup. Those remain pending until the operator supplies the
project configuration securely and the live checks pass. Current environment
network policy must explicitly allow the exact project origin and database
connection before cloud acceptance; a saved configuration draft is not applied
network access.

Independent market-data verification and prospectively issued, matured outcomes
remain separate gates. Do not backdate issuance or tune against spent test
periods. Managed accounts and persistence do not establish predictive advantage.
