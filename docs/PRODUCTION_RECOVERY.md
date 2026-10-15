# Production recovery

`scripts/backup_production.py` backs up the version 1 VibeFinance application
schema from PostgreSQL and encrypts it with AES-256-GCM. It preserves all
accounts, profiles, saved analysis sessions, decisions, database timestamps,
decision IDs and the decision sequence high-water mark. The schema initializer
recreates foreign keys, validation constraints and forced account row isolation.
It copies a single repeatable-read, read-only database snapshot, rather than
separate inconsistent table reads. Sequence reservations can create harmless
gaps during concurrent writes; the saved sequence never reuses a captured ID.

This is an application logical backup. It does **not** preserve database roles,
role passwords, grants, original ownership, extensions, arbitrary SQL objects, other
applications, Supabase Auth users or identity-provider configuration. Those
resources need their provider's separate recovery process. It supports exactly
the five `vf_production_*` version 1 public tables; incompatible tables or extra
public application tables are rejected. Backups materialize in memory and are
limited to 128 MiB of serialized application data. Larger deployments need a
reviewed streaming backup process or provider-managed database backups.

## Private configuration

Install the optional production and authentication dependency locks in addition
to the core lock. No PostgreSQL client binary is needed; the tool uses psycopg
and works independently of the server's `pg_dump` client version.

Set these through the operator's secret manager, never command arguments,
checked-in files or shared logs:

- `VIBEFINANCE_DATABASE_URL`: the configured application database URL using a
  dedicated recovery administrator with `BYPASSRLS` and permission to read the
  five application tables and sequence. Ordinary account roles must not receive
  this privilege. RLS stays enabled; a partial account-filtered backup is refused.
- `VIBEFINANCE_BACKUP_KEY`: a securely generated random 32-byte encryption key,
  standard or URL-safe base64 encoded. A human password is not a suitable key.
- `VIBEFINANCE_RESTORE_DATABASE_URL`: a separately provisioned target deployment
  whose **public application namespace is empty**, using the recovery
  administrator. Never alias this to the live URL. Existing provider-managed Auth
  and storage schemas can remain; the tool does not copy or modify them.

For restore, also provision an explicit application owner role with `LOGIN`,
`NOSUPERUSER` and `NOBYPASSRLS`, and the ability to create in the public schema.
The recovery administrator must be able to `SET ROLE` to this role and insert
the restored rows. The tool creates application schema/policies as that role,
then restores rows as the administrator. Consequently normal app startup can
migrate its own tables without granting account-security bypass to the app.

Remote connections require `sslmode=verify-full`, with a trusted provider CA
when necessary. The connection helper pins this default even if `PGSSLMODE` is
weaker. `--allow-local-insecure` is only for explicit disposable loopback tests;
it cannot weaken a remote connection. Do not disable TLS verification to work
around a certificate error. A provider pooler URL may be used only if it supports
these transactions and permissions; prefer the provider's documented direct or
session-mode administrative endpoint for recovery.

Use a POSIX runner and an existing directory owned by that operator with mode
0700. The production container runs as an unprivileged user; a mounted recovery
directory must be writable by that user. This implementation deliberately
refuses Windows file operations because it cannot assert owner-only Windows ACLs.
The local SQLite demo recovery tool remains separate.

## Backup and authenticate

From the repository checkout or the production image containing the script:

```bash
umask 077
mkdir -m 700 /private/vibefinance-backups
python scripts/backup_production.py backup \
  --database-url-env VIBEFINANCE_DATABASE_URL \
  --key-env VIBEFINANCE_BACKUP_KEY \
  --destination /private/vibefinance-backups/backup-2026-10-15.vfenc
python scripts/backup_production.py verify \
  --key-env VIBEFINANCE_BACKUP_KEY \
  --source /private/vibefinance-backups/backup-2026-10-15.vfenc
```

Choose a new filename for each run. File paths must contain no `..` or symlink
directories. The tool walks directory handles, rejects symlink destinations,
writes only encrypted temporary bytes with mode 0600, fsyncs them and publishes
the result atomically with an exclusive hard link. Existing files are never
replaced, including a competing writer's file. A final durability error can
leave a complete encrypted destination; verify it before choosing another name.
No plaintext dump file is created. Decrypted application data exists only in
process memory during backup, verification or restore.

The public envelope contains only format/version, UTC creation time, cipher,
serialized byte count and SHA-256. AES-GCM authenticates that metadata and the
encrypted snapshot. Account names, database URLs and passwords are absent from
metadata and CLI output. Verification checks the complete authentication tag,
hash, schema and account references before a restore can open its target.
Wrong keys, modified headers and modified ciphertext fail closed.

## Restore drill

Provision a target with an empty application namespace explicitly. The tool neither creates a remote service
nor chooses a paid plan. A free Supabase development project or a disposable
local PostgreSQL database can host a drill within the provider's documented
limits. Provider-managed Auth, storage and extension schemas are left untouched;
extension-owned public objects and their internal dependencies are also retained.
Any other existing public user object, including any VibeFinance table, blocks
the restore. Do not delete provider tables to force acceptance.

```bash
python scripts/backup_production.py restore \
  --database-url-env VIBEFINANCE_RESTORE_DATABASE_URL \
  --key-env VIBEFINANCE_BACKUP_KEY \
  --source /private/vibefinance-backups/backup-2026-10-15.vfenc \
  --owner-role vibefinance_app \
  --confirm-empty-target
```

Restore refuses any existing public user relation, function or type unless it
belongs to an installed extension. It creates application schema, row isolation,
rows and sequence in one transaction. It uses no `DROP`, `TRUNCATE`, replacement
or upsert against account data. A constraint failure or object collision rolls
the operation back. Stop other access to the new recovery target for the drill;
the advisory lock coordinates this application's migration/recovery tools, not
unrelated DBA clients. The target must remain dedicated to recovery until it is
accepted. The command never changes the source database or switches the app URL.

After restore, independently compare account exports and saved session/decision
history with the backup, check row isolation using a non-administrative runtime
role, and recreate any additional least-privilege grants through the provider's
reviewed procedure. Verify identity-provider issuer/subject compatibility before
switching the application. Backup does not migrate Supabase Auth credentials.
Accounts are keyed by the exact verified issuer and subject. A new data database
can continue using the original surviving Auth project and those same subjects.
If the original Auth project is lost, separately recover that provider identity
data or perform a reviewed explicit identity migration; restoring application
rows into a new Auth project does not recreate the original accounts. Never
silently reconnect an account by matching its email address.
Keep the original database and previous app release available during acceptance.

## Retention and off-service copies

No hosted scheduler, object-store bucket, upload credentials or retention policy
has been silently provisioned by this script. A temporary cloud workspace or the
Render container filesystem is not an off-service backup. A successful local
drill does not establish that production backups are scheduled or recoverable.

Before accepting production, configure an operator-owned free private backup
destination or an existing approved private bucket, and transfer only the
authenticated encrypted artifacts. Keep the encryption key in a separate secret
manager, with a tested recovery copy accessible to the authorized operator. Do
not put the key alongside the backup. Decide retention within the free quota,
verify every transfer, and record a restore drill using a downloaded copy.
Capture at least a daily snapshot and one before schema/release changes using an
existing trusted scheduler or an operator-run process. This describes the
operating requirement; it does not claim that a remote schedule or upload exists.

Key rotation requires retaining the key for each retained artifact or deliberately
decrypting and re-encrypting it in a private recovery process. Losing a key makes
that artifact unrecoverable. Never log a key to demonstrate backup readiness.

## Manual backup without a Render shell

The candidate [production-backup.yml](../.github/workflows/production-backup.yml)
provides an operator-triggered GitHub Actions route for a Windows operator using
Render's free service without shell access. It has **only** `workflow_dispatch`;
there is no schedule, deployment trigger, pull-request trigger or automatic
database access. It is prepared configuration, not a completed production backup:
no real database secrets were supplied and no live run was dispatched here.

The job uses a standard GitHub-hosted Linux runner, a ten-minute timeout,
hash-locked dependencies and a verified-TLS database connection. Only the
encrypted `backup.vfenc` file can be uploaded, after authentication, owner-only
permission checks and a 10 MiB hard upload limit. The artifact retention is one
day, compression is disabled for ciphertext, an absent file fails the upload,
and cleanup removes the runner copy. Keys, connection strings, database JSON and
child-process diagnostics are neither uploaded nor printed. Only the backup step
receives the two secrets. Read-only repository permissions and checkout without
persisted credentials limit the workflow's repository access.

The upload action is pinned to
`actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02`, verified
against the official repository's `refs/tags/v4` through GitHub's API on
2026-10-15. Checkout and Python setup also use fixed official action commits.
Review a trusted release revision before handing it production secrets; do not
select unreviewed branches for a manual run.

1. Confirm the GitHub account's current Actions and artifact-storage quotas,
   eligibility and **zero-spending/overage settings** before enabling this route.
   A bounded manual job does not guarantee zero charges under every account's
   existing usage or future provider terms. Do not enable a paid plan or paid
   overages to make the workflow pass. If the free quota is exhausted, wait for
   renewal or use an existing private operator-controlled runner/destination.
2. Once the reviewed workflow is available on the repository's default branch,
   open **Settings → Secrets and variables → Actions → New repository secret**.
   Add `VIBEFINANCE_BACKUP_DATABASE_URL` for the dedicated privileged recovery
   administrator, not the web application's restricted role, and
   `VIBEFINANCE_BACKUP_KEY` for the random base64-encoded 32-byte key. Obtain the
   provider's direct or session-pooler administrative URL with `sslmode=verify-full`.
   Keep a separate recovery copy of the encryption key in the operator's secret
   manager. Never put either value in chat, workflow input, a commit or a log.
3. Open **Actions → Manual encrypted application backup → Run workflow**.
   Select the reviewed release revision and check the acknowledgement only after
   reviewing its code, secret bindings and current free quotas. An unchecked
   acknowledgement skips the job. Do not dispatch until those prerequisites are
   real; an empty configuration is not a backup drill.
4. After success, download `vibefinance-encrypted-backup-<run>-<attempt>` from
   that run **within one day**. Extract only `backup.vfenc` into an operator-owned
   private directory and copy it to the approved off-service backup location.
   Delete the short-lived GitHub artifact after confirming the downloaded copy.
   In a public repository, workflow artifacts can be downloadable by other
   signed-in repository readers. Encryption protects their contents, but this is
   not a private artifact-access guarantee; artifact names and size are also
   visible. Use a private destination instead if this exposure is unacceptable.
5. Authenticate the downloaded file with the same key on a trusted POSIX runner,
   then complete the empty-application-namespace restore drill described above.
   Windows can download and retain the encrypted file, but this recovery CLI's
   file-permission enforcement requires POSIX. A private Linux workstation or
   existing trusted WSL environment can run the verification/restore; no paid
   Render shell is required. Supply secrets through that runner's secure
   environment and never echo them.
6. Record the reviewed source revision, successful run ID, download time,
   verification result and restore drill result without account data or secrets.
   Retain the downloaded artifact under the chosen retention policy, separately
   from its key. Repeat manually or configure an existing trusted scheduler only
   after quota/cost review. This workflow adds no automatic schedule.

An Actions artifact is short-lived delivery, not a durable backup SLA, encrypted
key escrow, Supabase Auth backup or proof of a successful off-service restore.
The local validation parsed the workflow and exercised its command arguments,
missing-secret, failed-backup, failed-verification and oversized-artifact guards
without credentials or any real GitHub upload. Real configuration, dispatch,
download, authentication and recovery remain operator acceptance steps.

## Verification evidence

`tests/test_production_backup.py` exercises encryption/authentication, metadata
tampering, wrong keys before database connection, invalid account references,
sequence validation, owner-only files, symlink/path traversal refusal and an
exclusive-publication race. Its optional integration creates real profiles,
sessions and decisions for two accounts in an owned PostgreSQL 17 source,
encrypts them, restores into a second pristine database, compares all captured
rows/timestamps/IDs, verifies forced row isolation and the next sequence value,
then proves a repeated restore preserves existing target and source state.
Provider Auth-schema and public-extension sentinels remain unchanged. The
restored schema belongs to the explicit non-administrative application role,
and ordinary application startup and writes work under that role.

The integration requires explicitly supplied disposable
`VIBEFINANCE_TEST_POSTGRES_URL`, `VIBEFINANCE_TEST_POSTGRES_ADMIN_URL`,
`VIBEFINANCE_TEST_POSTGRES_RESTORE_URL` and
`VIBEFINANCE_TEST_POSTGRES_RESTORE_APP_URL`; normal tests skip it rather than using a
live production database. These checks establish local implementation behavior,
not a completed production off-service backup or Supabase Auth recovery drill.
