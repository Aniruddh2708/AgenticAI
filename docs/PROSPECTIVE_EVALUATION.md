# Prospective forecasting: registration and observation workflow

Implemented on 15 October 2026. **No new market observations have been collected,
no prospective experiment is registered, and no new forecasting score exists.**
The original 2019–2020 and follow-up 2024–2025 evaluations remain spent. This
workflow does not rerun them, tune against them, change their masks, or rename
historical files to claim a fresh test.

## What this closes and what remains blocked

`scripts/prospective.py` provides registration, causal forecast issuance, explicit missed-origin accounting, matured
outcome ingestion and descriptive monitoring. Registration freezes protocol,
baseline parameters, calibration radii, regime thresholds, operator review,
source reconciliation, implementation hashes and timestamp. Exclusive creation
refuses overwrites; hash-chained, separately created events detect mutations and
missing/reordered events. A writer lock refuses concurrent appends. This is
overwrite refusal and local integrity checking, not proof against a malicious
rewrite or truncation of the complete ledger; that requires an independently
archived witness. Neither the hashes nor a local timestamp attest origin timing.

**Real registration fails closed until independent data verification passes.**
It requires the F1 price-reconciliation report and actual hashed price, reference,
calendar and corporate-action artifacts, together with a separate operator review
of rights and the point-in-time universe. A manually entered approval flag is
an attestation, not independent verification. File hashes establish identity,
not accuracy, rights, independence or a complete exchange calendar. The session
prices and dates must exactly match the normalized rows/calendar fingerprinted
by the passed reconciliation report; attaching an unrelated report is rejected.

The existing retrospective Yahoo archive does not satisfy this requirement.
Do not mark its unresolved review passed to get the registration command to run.
An unavailable approved feed is a dependency, not a reason to generate outcomes
or invent prices. The CLI performs no network downloads and no fallback.

Local files and the system clock do not provide an independent timestamp or a
cryptographically indestructible record. Archive the registration hash with an
independent timestamp witness **before the first origin**, retain off-machine
copies, and archive each ledger head. Preserve interrupted ledgers; investigate a
leftover `.writer.lock` rather than deleting a run to start it over. A code fix
that changes the frozen implementation closes the old study; review/register a
new study for subsequent dates. Do not call a renamed directory an independent
evaluation of dates already observed.

## Frozen design

The initial protocol is [data/prospective_protocol.json](../data/prospective_protocol.json).
It is a **template**, not a registration. It currently proposes origins from
16 October 2026 through 31 December 2030. If prerequisites finish later, move
`origin_start` into the future **before registration**; same-day or earlier
registration is refused. Both spent periods are explicitly excluded, including
when a caller tries a different run directory. Universe changes need an explicit
point-in-time review and apply only before registration.

- Fit prior-up probability and mean adjusted return on complete, non-overlapping,
  matured 30-session development targets in 2010–2020. Reuse of spent 2019–2020
  here is disclosed development, never new evaluation.
- Calibrate separate absolute-residual intervals for each security and each
  baseline on the identical 2021–2023 calibration origins. The requested 90%
  finite rank must be attainable; sparse calibration is rejected.
- Keep three declared candidates: prior/mean (default), constant 50%/zero return,
  and always-up/zero return. No feature model, hyperparameter search, post-result
  winner, evaluation-outcome refitting or automatic portfolio admission exists.
- Evaluate adjusted total returns over **30 complete independently reconciled
  exchange sessions**. This stricter prospective target does not change the old
  vendor-row target or alter the spent historical results.
- Require every security on every session. Missing prices, unverified calendars,
  source lineage changes and inconsistent origin prices are unavailable inputs,
  not silently dropped rows or filled prices. All baselines and intervals use
  exactly the same security/origin/target observations.
- Issue forecasts after the verified origin close, on that session's local
  Asia/Kolkata date, after registration. Use at least 20 past returns for the
  predeclared causal regime label. The first origin is the first verified session on or after the registered
  start; subsequent origins are exactly every 30 verified sessions. Delays and
  skips are rejected. Record an issuance failure with `missed` before proceeding
  to the next scheduled origin; never backfill that forecast. A missed origin
  remains visible and prevents a complete-cohort validation claim.
- Freeze each security's calm/elevated threshold at the development median of
  past-20-session log-return volatility. Future regime labels read only prices
  available at issuance; they do not select favorable evaluation windows.

The protocol freezes Brier, return MAE, marginal coverage, interval width and
proper interval score; same-origin paired comparisons use all declared baselines.
For lower-is-better Brier/MAE and interval score, the declared tolerances require
a paired upper improvement bound below zero; allowed coverage shortfall is five
percentage points from nominal 90%. These are review criteria, **not an automatic
admission gate or a promise that the next study will pass**. Coverage must always
be read with width and interval score. No conditional-coverage guarantee is
asserted.

Before uncertainty is reported, require **24 non-overlapping matured origins per
security, eight calendar quarters, and at least six origins in each of both
causally defined regimes for each security**. More stocks on the same day do not
replace time blocks. This likely requires years of observation. The minimum is a
planning floor, not a power calculation or proof that all future regimes are
represented. If one regime never appears, uncertainty remains unavailable;
changing that requirement after seeing data creates a different exploratory study.

When those minima are met, report approximate paired shared-quarter 95% bootstrap
intervals, sampling the securities jointly, with 2,000 draws and seed 2708. Also
report metric uncertainty, security, calendar-quarter and regime breakdowns.
Temporal dependence across quarter boundaries can remain. The cohort table separates issued forecasts, recorded outcomes, known-matured
but missing outcomes, pending origins whose maturity is not established by the
ingested verified calendar, and explicitly missed scheduled origins. Known-matured
missing outcomes or any missed issuance withhold uncertainty regardless of row
count. A local clock cannot infer exchange sessions that have not been supplied.
Before those minima, report raw descriptive counts/metrics and explicitly withhold confidence bounds.
`score` can be run for operational monitoring; **repeatedly viewed results are
interim/descriptive, never repeatedly untouched tests**. The returned `criteria_assessment` is explicitly withheld/interim and lists the
planned thresholds rather than silently treating them as passed. There is no
automatic significance-based stopping, candidate change or promotion. The preregistered
observation end remains fixed; a later confirmatory study needs a separately
reviewed plan, not reinterpretation of monitored data as unviewed.

At the fixed endpoint, an independent final reviewer must first wait for all
predeclared origins through `origin_end` to mature, retain missed issuance dates
and deviations, confirm no pending outcomes, and archive the witnessed ledger
head. The reviewer then checks minimum origin/quarter/regime support and the
planned criteria against **each** declared baseline: prior/mean paired Brier
and MAE upper bounds strictly below zero; marginal coverage lower bound at least
85%; paired interval-score upper bound at most zero. Width and every subgroup
remain visible. Insufficient support or a failed criterion stays inconclusive
or failed, without a replacement endpoint, security mask, candidate or interval
method. No significance-based early stop is provided. Monitoring history and
any temporal dependence/rights/source deviations accompany that review. Even a
successful research review cannot automatically promote a portfolio policy;
personalized effectiveness and safety require their own evaluation.

## Input contract

The F1 reconciliation report has `schema_version: 1`,
`kind: "price_reconciliation"`, `status: "passed"`, matching securities,
`exchange_timezone: "Asia/Kolkata"`, `price_basis: "split_dividend_adjusted"`, and
`currency: "INR"`. Its source/reference providers and lineage must be distinct
and present. Canonical provider identities and effective upstream lineage are
rechecked with the F1 rules, including inferred Yahoo ancestry; all three
independent price/calendar/action checks must explicitly be true. A `passed`
label alone cannot bypass those checks. Every local artifact hash is checked
again using the F1 reader. Artifact paths must be relative to `--artifact-root`;
absolute paths, traversal and symlinks escaping that root are rejected, as are
missing files and invalid CSV/Parquet structure. Every new session batch
needs a passed report for its own complete input scope from the same registered
provider/lineage pair. A historical pass does not verify later observations.

A data batch JSON embeds that report and contains `calendar_dates`, a sorted list
of independently verified session dates, plus `sessions` of this form:

```json
{
  "date": "2026-10-16",
  "close_at": "2026-10-16T10:00:00+00:00",
  "observed_at": "2026-10-16T10:01:00+00:00",
  "prices": {
    "HDFCBANK.NS": 100.0,
    "INFY.NS": 100.0,
    "ITC.NS": 100.0,
    "RELIANCE.NS": 100.0,
    "TCS.NS": 100.0
  }
}
```

**The numbers and dates above are format fixtures, not collected prices or
forecasts.** `close_at` must be the true verified session close, including any
special sessions; it is not universally assumed to be 15:30. `observed_at` must
follow the close and precede ingestion. The price rows must equal the report's
`verified_rows_sha256` and the date list its `verified_calendar_dates_sha256`.
Those bind reviewed inputs; they do not independently prove an observation time.
Keep the provider's timestamped raw observations as evidence. Session close and
observation timestamps remain operator/provider attestations: the F1 calendar
fingerprint binds session dates, not independently authenticated close-time events.
Do not claim the timestamp checks establish the true exchange close by themselves.

Registration data must end by 2023-12-31 and contain sufficient development and
calibration sessions. A forecast batch ends at its current origin and contains
at least 21 sessions. Its first batch must start at/before the registered start
boundary to establish the first scheduled session; later batches include the
previous planned origin so the exact 30-session cadence is checked.

An outcome batch contains the same **origin date and session close plus exactly
30 later verified sessions**, all independently reconciled in **one outcome
adjustment vintage**. Both sources must document the identical vintage, covering
the batch end and no later than ingestion; it cannot precede the issuance vintage.
Origin adjusted prices may legitimately be restated after dividends/splits. The
return therefore uses `outcome_target_adjusted / outcome_origin_adjusted - 1`,
never a new adjusted numerator divided by a frozen older-vintage denominator.
The immutable issuance event remains unchanged; the outcome separately stores
its origin and target snapshots, both vintage dates and origin adjustment factors.
Changed origin prices without a changed adjustment vintage are rejected. All
source declaration metadata besides the explicitly dated vintage remains fixed.

For example, a two-for-one split can restate an issuance price of 100 to an
outcome-vintage origin of 50. A target of 50 means 0% total return, not -50%. A
five-unit dividend can reduce a price from 100 to 95; outcome-vintage origin and
target both 95 mean 0% total return, not -5%. With dividend reinvestment at 95
and later recovery to 100, the same-vintage ratio is `100 / 95 - 1` (5.263%).
These are arithmetic fixtures, not collected prices or scored forecasts.

All 30 target sessions must have closed and been observed before ingestion. The
first future session must close after forecast issuance. An outcome cannot be
ingested without an earlier forecast, ingested early, or ingested twice.

The separate review JSON needs `status: "reviewed_approved"`, a timezone-aware
`review_completed_at`, `reviewer`, exact `verified_securities`, and nonempty
`rights_evidence`, `universe_evidence`, `calendar_evidence` and
`corporate_actions_evidence`. Supply genuine review/evidence references; this
repository does not include a fictitious approved attestation.

## Commands after the prerequisites actually pass

These are concrete commands for **new, authorized, independently reconciled
inputs**; the files are not claimed to exist yet:

```bash
python scripts/prospective.py register \
  --run-dir .runtime/prospective/baselines-v1 \
  --protocol data/prospective_protocol.json \
  --data /authorized-data/development-through-2023.json \
  --review /authorized-data/independent-review.json \
  --artifact-root /authorized-data

python scripts/prospective.py forecast \
  --run-dir .runtime/prospective/baselines-v1 \
  --data /authorized-data/closed-origin-batch.json \
  --artifact-root /authorized-data

# If a scheduled issuance was missed, account for it without inventing a forecast:
python scripts/prospective.py missed \
  --run-dir .runtime/prospective/baselines-v1 \
  --data /authorized-data/batch-ending-at-missed-origin.json \
  --reason "Collector outage; forecast was not issued" \
  --artifact-root /authorized-data

python scripts/prospective.py outcome \
  --run-dir .runtime/prospective/baselines-v1 \
  --origin YYYY-MM-DD \
  --data /authorized-data/origin-plus-thirty-closed-sessions.json \
  --artifact-root /authorized-data

python scripts/prospective.py score \
  --run-dir .runtime/prospective/baselines-v1 \
  --output .runtime/prospective/baselines-v1/interim-YYYY-MM-DD.json
```

`--output` exclusively creates a report and refuses overwrite. No CLI clock or
backdating option exists. Tests inject time only in explicit unit fixtures.

Run the fixture checks with:

```bash
python -m pytest -q tests/test_prospective.py
```

These checks cover changed registration/events/artifacts, source/provenance and
calendar failures, spent/past-period origins, future observations, sparse support,
identical-origin baselines, duplicate/overlapping forecasts, unavailable or early
outcomes, immutable issuance records with same-vintage corporate-action returns,
missed issuance and missing matured-outcome accounting and withholding unstable uncertainty. Synthetic
fixtures test implementation behavior and never count as improved market scores.
