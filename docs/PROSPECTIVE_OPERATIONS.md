# Operating the prospective forecasting ledger

This runner makes the existing [prospective protocol](PROSPECTIVE_EVALUATION.md)
operational without registering a study, downloading data, fabricating missing
observations or selecting a model. It consumes explicitly supplied, locally
reconciled evidence. **No real experiment or new market score is created by
installing or testing this command.**

## Prerequisites and the waiting period

Before the first cycle, obtain authorized independent prices, corporate actions,
complete exchange calendars and review of rights and the point-in-time universe.
Pass the [F1 evidence reconciliation](DATA_VERIFICATION.md), then register a
future study using `scripts/prospective.py register`. Preserve the protocol and
implementation freeze. A historical mirror, a checksum, an editable approval
flag, a new folder or a changed date does not satisfy these requirements.

Independently witness the registration before issuing any forecast. Keep the
external receipt and archive registration/ledger identities outside this
workspace. This runner checks receipt fields, matching identity and chronological
ordering; it **does not authenticate a witness service, license, exchange close
or provider timestamp**. Those are reviewed external evidence. Local hashes
cannot defeat a malicious rewrite/truncation without an independent archive.

An outcome needs an actually issued forecast followed by **30 observed verified
sessions**. It cannot be finished before those sessions close. The protocol also
requires 24 non-overlapping origins per security, eight quarters and sufficient
observations in both declared regimes before uncertainty is supported; that
likely means years of observation. Today's engineering work cannot supply this
future evidence or establish a learned predictive advantage.

## Local inputs

Use a versioned, immutable directory for each observation batch. Keep CSV/Parquet
artifacts, the passed F1 report and the session-batch JSON together. Do not edit
old batch files to prepare a later cycle. The batch contract, source-vintage
rules and same-vintage dividend/split target construction are unchanged from the
core prospective workflow.

Create an inputs manifest next to those directories:

```json
{
  "schema_version": 1,
  "registration_witness": "registration-witness.json",
  "calendar_batch": {
    "data": "YYYY-MM-DD/calendar-batch.json",
    "artifact_root": "YYYY-MM-DD"
  },
  "operations": [
    {
      "kind": "outcome",
      "origin": "ACTUAL-ISSUED-ORIGIN-DATE",
      "data": "YYYY-MM-DD/origin-plus-thirty-sessions.json",
      "artifact_root": "YYYY-MM-DD"
    },
    {
      "kind": "forecast",
      "data": "YYYY-MM-DD/current-closed-origin.json",
      "artifact_root": "YYYY-MM-DD"
    }
  ]
}
```

These paths and dates are **format placeholders**, not supplied market data.
Use ISO dates from real records. All input-file and artifact-root paths must be
relative to the manifest directory. Absolute paths, traversal and symlink escapes
are rejected. The optional calendar batch helps establish maturity/readiness; it
is independently reconciled and source-checked like every other batch. It does
not create a forecast or an outcome. An empty `operations` list is suitable for a
read-only readiness check.

The witness JSON must identify the actual registered study:

```json
{
  "registration_sha256": "ACTUAL-REGISTRATION-SHA256",
  "witnessed_at_utc": "ACTUAL-TIMEZONE-AWARE-TIMESTAMP",
  "provider": "INDEPENDENT-WITNESS-PROVIDER",
  "evidence_ref": "https://witness.example.org/actual-receipt",
  "reviewed_by": "ACTUAL-INDEPENDENT-REVIEWER"
}
```

This is a contract example, not a genuine witness receipt. Its timestamp must
follow registration, cannot be in the future, and must precede the first issued
forecast. HTTPS witness references cannot embed URL user information.

## Readiness, issuance and outcomes

```bash
python scripts/run_prospective_cycle.py ready \
  --run-dir .runtime/prospective/baselines-v1 \
  --inputs /authorized-data/cycle-inputs-YYYY-MM-DD.json

python scripts/run_prospective_cycle.py run \
  --run-dir .runtime/prospective/baselines-v1 \
  --inputs /authorized-data/cycle-inputs-YYYY-MM-DD.json
```

`ready` never writes to the study. Optional `--output /new/path.json` exclusively
creates a report; it refuses overwrite. With no registered study, readiness
lists the missing registration and dependent real-data/review/witness/input
requirements. It does not claim to have checked evidence that was not supplied.

Readiness reports the next scheduled origin only if supplied, independently
reconciled calendar scopes establish it. It counts remaining verified sessions
and separately lists matured but missing outcomes, pending maturity and missed
issuance. Disconnected calendar fragments do not bridge unknown sessions.
**Calendar days to an unknown origin/target remain `null`**; no weekday heuristic,
future exchange calendar or guaranteed completion date is invented. Reported
maturity is conditional on the supplied verified evidence. An old calendar does
not establish that a real-world target remains unexpired.

Statuses distinguish `blocked` prerequisites, `waiting` for more observations,
`action_required` when known due operations are absent from an empty plan, and
`ready` to execute supplied operations. `required_operations_not_in_inputs`
exposes other known due forecasts/missed origins/outcomes even when an explicit
partial plan is ready. A completed cycle means its listed operations were
recorded; inspect `required_operations_remaining` and `cohort` before claiming
current cohort completeness. It never certifies the final planned cohort.

A `forecast` operation can issue only on today's closed, scheduled origin using
causal inputs. It cannot backfill a missed origin. If issuance failed, explicitly
account for it instead:

```json
{
  "kind": "missed",
  "data": "MISSED-DATE/batch-ending-at-missed-origin.json",
  "artifact_root": "MISSED-DATE",
  "reason": "Actual documented reason the forecast was not issued"
}
```

The deterministic first-origin/every-30-session schedule is enforced by the
unchanged core. Missed issuance remains visible and prevents a complete-cohort
validation claim. Recording it does not make a replacement forecast or allow an
outcome for an unissued forecast. `outcome` requires a previously issued origin
and its complete, matured 30-session target. All baselines stay on identical
observations. Core source, calendar, vintage, timing and overwrite guards run
again at each append.

For unattended operation, an authorized local scheduler may invoke `ready`/`run`
against a newly prepared immutable inputs manifest. This change does not install
a scheduler, collector, Render job or notification sender. A collector must
produce genuine reconciled evidence before an operation is executable. Monitor
exit code 2 and JSON reports for blocked/partial/action-required cycles; there is
no automatic forecast, missed-event inference, winner selection or promotion.

## Idempotency and recovery

Every cycle has a stable identity derived from registration, runner implementation,
manifest, witness/batch file hashes and explicit operations. Current time and the
observed ledger head are deliberately excluded, so partial progress does not
change its identity. An exclusive sealed intent is stored **before any event
mutation** under:

`.runtime/prospective/baselines-v1/cycles/<cycle-id>/`

Each successful event receives an exclusive `step-NNNN.json`; attempts and failures
are retained; `completed.json` is exclusively created after completion. Rerunning
identical inputs reconciles exact existing event identities instead of writing
duplicates. If a process appended an event but failed before writing its step
receipt, a retry can recover that receipt even after the origin date. It reuses
the original issuance event; it cannot create a late forecast.

A conflicting batch, changed reason, altered audit seal, changed frozen core or
changed input file during execution blocks progress. Preserve the partial cycle
and evidence. Do not delete the run, reset its ledger or modify input files to
get a clean result. Normal errors release locks. If a hard process kill leaves
`.cycle.lock` or the core `.writer.lock`, first establish that no writer remains,
inspect the intent and ledger with an independent operator, then reconcile the
stale lock before retrying. The runner deliberately does not remove an
unexplained lock automatically. A partial/invalid JSON event also needs review;
it must not be silently erased or overwritten.

Completed-cycle results are historical audit receipts. A replay checks that their
event identities remain in the ledger; it does not reinterpret their recorded
head as the current head or re-evaluate prices. Run a new `ready` check for current
operations. No scores, confidence improvement or automatic portfolio changes are
inferred from a cycle's operational success.

## Checks

```bash
python -m pytest -q tests/test_prospective_cycle.py tests/test_prospective.py \
  tests/test_data_reconciliation.py tests/test_forecast_followup_cli.py
```

Tests use explicitly synthetic fixture evidence and injected clocks only inside
tests. Production CLI has no clock override. They check unregistered/missing
prerequisites, witness ordering, source/calendar/path guards, unavailable/early
outcomes, overdue issuance, missed-event accounting, partial append/audit recovery,
idempotent completed cycles, unknown/disconnected calendars and preservation of
core freeze and portfolio safeguards. They establish implementation behavior,
not real forecast performance.
