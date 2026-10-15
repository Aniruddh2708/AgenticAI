# Hosted acceptance and state recovery

These tools verify an existing release and recover a local SQLite snapshot.
The new Supabase candidate also has protected acceptance and encrypted
PostgreSQL recovery tooling. They do not deploy code, change Render's service
plan or token, reset a running database, or promote forecasting research.
Keep the existing login gate enabled.
See [Render configuration](RENDER.md) and [the updated blueprint](BLUEPRINT_UPDATED.md).

## Check the hosted release without credentials

`scripts/check_hosted.py` checks public health, the revision received from the
Streamlit websocket, and a password-type demo login field. Supply the exact
deployed commit. The examples use HEAD from a clean released checkout; when checking another release, pass its known commit explicitly:

```sh
python scripts/check_hosted.py --expected-revision "$(git rev-parse HEAD)"
```

The command prints a small JSON result and exits nonzero on failure, a missing
gate, or a mismatched revision. It uses inherited proxy settings and CA trust,
with certificate and hostname verification enabled. HTTP is accepted only for a
loopback local test. Health alone does not establish release identity. A public
revision is an application marker, not a security attestation or Render
control-plane deployment record. Public checks create an unauthenticated
Streamlit session but do not submit a token or call protected controls.

The checker needs optional `websocket-client` operator tooling. Keep it outside
the application's dependency locks; for example, from the repository root:

```sh
python3.11 -m venv .runtime/operations-tools
.runtime/operations-tools/bin/python -m pip install --require-hashes -r requirements.lock
.runtime/operations-tools/bin/python -m pip install websocket-client==1.9.2
.runtime/operations-tools/bin/python scripts/check_hosted.py --expected-revision "$(git rev-parse HEAD)"
```

Use an existing trusted package index and normal TLS. No application lockfile
change or browser installation is needed for these public checks. Render free
tier may cold-start: the default total budget is 120 seconds; `--timeout` accepts
1–300 seconds. A policy denial is a configuration problem, not a reason to disable
the proxy or certificate checking.

## Optional protected browser acceptance

Protected hosted acceptance remains pending until an operator supplies legitimate
access through secure environment configuration. Do not ask for the private demo
password in chat, search secret files, or use a Render/GitHub API key as a demo
token. `--protected-token-env` accepts a **variable name**, never a token value.
The checker never prints that value, page contents, browser traces or screenshots.

**Dashboard login currently automatically analyzes the selected demo investor and
ticker, saving a session.** A protected browser check therefore needs explicit
authorization for that write on the chosen target. There is no read-only browser
login mode. The script requires a separate acknowledgement and otherwise refuses:

```sh
# CHECK_HOSTED_TOKEN must already be supplied securely by the caller.
.runtime/operations-tools/bin/python scripts/check_hosted.py \
  --url https://vibefinance.onrender.com \
  --expected-revision "$(git rev-parse HEAD)" \
  --protected-token-env CHECK_HOSTED_TOKEN \
  --allow-protected-session-write
```

Install optional browser tooling only in the isolated tooling environment when
this check is authorized:

```sh
.runtime/operations-tools/bin/python -m pip install playwright==1.56.0
.runtime/operations-tools/bin/python -m playwright install chromium
```

An existing Chromium can instead be selected with `--browser-executable`.
Chromium must trust the operator's CA itself; Python's `SSL_CERT_FILE` alone may
not configure Chromium's trust store. Fix browser CA installation if needed;
never add `ignore_https_errors` or disable certificate validation. The protected
check opens Metrics and the saved research report, verifies its research-only
label, and does not save a decision, edit an investor, scan a watchlist, download
prices or retrain anything. A passed public check does not imply these private
workflows passed. Failure JSON contains only sanitized exception types.

## Personal-account hosted acceptance

The zero-cost account candidate is described in
[FREE_PRODUCTION_STATUS.md](FREE_PRODUCTION_STATUS.md). It has not been activated
on the existing Render service. For a released Supabase candidate, add
`--login-kind supabase` to the public command; the checker requires Email and
password-type Password fields instead of the shared demo gate.

Protected acceptance reads an existing confirmed operator account from secure
environment bindings. Pass variable names only:

```sh
python scripts/check_hosted.py \
  --url https://vibefinance.onrender.com \
  --expected-revision "$(git rev-parse HEAD)" \
  --login-kind supabase \
  --account-email-env CHECK_HOSTED_EMAIL \
  --account-password-env CHECK_HOSTED_PASSWORD \
  --allow-protected-session-write
```

The owner must create a profile before this check. Empty accounts return
`operator_profile_required: true`; the checker never creates one. Signing in
with an existing profile saves an analysis session, hence the explicit write
flag. Do not combine personal-account flags with `--protected-token-env`.
The checker validates credential names and presence before network access and
retains no browser trace, screenshot, page contents or raw exception messages.
Local fixture success does not establish live provider acceptance.

Managed account data uses [PRODUCTION_RECOVERY.md](PRODUCTION_RECOVERY.md),
including authenticated encrypted exports and a manual one-day ciphertext-only
artifact workflow. SQLite instructions below apply to the shared demo.

## Back up committed SQLite state

`scripts/backup_state.py` uses SQLite's online backup API, including committed WAL
data, rather than copying a live `.sqlite3` file. It validates database integrity
and the application's table/column layout before publishing a snapshot.
Profiles, history, sessions and saved decisions are sensitive shared-demo data.
On POSIX, backups are owner-readable/writable (`0600`) and must live in a private directory:

```sh
install -d -m 700 .runtime/backups
python scripts/backup_state.py backup \
  .runtime/vibefinance.sqlite3 .runtime/backups/state-2026-10-15.sqlite3
```

Use the actual configured `VIBEFINANCE_STATE_DIR` source. The destination must be
new and its parent must exist. An existing file or symlink is never overwritten;
failed copying/validation creates no destination. The validated temporary file is
published atomically with an exclusive hard link on the same filesystem. The
source is read-only; concurrently committed transactions produce a consistent
snapshot. Do not delete WAL/SHM files while a service is running.

On Windows, use a destination directory whose inherited ACL is restricted to the
operator before running the tool. Python's `chmod` does not establish an
owner-only Windows ACL; this script does not claim that it does. NTFS hard links
provide exclusive publication; use a filesystem that supports hard links. Files
are flushed on both platforms, and the parent directory is additionally fsynced
on POSIX. Unsupported filesystem operations fail rather than falling back to an
overwrite-prone copy. If final directory syncing fails after publication, the
command reports failure and leaves the complete destination in place for
inspection; a retry must still use a new destination.

Store encrypted copies outside the service's ephemeral filesystem with access
limited to authorized operators. This tool does not configure a cloud backup
service, automatic schedules, retention, or encryption. An on-service backup alone
does not survive a free-tier filesystem replacement. Never commit database files
or upload profiles to public artifacts. Test recovery before relying on a backup.

## Restore to a new path, then verify

Restore never swaps or overwrites the running application's database:

```sh
install -d -m 700 .runtime/recovery-check
python scripts/backup_state.py restore \
  .runtime/backups/state-2026-10-15.sqlite3 \
  .runtime/recovery-check/vibefinance.sqlite3
```

This repeats online copying, integrity/schema validation, private file creation
and exclusive publication. Run an isolated application against the recovered
directory and verify expected profiles, history and decisions without printing
private contents. Local tests exercise actual stored profiles, sessions and
decisions, a concurrent WAL writer, invalid sources, and competing destination
creation. Integrity validation establishes structural consistency, not that an
operator selected the correct historical snapshot.

Switching the real service to a recovered state is a separate operator action:
stop writes, preserve its previous state, review the snapshot and recovery point,
then deliberately select the new state path. No production state or existing
Render storage is changed by these tools. Durable hosting, automated encrypted
off-service backups, retention, and a production recovery rehearsal remain
deployment decisions; they are not completed by the local restore test.
