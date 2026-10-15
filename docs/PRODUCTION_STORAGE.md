# Production storage and account migration

Production mode uses an explicitly configured PostgreSQL database and verified OIDC accounts. The existing shared SQLite demo remains a separate mode. These changes provide and test the implementation; they do **not** establish that a live Supabase database, production identity provider, off-machine backup schedule, or protected Render account has been configured.

The zero-cost deployment target is the existing Render free web service plus a **Supabase Free** project for Auth and PostgreSQL. No paid database, disk or account was purchased or created. Free-provider quotas, inactivity pauses, service restarts, email delivery limits and the absence of a paid availability commitment remain operational limits. Confirm the provider's current free-plan terms before creating the project.

## Configuration

Install the base hashed lock, the separate authentication lock, and the storage lock into the production environment:

```bash
python -m pip install --require-hashes -r requirements.lock
python -m pip install --require-hashes -r requirements-auth.lock
python -m pip install --require-hashes -r requirements-production.lock
```

Set `VIBEFINANCE_DATABASE_URL` as a server-side secret. Do not paste it into tickets, screenshots, source control or browser settings. Use the **session pooler on port 5432** from the owned Supabase project's Connect panel when an IPv4-accessible connection is needed. Preserve the full project-specific database username and URL-encode reserved characters in the password. The actual hosted connection remains to be checked using the owner's project; a generic example hostname is not a working database.

The storage backend accepts a PostgreSQL URL with one host and requires `sslmode=verify-full`. If omitted, it explicitly adds that mode; `PGSSLMODE` cannot weaken it. Supply the provider's trusted CA through `sslrootcert`, or `sslrootcert=system` when the bundled libpq and provider certificate chain support system trust. Do not resolve certificate failures with `sslmode=require`, `verify-ca` or disabled verification. The optional binary driver bundles libpq, so verify its compatibility with the chosen provider. URL query overrides for host, host address, port or service are rejected. No database URL or driver error text is logged by this module.

`VIBEFINANCE_ALLOW_INSECURE_LOCAL_DATABASE=1` permits `sslmode=disable` **only** for the literal loopback hosts `localhost`, `127.0.0.1` and `::1`; it exists for disposable local integration databases. Leave this variable unset on Render. Automatic prepared statements are disabled for pooler compatibility. The actual Supabase session-pooler deployment has not yet been exercised; the local integration evidence is PostgreSQL 17.

Authentication configuration and verified issuer/subject handling are described in [PRODUCTION_AUTH.md](PRODUCTION_AUTH.md). The account key is the lowercase SHA-256 digest of UTF-8 JSON `[issuer, subject]` using `ensure_ascii=True` and separators `(',', ':')`. The exact verified claims identify an account; an email address, profile ID, request body or query parameter cannot select another account.

## Database isolation and schema

The application stores only these separate tables: `vf_production_schema`, `vf_production_accounts`, `vf_production_profiles`, `vf_production_sessions`, and `vf_production_decisions`. It does not open or seed the demo SQLite database in production. Startup applies schema version 1 transactionally under a PostgreSQL advisory transaction lock and rejects an unsupported version. Concurrent first-start migrations are tested. Startup creates no account rows; an authenticated owner's first profile save creates that account row and profile in one transaction. A new account has zero profiles, sessions and decisions.

Each `ProductionStore` instance is bound to one authenticated account. All application queries parameterize values and explicitly scope account ownership. Composite profile/session foreign keys prevent linking a session or decision across accounts. Forced row-level security also scopes all four data tables to the transaction-local `vibefinance.account_id`. Startup rejects superuser or `BYPASSRLS` application connections. Use a dedicated **nonsuperuser, NOBYPASSRLS** application database role. Migrations explicitly revoke table and decision-sequence privileges from `PUBLIC` and any existing `anon`, `authenticated` and `service_role` roles, overriding browser-facing default grants. Never use those browser API roles for the backend connection. A role that owns these application tables needs schema migration permission; restrict this credential to the backend. Table ownership still permits an administrator holding the credential to change policies, so this is not a defense against arbitrary execution by a compromised database administrator.

For a free managed project, inject the owned database administrator URL as `ADMIN_DATABASE_URL` and a newly generated private password (at least 24 characters) as `VIBEFINANCE_APP_ROLE_PASSWORD` into a local administrative environment. Neither value belongs in command arguments. Then run:

```bash
PYTHONPATH=. python scripts/bootstrap_production_role.py
```

This transaction creates only a **new** fixed `vibefinance_app` login, grants `CONNECT` on the selected database and `USAGE, CREATE` on `public`, and verifies that superuser, role/database creation, replication and RLS bypass are disabled. It refuses existing application roles or application objects and never resets passwords or changes an existing role. It does not provision a database or a paid resource. If the managed provider restricts role creation, use its approved SQL interface to apply the same restricted role and grants; do not deploy the administrator URL as a workaround. No live SQL-role creation was performed during this implementation.

Configure Render with the new role's connection, not `ADMIN_DATABASE_URL`. For Supabase session pooling, the username normally combines the role and project reference, such as `vibefinance_app.PROJECT_REF`; obtain and confirm the provider's current format rather than guessing it. Restrict the new role to the backend and do not grant access to unrelated tables.

Profile deletion cascades to that account's associated sessions and decisions. This is intentional production behavior and must be reflected in the UI's deletion confirmation. Account identity cannot be switched within a store operation. Session IDs may coincide in different accounts without making records visible across accounts. All stored timestamps use PostgreSQL `TIMESTAMPTZ`; application transactions use UTC. Session payloads and portfolio safeguards retain the existing application contract.

## Initialization and account transfers

From a checkout with production dependencies installed and the database URL injected privately:

```bash
PYTHONPATH=. python scripts/migrate_production.py initialize
```

This initializes/checks the schema only. Production startup also performs this check and fails closed when configuration, dependencies, storage or schema are unavailable. Request-bound store factories and public health checks perform read-only role/schema-version checks; they do not repeat DDL, migration locks or privilege changes. They never fall back to a demo account or a second database.

The local administrative CLI trusts an operator to supply **already verified** issuer and subject values; it does not authenticate arbitrary command-line claims. Keep it outside the public web routes. Examples use placeholders that must be replaced from a verified identity:

```bash
PYTHONPATH=. python scripts/migrate_production.py export-account /private/new-account-export.json \
  --issuer 'https://owned-project.example/auth/v1' --subject 'verified-subject'
PYTHONPATH=. python scripts/migrate_production.py import-account /private/new-account-export.json \
  --issuer 'https://owned-project.example/auth/v1' --subject 'verified-subject'
```

An account export is plaintext sensitive portfolio data. On POSIX it is published as a new file with mode 0600, synchronized before publication and never overwrites an existing file or symlink. On Windows the destination directory must already have a private inherited ACL; mode bits do not establish Windows ACL protection. Keep these short-lived transfer files private and remove them after the controlled transfer. Use the separate encrypted production recovery tooling for operational backups and off-machine storage.

Import validates the account hash, profile schema, unique IDs, aware timestamps, payload identity, metrics, and session/decision references before database writes. It permits **only an empty target account**, inserts all selected data in one transaction and serializes parallel restores. It never merges profiles, overwrites sessions, resets other accounts or accepts another account's snapshot. Decision ordering and timestamps are retained; database-local decision sequence IDs are reassigned on account transfer.

Shared demo data has no reliable per-person account ownership mapping. Migration is therefore explicit, operator-attested and restricted to selected owned profiles from an existing read-only backup:

```bash
PYTHONPATH=. python scripts/migrate_production.py import-owned-sqlite /private/owned-backup.sqlite3 \
  --issuer 'https://owned-project.example/auth/v1' --subject 'verified-subject' \
  --profile-id 'my-owned-profile' --confirm-owned-backup
```

Do not migrate shared demonstration profiles into a person's account merely because their IDs exist. The CLI imports only the named profiles and their linked sessions/decisions; it verifies source integrity without modifying the SQLite backup. Existing session/decision timestamps are preserved. SQLite profiles had no stored modification timestamp, so the transfer records the actual export instant for that field and does not invent a historical timestamp.

## Verification and remaining acceptance

Real disposable PostgreSQL 17 integration tests use verified TLS with an ephemeral test CA and a table-owning role with `NOSUPERUSER NOBYPASSRLS`. They cover concurrent migrations, empty new accounts, same profile/session IDs across accounts, foreign-tenant access denial, forced RLS against unscoped SQL, revocation of browser-role default grants, hostile strings as data, decision ownership, deletion isolation, export/import rollback, read-only request/health checks, restricted-role bootstrap and reconnect persistence. Unit tests cover TLS policy, identity construction, invalid snapshots, explicit SQLite selection and private no-overwrite exports. These tests do not validate provider billing, a live Supabase connection, long-term retention, SMTP delivery or an actual hosted account.

With Docker and OpenSSL available and the hashed optional dependencies installed, run the reproducible disposable database checks from the repository root:

```bash
.venv/bin/python scripts/check_production_storage.py
```

The runner uses the official PostgreSQL 17 image pinned to digest `sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3`. It generates an ephemeral CA, verifies the server certificate and hostname, uses random in-memory database passwords, exercises restricted application roles plus privileged backup/restore roles, and removes its own test container, network and temporary certificates afterward. Its default test groups cover storage, API isolation and encrypted production backups. It injects test database URLs only into the test process environment and prints no connection URLs or private material. Optional arguments select specific pytest paths. The ordinary core-only suite skips database integration when these disposable-test environment variables are absent.

Before production is accepted, configure the owned free project and application role, run the live verified-TLS connection/startup check, create two real test accounts, confirm each begins empty, save separate portfolios, verify session/history/decision and source isolation, sign out and back in, restart the service, and verify retained state. Exercise the encrypted off-machine backup/restore procedure into a separate empty owned database and record its result. Keep Render's shared demo unchanged until these concrete settings and limitations have been reviewed. No forecasting scores or frozen research artifacts are altered by storage migration.
