# NSE raw-data acquisition and the remaining verification packet

This adapter makes authorized official daily exports usable by the local audit.
On **15 October 2026**, current runtime observations confirmed the NSE domains
were allowed and policy enforced. Two official, already-spent daily files were
then successfully acquired using normal TLS and proxy routing. The earlier proxy
`403 Forbidden` is historical; requests resumed only after that meaningful access
change. **No full data review was approved, and no fresh outcome, registered
prospective experiment or new forecasting score exists.** Unit tests use synthetic
format fixtures and mocked HTTP responses, separate from these real acquisitions.

Actual public terms were subsequently read. They restrict automated collection
and other uses; no further data requests or broad historical crawl were made.
Use an independently authorized feed/export or obtain the required permissions
and review before enabling an automated acquisition program. Network access is
no longer the same as the earlier blocker, and it is not a use-rights approval.

## What the two real files establish

Both official ZIPs and their extracted five-security CSVs remain private under
ignored `.runtime/exchange/`; no exchange raw file is committed or deployed.

| Spent date / format | Official source evidence | Narrow finding |
|---|---|---|
| 2020-12-31 / legacy | 2,017 source rows; ZIP SHA-256 `913177f995de74ace4fe2fe527481a6d7b85ef65231af306e8230301d3fe1d66` | All five required EQ records passed structural checks; TCS raw OHLC/volume match the pinned Yahoo row numerically, and INFY differs only at floating-point precision |
| 2025-03-18 / UDiFF | 3,043 source rows; ZIP SHA-256 `e311ccec13a8a0c800fa7edbfbebcb706cb344f518113c7736d1ab563437a12d` | Official records show positive traded volume and nonflat intraday ranges for all five stocks, independently confirming the four stale vendor placeholders described below |

For 2020-12-31, Yahoo-to-official OHLC ratios are approximately 0.46150 for
RELIANCE, 0.5 for HDFCBANK and 0.962915 for ITC, with almost constant ratios
across each stock's four fields. Their volume bases also differ. This supports
the need to reconcile retrospective corporate-action bases; it does not prove
the adjustment events, their completeness or their correctness. Do not compare
these nominally different prices as if their bases already matched. A numerical
match for TCS or INFY on one date likewise does not certify the entire series.

For 2025-03-18, the pinned Yahoo archive has zero volume and flat OHLC equal to
the previous close for RELIANCE, TCS, INFY and HDFCBANK. Official independent
records instead show actual trading for all four. ITC has positive volume in
both sources and matching volume. This confirms a security-specific vendor-data
defect, rather than a common exchange holiday. It is **exploratory source-quality
analysis on a spent period**. Old data, exclusion masks, targets, predictions and
scores were not repaired, realigned, refitted or rescored. There is no new F1 pass.

Private evidence directories are `.runtime/exchange/2020-12-31-live/` and
`.runtime/exchange/2025-03-18-live/`, each with `acquisition.json`, the unchanged
source ZIP, normalized raw files and `yahoo-comparison.json`. Both comparisons
record the limited scope. The complete calendar, corporate actions, equivalent
adjusted vintage, rights and universe review remain unresolved.

## Actual rights evidence

The official homepage linked to NSE's copyright and terms pages; same-host
redirects led to the public pages below, both retrieved HTTP 200 on 15 October 2026:

- [Copyright](https://www.nseindia.com/static/nse-copyright), SHA-256
  `9caa884afbb008f3d56f6377503c06b31189b7fd49d42bac4b697bb5dad99af1`.
  It permits personal, noncommercial or educational viewing, printing and
  downloading with accurate, unchanged content and full source acknowledgement,
  and excludes third-party copyrighted material from that permission.
- [Terms of Use](https://www.nseindia.com/static/nse-terms-of-use), SHA-256
  `ace927220d46b3cbe68711fd18d45626ecbc5a8da063cbd0c2c16ba5b78aac6a`.
  It prohibits systematic or automated collection, including scraping, mining,
  extraction and harvesting, and restricts modification/distribution and use in
  gaming, virtual trading or simulation. These restrictions must be considered
  together with the copyright page; a general research/commercial permission
  was not inferred.

Original HTML, extracted text and retrieval metadata are retained privately in
`.runtime/exchange/terms-live/`. This is recorded evidence for an actual source
review, not legal clearance or a fabricated operator approval. The app's existing
synthetic simulation did not receive these official files, and Render is unchanged.

## Local import first

Use an authorized original daily CSV or ZIP, the exact session date, and a new
ignored output directory. The existing input is read only.

```bash
.venv/bin/python scripts/acquire_exchange.py \
  --input /workspace/authorized/cm31DEC2020bhav.csv.zip \
  --date 2020-12-31 \
  --output-dir .runtime/exchange/2020-12-31
```

On Windows use `.venv\Scripts\python.exe` and an existing local input path.
`--sha256 ACTUAL_64_HEX_DIGEST` optionally checks a previously recorded source
identity. An observed checksum is always recorded. Computing a checksum yourself
does not prove authenticity or create a permission to use the data.

The adapter exclusively creates:

- `source.csv` or `source.zip`, preserving the original artifact bytes;
- one normalized CSV each for RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS and ITC.NS;
- `acquisition.json`, with source/member/output hashes, format, date, provenance,
  raw-price semantics, findings and explicit unresolved review fields.

Existing output directories are refused. Input/schema errors create no output
bundle. Completion metadata is written last; an interrupted filesystem write can
leave an incomplete directory, which must be preserved and inspected rather than
called a successful acquisition. The command prints machine-readable JSON,
returning zero for successful **raw import**, or 2 for failure. Zero is not an F1
reconciliation pass. Local imports explicitly record
`origin_evidence: "local_file_origin_unverified"`.

## Automated request requires separate permission evidence

The default local importer remains available for authorized files. Automated
`--fetch` now fails **before creating an HTTP client** unless `--permission-review`
identifies a separately supplied operator review and actual hashed permission
artifact. Missing or invalid review returns status/code `permission_required`
and exit 2. Network allowlisting or the public copyright page cannot substitute
for an actual automation authorization covering the date and NSE source.

The local JSON record must contain these fields. Values marked `REPLACE_...`
must come from a real completed review; no approved record was created here.

```json
{
  "schema_version": 1,
  "kind": "nse_automation_permission_review",
  "status": "reviewed_approved",
  "automation_authorized": true,
  "reviewed_by": "REPLACE_ACTUAL_OPERATOR_IDENTITY",
  "reviewed_at": "REPLACE_COMPLETED_ISO_TIMESTAMP_WITH_TIMEZONE",
  "authorization_reference": "REPLACE_ACTUAL_WRITTEN_PERMISSION_REFERENCE",
  "source_host": "nsearchives.nseindia.com",
  "authorized_dates": ["2020-12-31"],
  "evidence": {
    "path": "REPLACE_ACTUAL_PERMISSION_DOCUMENT.pdf",
    "sha256": "REPLACE_ACTUAL_64_HEX_DIGEST"
  }
}
```

The referenced nonempty artifact must exist inside the review directory and
match its hash; traversal and escaping symlinks fail. The reviewer timestamp
must already be completed. The requested date must appear explicitly in
`authorized_dates` and the source host must be the exact official archive host.
Wildcard approval is not accepted. The acquisition records the review and
evidence hashes while retaining `rights_status: "unreviewed"`: this is an
operator declaration gate, **not proof of genuine permission, legal clearance
or independent review authenticity**. The tool does not generate the review or
infer automation rights by interpreting a generic public page.

If real authorization exists, select the intended source format explicitly.
There is no automatic retry,
alternate-host fallback, redirect following, range crawler or inferred calendar.

```bash
.venv/bin/python scripts/acquire_exchange.py \
  --fetch --format legacy --date 2020-12-31 \
  --permission-review /workspace/authorized/nse-automation-review.json \
  --output-dir .runtime/exchange/2020-12-31
```

This requests exactly:

`https://nsearchives.nseindia.com/content/historical/EQUITIES/2020/DEC/cm31DEC2020bhav.csv.zip`

For an already-spent date using the new UDiFF archive layout:

```bash
.venv/bin/python scripts/acquire_exchange.py \
  --fetch --format udiff --date 2025-01-02 \
  --permission-review /workspace/authorized/nse-automation-review.json \
  --output-dir .runtime/exchange/2025-01-02
```

Its canonical path is:

`https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20250102_F_0000.csv.zip`

These are request recipes. The separate evidence above records the exact files
that were actually received; it does not imply other requested dates exist.
The correct format and source availability must be checked for each chosen date.
The tool does not guess a format-transition date or silently substitute a file
when a requested source returns unavailable.
These example requests require a review whose exact date scope includes the
chosen date. The two historical diagnostic acquisitions above predate this new
guard and remain preserved as actual observations; they were not retroactively
assigned an approval record.

Network fetching is intentionally limited to development/spent dates through
2025-12-31. No 2026+ outcomes can be downloaded by this command. Later local
imports are possible for deliberately supplied, already-closed dates, but they
are not a substitute for preregistration, causal observation timestamps, approved
rights or a separately reviewed prospective ingestion process. Do not download
new outcomes to make the old research appear fresh.

## Provider fields and validation

The legacy format requires `SYMBOL`, `SERIES`, `OPEN`, `HIGH`, `LOW`, `CLOSE`,
`TOTTRDQTY`, `TIMESTAMP`, and `ISIN`. Session labels must be `DD-MMM-YYYY` with
the provider's English month abbreviations. Its documented single trailing comma
is accepted. Duplicate or blank meaningful column names are rejected.

The UDiFF format requires `TckrSymb`, `SctySrs`, `OpnPric`, `HghPric`, `LwPric`,
**`ClsPric`**, `TtlTradgVol`, `TradDt`, `ISIN`, plus `BizDt`, `Sgmt`, `Src`, and
`FinInstrmTp`. Dates must be ISO `YYYY-MM-DD`; source/segment must be `NSE`/`CM`,
and selected instruments must be `STK`. Unknown schemas require review rather
than speculative column aliases.

Every source row must belong to the declared daily session. The five exact
symbols must each have exactly one `EQ` observation; a different series is not
substituted. Missing or duplicate selected observations fail. Prices must be
finite, positive and consistent with their OHLC bounds; volume must be a finite,
nonnegative integer within the supported signed-64-bit quantity range. A zero
volume is preserved and flagged; no price, row or session is filled or discarded.
Reported Indian ISINs must be structurally valid and distinct across the five
different equities. Their authenticity,
checksum and point-in-time symbol mapping still need independent review.

ZIP input must contain exactly one local CSV basename. Traversal paths, absolute
or Windows-drive paths, nested paths, links, encryption and multiple members are
rejected. Artifact input is bounded to 32 MiB, expanded CSV to 64 MiB and expansion
ratio to 100. The ZIP reader checks CRC; observed source and expanded-member
hashes are recorded. Neither bounds nor checksums authenticate a locally supplied
file's origin.

## Exact artifacts still needed

The existing local inventory contains the pinned third-party Yahoo Parquet files,
earlier Yahoo/yfinance-derived discovery exports, and the two scoped official files
recorded above. The Yahoo mirrors are not independent provider evidence. There is
still no complete authorized official price/calendar/action bundle or approved
operator review available locally.

For the five declared securities, obtain and retain the following without
rewriting the spent experiments:

| Evidence | Required scope and purpose | Still unresolved |
|---|---|---|
| Independent original prices | Authorized official/external observations for the declared audit window; 2010–2023 is needed for the current prospective development/calibration design | Two spent daily files acquired; they establish their own dates, not the complete historical window |
| Exchange sessions | Authoritative complete session lists over the same window, including closures, special/Muhurat sessions and source evidence | A weekday list or dates observed in bhavcopies cannot certify missing sessions |
| Session close evidence | Actual close times for future issuance/outcome sessions, including special schedules | F1 hashes dates, not authenticated close-time events |
| Primary corporate actions | Dated dividends/splits for the original provider with complete declared scope | Existing Yahoo lineage must be retained; authenticity and coverage remain review items |
| Independent corporate actions | Authorized dated records from an independent source over the same complete scope | Cash dividends, splits, bonus/rights/demerger treatment and completeness need review |
| Adjustment procedure/vintage | A separately reviewed procedure producing equivalent split-and-dividend-adjusted prices from both sources at one documented vintage | This adapter deliberately produces raw prices only |
| Source rights | Actual license/terms or permission evidence for each export and its intended noncommercial research use | Public terms were read and contain automation/use restrictions; no approval for the intended full pipeline was inferred |
| Universe review | Point-in-time security identity, symbol/ISIN mapping and rationale for the five survivors | Current convenience-universe limitations remain |
| Operator attestation | Independent review references, actual reviewer identity/completion time and approval only after evidence is checked | A machine-generated approval or invented reviewer is not acceptable |

An initial spent-date acquisition is useful for testing the source/format path
and investigating an already-known discrepancy. It is not enough to approve
eleven years of prices, three years of calibration, or a new prospective batch.

**Raw NSE closes and Yahoo adjusted closes are incompatible inputs.** The adapter
sets `price_basis: "raw"`, `adjustment_method: "none; no adjustments applied"`,
`rights_status: "unreviewed"`, and `status: "raw_only_not_reconciled"`.
Its per-security `files` entries can be used in a reviewed *raw-vs-raw* F1
comparison after adding real source/rights/calendar/action evidence. Do not relabel
the raw output `split_dividend_adjusted` to satisfy the prospective gate. Yahoo's
`Close` can already be split-adjusted; that column name does not make its basis
equivalent to the official nominal cash close.

Only after equivalent price construction and the entire evidence packet pass
[F1 reconciliation](DATA_VERIFICATION.md) may the separate human review and
[prospective workflow](PROSPECTIVE_EVALUATION.md) proceed. Corporate actions can
legitimately restate adjusted origins: outcome numerator and denominator must
come from the same independently reconciled outcome vintage, while original
issuance evidence stays preserved. Neither spent period is made fresh by new
exchange files, a new output directory or a calendar correction.

Fresh forecasts must be registered and independently timestamped before their
origin, then wait for 30 actual verified sessions to mature. Robust final
uncertainty also needs the predeclared origins/quarters/regimes. No script can
produce those genuinely future outcomes today or replace them with a better
simulation. Existing portfolio safeguards, Render behavior, lockfiles, research
results and failed-admission labels are unchanged by this standalone adapter.
