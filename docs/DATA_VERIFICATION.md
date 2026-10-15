# Independent historical-data reconciliation

The F1 verification tool is implemented. **The historical data itself is not yet
independently validated.** A normal TLS/proxy request to the official NSE archive
for the already-spent date 31 December 2020 failed with `ProxyError: 403 Forbidden`
on 15 October 2026. No exchange data was obtained, no credentials were requested,
and no uninspected evaluation outcomes were downloaded. Opening network access
would permit a request; it would not establish source rights or accuracy.

The existing pinned Yahoo/yfinance archive remains research-only. A second
GitHub/Yahoo mirror does not provide independent provider evidence. Its license
allows noncommercial research and personal use; a checksum is neither a license
grant nor an accuracy check. Keep both spent experiments and their reports intact.

## Run the local tool

Obtain an authorized independent export, the complete exchange-session calendar,
and primary/reference corporate-action records for a declared **already-spent or
development** period. Put these local files and the evidence manifest under an
ignored directory, such as `.runtime/reconciliation/`. No network access, private
password, API key, data subscription, or additional dependency is used by the tool.

```bash
.venv/bin/python scripts/reconcile_prices.py \
  --manifest .runtime/reconciliation/evidence.json \
  --output .runtime/reconciliation/reconciliation.json
```

On Windows use `.venv\Scripts\python.exe`. The command prints a JSON report and
returns zero only for `passed`; other results return 2. The output is exclusively
created, so an existing report is never overwritten. Source artifacts are read
only. Do not attach an unrelated passed report to a new dataset.

| Status | Meaning |
|---|---|
| `passed` | Supplied scoped prices, calendar and actions agree under the declared rules and lineage metadata; human evidence review is still required |
| `not_validated` | Price comparison produced no discrepancies, but independent calendar or paired action evidence is absent |
| `failed` | Valid evidence contains discrepancies, stale/zero-volume observations, or shared provider lineage |
| `invalid` | Artifact identity, metadata, scope, schema, dates, numbers, or file structure is invalid |

Reports expose stable finding codes, affected securities/dates, declared
tolerances, counts, artifact hashes and limitations. A `passed` result does not
certify provider identity, legal rights, point-in-time availability, index-universe
selection, complete source authenticity, or predictive performance.

## Evidence manifest

Use reconciliation schema version 1, separate from the original historical
loader's manifest. **Do not edit the frozen forecasting manifests** to add
verification metadata. Their generic `adjusted` flag is insufficient to assert
the exact currency, dividend treatment and adjustment vintage required here.

This structure illustrates a single-security scoped audit. Replace all
`REPLACE_...` values with actual evidence before running. It is deliberately not
a passed example and contains no invented historical prices. For a five-security
audit, list all five and provide exactly one file per ticker in each price source.

```json
{
  "schema_version": 1,
  "start": "2020-01-01",
  "end": "2020-12-31",
  "exchange_timezone": "Asia/Kolkata",
  "securities": ["TCS.NS"],
  "absolute_tolerance": 0.01,
  "relative_tolerance": 0.0001,
  "stale_run_sessions": 3,
  "source": {
    "provider": "Yahoo Finance via the pinned third-party archive",
    "lineage": ["yahoo_finance"],
    "source_url": "REPLACE_EXACT_PINNED_ARTIFACT_URL",
    "lineage_url": "REPLACE_FETCH_CODE_OR_PROVIDER_LINEAGE_URL",
    "license": "REPLACE_ACTUAL_LICENSE_AND_AUTHORIZATION",
    "license_url": "REPLACE_LICENSE_EVIDENCE_URL",
    "authorized_use": "noncommercial_research",
    "currency": "INR",
    "price_basis": "split_dividend_adjusted",
    "adjustment_method": "REPLACE_DOCUMENTED_VENDOR_METHOD_NOT_AN_INFERENCE",
    "adjustment_as_of": "REPLACE_YYYY-MM-DD",
    "files": [{
      "ticker": "TCS.NS",
      "path": "TCS_NS.parquet",
      "sha256": "REPLACE_64_CHARACTER_ACTUAL_SHA256",
      "columns": {"date": "Date", "price": "Adj Close", "volume": "Volume"}
    }]
  },
  "reference": {
    "provider": "REPLACE_AUTHORIZED_INDEPENDENT_PROVIDER",
    "lineage": ["REPLACE_ACTUAL_UPSTREAM_NOT_YAHOO"],
    "source_url": "REPLACE_REFERENCE_EXPORT_OR_ORIGINAL_SOURCE_URL",
    "lineage_url": "REPLACE_REFERENCE_METHOD_OR_LINEAGE_URL",
    "license": "REPLACE_ACTUAL_LICENSE_AND_AUTHORIZATION",
    "license_url": "REPLACE_LICENSE_EVIDENCE_URL",
    "authorized_use": "noncommercial_research",
    "currency": "INR",
    "price_basis": "split_dividend_adjusted",
    "adjustment_method": "REPLACE_DOCUMENTED_PROVIDER_METHOD",
    "adjustment_as_of": "REPLACE_SAME_DOCUMENTED_ADJUSTMENT_VINTAGE",
    "files": [{
      "ticker": "TCS.NS",
      "path": "independent-tcs.csv",
      "sha256": "REPLACE_64_CHARACTER_ACTUAL_SHA256",
      "columns": {"date": "date", "price": "adjusted_close", "volume": "volume"}
    }]
  },
  "calendar": {
    "provider": "REPLACE_EXCHANGE_OR_AUTHORIZED_CALENDAR_PROVIDER",
    "lineage": ["REPLACE_INDEPENDENT_CALENDAR_UPSTREAM"],
    "source_url": "REPLACE_EXACT_CALENDAR_SOURCE_URL",
    "lineage_url": "REPLACE_CALENDAR_METHOD_URL",
    "license": "REPLACE_ACTUAL_LICENSE_AND_AUTHORIZATION",
    "license_url": "REPLACE_LICENSE_EVIDENCE_URL",
    "authorized_use": "noncommercial_research",
    "exchange_timezone": "Asia/Kolkata",
    "coverage_start": "2020-01-01",
    "coverage_end": "2020-12-31",
    "path": "calendar.csv",
    "sha256": "REPLACE_64_CHARACTER_ACTUAL_SHA256",
    "date_column": "date"
  },
  "source_actions": {
    "provider": "REPLACE_PRIMARY_PROVIDER",
    "lineage": ["yahoo_finance"],
    "source_url": "REPLACE_PRIMARY_ACTION_SOURCE_URL",
    "lineage_url": "REPLACE_PRIMARY_ACTION_METHOD_URL",
    "license": "REPLACE_ACTUAL_LICENSE_AND_AUTHORIZATION",
    "license_url": "REPLACE_LICENSE_EVIDENCE_URL",
    "authorized_use": "noncommercial_research",
    "currency": "INR",
    "coverage_start": "2020-01-01",
    "coverage_end": "2020-12-31",
    "securities": ["TCS.NS"],
    "path": "primary-actions.csv",
    "sha256": "REPLACE_64_CHARACTER_ACTUAL_SHA256"
  },
  "reference_actions": {
    "provider": "REPLACE_INDEPENDENT_PROVIDER",
    "lineage": ["REPLACE_SAME_UPSTREAM_AS_REFERENCE_PRICES"],
    "source_url": "REPLACE_INDEPENDENT_ACTION_SOURCE_URL",
    "lineage_url": "REPLACE_INDEPENDENT_ACTION_METHOD_URL",
    "license": "REPLACE_ACTUAL_LICENSE_AND_AUTHORIZATION",
    "license_url": "REPLACE_LICENSE_EVIDENCE_URL",
    "authorized_use": "noncommercial_research",
    "currency": "INR",
    "coverage_start": "2020-01-01",
    "coverage_end": "2020-12-31",
    "securities": ["TCS.NS"],
    "path": "independent-actions.csv",
    "sha256": "REPLACE_64_CHARACTER_ACTUAL_SHA256"
  }
}
```

Compute each SHA-256 from the actual file, for example:

```bash
.venv/bin/python -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('.runtime/reconciliation/calendar.csv').read_bytes()).hexdigest())"
```

Relative paths must remain inside the manifest directory, including through
symlinks. CSV and Parquet are accepted; no source is fetched automatically.
Scope dates and CSV session labels use unambiguous ISO `YYYY-MM-DD`. Midnight
Parquet timestamps retain their local calendar label; intraday values are rejected.
Within the requested window, daily prices must be chronological, unique, finite
and positive; volume must be finite and nonnegative. Empty scopes, malformed dates,
duplicate headers and mismatched artifact hashes fail. Rows outside the explicit
window do not enter numeric comparisons or forecasts.

The calendar CSV contains **only documented trading-session dates**, one `date`
per row in chronological order. Include actual special/Muhurat sessions even on
weekends. Do not generate it using weekdays or infer closures from missing vendor
rows. `coverage_start`/`coverage_end` assert that the evidence is complete over
the requested interval; a human must verify that assertion against its source.

Action CSVs use `date,ticker,kind,value`, with one event per date/ticker/kind.
Kinds are `cash_dividend` (cash per share in the declared currency) or `split`
(new shares per old share). Values must be finite and positive. A header-only file
with complete declared coverage is an explicit assertion of no events; missing
files are not treated as no events. Primary action lineage must match primary
prices, and independent action lineage must match independent prices. Event dates,
types and values must agree; numeric values use absolute tolerance `1e-8`.

## Comparison rules and unresolved evidence

Declare the price basis as exactly `raw`, `split_adjusted`, or
`split_dividend_adjusted`. Both sources must use the same basis and currency.
Adjusted sources must document an identical adjustment-as-of vintage. Provider
definitions and cash-dividend conventions still need review. An official raw
exchange close is not automatically equivalent to Yahoo's split-adjusted close
or its dividend-adjusted close. The tool does not invent adjustment factors or
apply dividends/splits. Normalize an authorized reference through a separately
reviewed, frozen procedure if equivalent inputs are not already available.
The declared adjustment vintage must cover the end of the complete audit scope
and cannot be in the future. Both source entries retain `adjustment_as_of`,
`price_basis`, `currency`, `adjustment_method` and canonical `effective_lineage`
in the generated report. A later vintage does not imply a different upstream
provider; provider identity and adjustment vintage are separate evidence fields.

Retrospective adjusted prices can legitimately change after dividends or splits.
For prospective outcomes, retain the original issuance evidence unchanged and
independently reconcile a new snapshot containing **both the forecast origin and
the target date in the same new adjustment vintage**, with complete calendar and
paired corporate-action coverage across that whole interval. Construct the return
as `new_vintage_target / new_vintage_origin - 1`. Dividing a newly adjusted target
by an old-vintage issuance price mixes incompatible price bases. Requiring the
later adjusted origin to equal its old-vintage value would reject valid corporate
actions. A changed origin within an unchanged declared vintage still needs
resolution; do not silently relabel an unexplained vendor revision as a split.
Keep both reports, row fingerprints and their vintages for review. This procedure
does not authorize changing either spent historical experiment or its results.

Price matching is on identical dates and uses:

`abs(source - reference) <= absolute_tolerance + relative_tolerance * abs(reference)`

The sample tolerances and stale-run length above illustrate declarations, not
empirically selected thresholds. Set economically justified rules before looking
at discrepancies, retain the report, and document any later revision. Loosening
tolerances after inspection does not establish an independent confirmatory pass.

No unmatched date is filled. Zero-volume rows and unchanged-price runs at least
`stale_run_sessions` long are retained and reported as failures needing external
resolution. A stale flag is a conservative review trigger, not proof that an
unchanged market price is wrong. Both sources are compared against the independent
calendar, so shared vendor omissions cannot silently become expected sessions.
Volume levels are not compared as a split/turnover metric; only validity and
zero-volume observations are checked.

The current known 2014 zero-volume holiday placeholders, missing older Muhurat
observations and security-specific 18 March 2025 stale rows require this external
reconciliation. Do not overwrite old artifacts, retrospectively realign old
targets, or call a corrected spent-period analysis fresh. A discrepancy needs a
documented resolution and a new protocol, not a fabricated price or calendar fill.

## Handoff to prospective research

A passed report uses `schema_version: 1`, `kind: "price_reconciliation"`, exact
`scope` (`start`, `end`, `securities`, `exchange_timezone`, `price_basis`, `currency`),
source metadata, the input-manifest fingerprint and `artifacts` containing
`role`, local `path`, `sha256`, and per-price-file `ticker`. Required artifact
roles are `source_prices`, `reference_prices`, `calendar`, `source_actions`, and
`reference_actions`. Every artifact remains independently reviewable.

Only a passed split-and-dividend-adjusted report also includes
`verified_rows_sha256`: canonical JSON of primary `{date,ticker,adjusted_close}`
rows, with float prices, sorted by `(date,ticker)`. A passed report includes
`verified_calendar_dates_sha256`, the canonical sorted calendar date list. Both
use UTF-8 `json.dumps(sort_keys=True,separators=(',',':'),allow_nan=False)`.
The prospective workflow can bind its supplied sessions to these exact hashes.

An operator must separately approve source authenticity, rights, calendar/action
coverage and the universe; the reconciliation tool does not emit a
`reviewed_approved` attestation. Current absence of real independent evidence keeps
that gate closed. Unit fixtures test the machinery only and are never described
as verified market observations or new forecasting evidence.
