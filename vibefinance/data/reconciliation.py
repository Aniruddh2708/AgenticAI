"""Read-only, scoped reconciliation of locally supplied historical evidence.

This checks declared evidence; a matching file is not a certification of a
provider, license, point-in-time universe, or future forecasting performance.
No downloads, inferred holidays, adjustment repairs, or price fills occur here.
"""
from datetime import date
import csv
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse

import numpy as np
import pandas as pd


class ReconciliationError(ValueError):
    """Invalid input carrying a stable machine-readable failure code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _require(condition, code, message):
    if not condition:
        raise ReconciliationError(code, message)


def _day(value):
    _require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
             "invalid_date", "Scope dates must be ISO YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ReconciliationError("invalid_date", "Invalid calendar date") from exc


def _dates(series):
    # Preserve the local daily label, including midnight Asia/Kolkata Parquet
    # timestamps. Reject intraday values instead of silently truncating them.
    result = []
    for value in series:
        if isinstance(value, str):
            _require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T]00:00:00(?:\+\d{2}:\d{2})?)?", value)),
                     "invalid_date", "Evidence dates must be unambiguous daily ISO labels")
        try:
            stamp = pd.Timestamp(value)
        except (TypeError, ValueError) as exc:
            raise ReconciliationError("invalid_date", "Unparseable daily date") from exc
        _require(not pd.isna(stamp) and stamp == stamp.normalize(), "invalid_date",
                 "Missing or intraday evidence date")
        result.append(stamp.date().isoformat())
    return pd.Series(result, index=series.index, dtype="string")


def _canonical(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _identity(spec):
    _require(isinstance(spec, dict), "missing_provenance", "Evidence metadata must be an object")
    for key in ("provider", "source_url", "lineage_url", "license", "license_url"):
        _require(isinstance(spec.get(key), str) and bool(spec[key].strip()),
                 "missing_provenance", f"Evidence requires explicit {key}")
    for key in ("source_url", "lineage_url", "license_url"):
        url = urlparse(spec[key])
        _require(url.scheme == "https" and url.hostname and not url.username and not url.password,
                 "invalid_provenance_url", "Evidence URLs require HTTPS without embedded credentials")
    _require(spec.get("authorized_use") in {"noncommercial_research", "commercial"},
             "missing_rights", "Evidence requires declared authorized_use")
    _require(isinstance(spec.get("lineage"), list) and spec["lineage"] and
             all(isinstance(x, str) and x.strip() for x in spec["lineage"]),
             "missing_lineage", "Evidence requires nonempty upstream lineage identities")
    lineage = {_canonical(x) for x in spec["lineage"]}
    _require(all(lineage), "missing_lineage", "Lineage identities require letters or digits")
    description = " ".join(str(spec.get(key, "")) for key in
                           ("provider", "source_url", "lineage_url"))
    if re.search(r"yahoo|yfinance", description, re.IGNORECASE) or any(
            "yahoo" in x or "yfinance" in x for x in lineage):
        lineage.add("yahoofinance")
    return lineage


def _read_artifact(spec, base, role, report, ticker=None):
    name = spec.get("path")
    _require(isinstance(name, str) and name and not Path(name).is_absolute() and
             ".." not in Path(name).parts, "invalid_path", "Artifact paths must stay within the manifest directory")
    path = (base / name).resolve()
    _require(path.is_relative_to(base), "invalid_path", "Artifact symlink leaves manifest directory")
    expected = spec.get("sha256")
    _require(isinstance(expected, str) and bool(re.fullmatch(r"[0-9a-f]{64}", expected)),
             "invalid_hash", "Every artifact requires its SHA-256")
    _require(path.is_file(), "missing_artifact", f"Missing {role} artifact: {name}")
    _require(hashlib.sha256(path.read_bytes()).hexdigest() == expected,
             "checksum_mismatch", f"Checksum mismatch in {role}: {name}")
    _require(path.suffix.lower() in {".csv", ".parquet"}, "unsupported_format", "Use CSV or Parquet artifacts")
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle), [])
        _require(header and len(set(header)) == len(header), "duplicate_columns", "CSV headers must be nonempty and unique")
        frame = pd.read_csv(path)
    else:
        frame = pd.read_parquet(path)
    _require(not frame.columns.duplicated().any(), "duplicate_columns", "Artifact columns must be unique")
    report["artifacts"].append({"role": role, "path": name, "sha256": expected,
                                **({"ticker": ticker} if ticker is not None else {})})
    return frame


def _scoped(frame, date_column, start, end):
    _require(date_column in frame, "missing_columns", f"Missing date column: {date_column}")
    frame = frame.copy()
    frame["date"] = _dates(frame[date_column])
    return frame.loc[(frame.date >= start) & (frame.date <= end)].copy()


def _numbers(series, name, positive=False):
    _require(not any(isinstance(value, (bool, np.bool_)) for value in series),
             "invalid_numeric", f"{name} cannot contain boolean values")
    try:
        values = pd.to_numeric(series, errors="raise").to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ReconciliationError("invalid_numeric", f"Invalid numeric {name}") from exc
    _require(np.isfinite(values).all() and (values > 0 if positive else values >= 0).all(),
             "invalid_numeric", f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    return values


def _price_frames(spec, base, role, manifest, report):
    securities = manifest["securities"]
    files = spec.get("files", [])
    _require(isinstance(files, list) and len(files) == len(securities) and
             {x.get("ticker") for x in files} == set(securities),
             "universe_mismatch", "Price files must cover the exact declared securities once")
    frames = {}
    for artifact in files:
        ticker = artifact["ticker"]
        raw = _read_artifact(artifact, base, role, report, ticker)
        columns = artifact.get("columns", {})
        _require(all(isinstance(columns.get(k), str) and columns[k] in raw
                     for k in ("date", "price", "volume")),
                 "missing_columns", "Price artifacts require date, price and volume column mappings")
        frame = _scoped(raw, columns["date"], manifest["start"], manifest["end"])
        _require(len(frame) > 0, "empty_scope", f"No {ticker} prices inside requested scope")
        _require(not frame.date.duplicated().any(), "duplicate_dates", f"Duplicate daily price for {ticker}")
        _require(frame.date.is_monotonic_increasing, "unordered_dates", f"Unordered daily prices for {ticker}")
        frame["price"] = _numbers(frame[columns["price"]], "price", positive=True)
        frame["volume"] = _numbers(frame[columns["volume"]], "volume")
        frames[ticker] = frame[["date", "price", "volume"]].set_index("date")
    return frames


def _finding(report, severity, code, message, **details):
    report["findings"].append({"severity": severity, "code": code, "message": message, **details})


def _independent(left, right):
    return not (_identity(left) & _identity(right)) and _canonical(left["provider"]) != _canonical(right["provider"])


def _calendar(spec, manifest, base, report):
    _identity(spec)
    _require(spec.get("exchange_timezone") == manifest["exchange_timezone"],
             "calendar_timezone", "Calendar must use the declared exchange timezone")
    _day(spec.get("coverage_start"))
    _day(spec.get("coverage_end"))
    _require(spec["coverage_start"] <= manifest["start"] and
             spec.get("coverage_end") >= manifest["end"], "calendar_scope", "Calendar must declare complete scoped coverage")
    raw = _read_artifact(spec, base, "calendar", report)
    frame = _scoped(raw, spec.get("date_column", "date"), manifest["start"], manifest["end"])
    _require(len(frame) > 0 and not frame.date.duplicated().any() and frame.date.is_monotonic_increasing,
             "invalid_calendar", "Calendar sessions must be nonempty, unique and chronological")
    # No weekday heuristics: an authorized Muhurat/weekend session belongs here.
    return set(frame.date)


def _actions(spec, manifest, base, role, report):
    _identity(spec)
    _day(spec.get("coverage_start"))
    _day(spec.get("coverage_end"))
    _require(spec["coverage_start"] <= manifest["start"] and
             spec.get("coverage_end") >= manifest["end"] and
             set(spec.get("securities", [])) == set(manifest["securities"]),
             "action_scope", "Action evidence must declare complete coverage for every scoped security")
    _require(spec.get("currency") == manifest["source"]["currency"], "action_currency", "Dividend action currency must match prices")
    raw = _read_artifact(spec, base, role, report)
    _require({"date", "ticker", "kind", "value"}.issubset(raw.columns),
             "missing_columns", "Actions require date,ticker,kind,value columns (header-only is explicit no-events)")
    frame = _scoped(raw, "date", manifest["start"], manifest["end"])
    _require(set(frame.ticker).issubset(manifest["securities"]) and
             set(frame.kind).issubset({"cash_dividend", "split"}),
             "invalid_action", "Unrecognized action type or security")
    _require(not frame.duplicated(["date", "ticker", "kind"]).any(),
             "duplicate_actions", "Duplicate corporate action")
    frame["value"] = _numbers(frame.value, "action value", positive=True)
    return frame.set_index(["date", "ticker", "kind"])["value"]


def _reconcile(manifest, base, report):
    _require(manifest.get("schema_version") == 1, "schema_version", "Use reconciliation manifest schema_version 1")
    start, end = _day(manifest.get("start")), _day(manifest.get("end"))
    _require(start <= end and end <= date.today(), "invalid_scope", "Scope must be ordered and historical")
    securities = manifest.get("securities")
    _require(isinstance(securities, list) and securities and
             all(isinstance(t, str) and t.strip() for t in securities) and len(set(securities)) == len(securities),
             "invalid_universe", "Declare unique nonempty securities")
    _require(manifest.get("exchange_timezone") == "Asia/Kolkata", "invalid_timezone", "This NSE audit requires Asia/Kolkata daily session labels")
    for key in ("absolute_tolerance", "relative_tolerance"):
        _require(type(manifest.get(key)) in {float, int} and np.isfinite(manifest[key]) and manifest[key] >= 0,
                 "invalid_tolerance", "Declare finite nonnegative absolute/relative price tolerances before comparison")
    stale = manifest.get("stale_run_sessions")
    _require(type(stale) is int and stale >= 2, "invalid_stale_rule", "Declare stale_run_sessions >= 2")
    source, reference = manifest.get("source", {}), manifest.get("reference", {})
    _identity(source)
    _identity(reference)
    basis = source.get("price_basis")
    _require(basis in {"raw", "split_adjusted", "split_dividend_adjusted"} and
             basis == reference.get("price_basis"), "incompatible_basis", "Compare explicitly equivalent raw/adjusted price bases only; no automatic adjustment")
    _require(isinstance(source.get("currency"), str) and re.fullmatch(r"[A-Z]{3}", source["currency"]) and
             source["currency"] == reference.get("currency"), "incompatible_currency", "Declare identical three-letter price currencies")
    for spec in (source, reference):
        _require(isinstance(spec.get("adjustment_method"), str) and spec["adjustment_method"].strip(),
                 "missing_adjustment_method", "Document adjustment method, including 'none' for raw")
        if basis != "raw":
            vintage = _day(spec.get("adjustment_as_of"))
            _require(end <= vintage <= date.today(), "adjustment_vintage_scope",
                     "Adjustment vintage must cover the entire scoped period and cannot be in the future")
    _require(basis == "raw" or source["adjustment_as_of"] == reference["adjustment_as_of"],
             "adjustment_vintage", "Adjusted comparisons require the same explicitly documented adjustment vintage")
    report["scope"] = {key: manifest[key] for key in ("start", "end", "securities", "exchange_timezone")}
    report["scope"].update(price_basis=basis, currency=source["currency"])
    report["sources"] = {role: {k: spec[k] for k in
        ("provider", "lineage", "source_url", "lineage_url", "license", "license_url", "authorized_use", "price_basis", "currency", "adjustment_method")}
        for role, spec in (("source", source), ("reference", reference))}
    for role, spec in (("source", source), ("reference", reference)):
        report["sources"][role]["effective_lineage"] = sorted(_identity(spec))
        if basis != "raw":
            report["sources"][role]["adjustment_as_of"] = spec["adjustment_as_of"]
    report["protocol"] = {key: manifest[key] for key in ("absolute_tolerance", "relative_tolerance", "stale_run_sessions")}
    report["checks"]["independent_price_lineage"] = _independent(source, reference)
    if not report["checks"]["independent_price_lineage"]:
        _finding(report, "error", "same_lineage", "Reference shares primary upstream lineage; another Yahoo mirror is not independent proof")
    left = _price_frames(source, base, "source_prices", manifest, report)
    right = _price_frames(reference, base, "reference_prices", manifest, report)
    source_hashes = {x["sha256"] for x in report["artifacts"] if x["role"] == "source_prices"}
    if any(x["sha256"] in source_hashes for x in report["artifacts"] if x["role"] == "reference_prices"):
        _finding(report, "error", "identical_source_artifact", "Reference reuses a source price artifact; hashes establish identity, not independent accuracy")
    calendar = None
    if manifest.get("calendar"):
        spec = manifest["calendar"]
        calendar = _calendar(spec, manifest, base, report)
        report["checks"]["independent_calendar_lineage"] = _independent(source, spec)
        if not report["checks"]["independent_calendar_lineage"]:
            _finding(report, "error", "calendar_lineage", "Calendar shares primary upstream price lineage")
    else:
        _finding(report, "warning", "missing_calendar", "Independent complete exchange-session evidence not supplied")
    report["comparisons"] = {}
    for ticker in securities:
        a, b = left[ticker], right[ticker]
        common = a.index.intersection(b.index)
        missing_ref, missing_source = sorted(set(a.index) - set(b.index)), sorted(set(b.index) - set(a.index))
        if missing_ref or missing_source:
            _finding(report, "error", "date_mismatch", "Provider daily labels differ; no observations filled or removed", ticker=ticker,
                     missing_from_reference=missing_ref, missing_from_source=missing_source)
        delta = (a.loc[common, "price"] - b.loc[common, "price"]).abs()
        tolerance = manifest["absolute_tolerance"] + manifest["relative_tolerance"] * b.loc[common, "price"].abs()
        mismatched = delta > tolerance
        differences = [{"date": day, "source": float(a.at[day, "price"]), "reference": float(b.at[day, "price"]),
                        "absolute_difference": float(delta.at[day])} for day in common[mismatched]]
        if differences:
            _finding(report, "error", "price_mismatch", "Same-date prices exceed the declared absolute + relative tolerance", ticker=ticker, differences=differences)
        detail = {"source_rows": len(a), "reference_rows": len(b), "common_dates": len(common),
                  "max_absolute_difference": float(delta.max()) if len(common) else None,
                  "mismatched_prices": len(differences)}
        for role, frame in (("source", a), ("reference", b)):
            zero = list(frame.index[frame.volume == 0])
            if zero:
                _finding(report, "error", "zero_volume", "Zero-volume vendor rows require explicit external resolution; retained without repair", ticker=ticker, role=role, dates=zero)
            repeats = frame.price.groupby(frame.price.ne(frame.price.shift()).cumsum()).transform("size")
            stale_dates = list(frame.index[repeats >= stale])
            if stale_dates:
                _finding(report, "error", "stale_price_run", "Unchanged price run requires human/external review; no fill or removal", ticker=ticker, role=role, dates=stale_dates)
            if calendar is not None:
                missing, extra = sorted(calendar - set(frame.index)), sorted(set(frame.index) - calendar)
                if missing or extra:
                    _finding(report, "error", "calendar_mismatch", "Observed dates differ from declared complete exchange sessions", ticker=ticker, role=role,
                             missing_sessions=missing, unexpected_sessions=extra)
                detail[f"{role}_missing_sessions"] = missing
                detail[f"{role}_unexpected_sessions"] = extra
        report["comparisons"][ticker] = detail
    if manifest.get("source_actions") and manifest.get("reference_actions"):
        a = _actions(manifest["source_actions"], manifest, base, "source_actions", report)
        b = _actions(manifest["reference_actions"], manifest, base, "reference_actions", report)
        report["checks"]["independent_action_lineage"] = _independent(source, manifest["reference_actions"])
        _require(bool(_identity(source) & _identity(manifest["source_actions"])),
                 "source_action_lineage", "Primary action evidence must document primary price-source lineage")
        _require(bool(_identity(reference) & _identity(manifest["reference_actions"])),
                 "reference_action_lineage", "Independent action evidence must document reference price-source lineage")
        if not report["checks"]["independent_action_lineage"]:
            _finding(report, "error", "action_lineage", "Reference corporate actions share primary upstream price lineage")
        action_differences = sorted(set(a.index) ^ set(b.index))
        common = a.index.intersection(b.index)
        action_differences += list(common[~np.isclose(a.loc[common], b.loc[common], rtol=0, atol=1e-8)])
        if action_differences:
            _finding(report, "error", "action_mismatch", "Declared split/dividend dates or values differ (absolute action tolerance 1e-8)", events=[list(x) for x in action_differences])
        report["checks"]["corporate_action_counts"] = {"source": len(a), "reference": len(b)}
    else:
        _finding(report, "warning", "missing_actions", "Both primary and independently sourced full-scope corporate-action records are required")
    if any(x["severity"] == "error" for x in report["findings"]):
        report["status"] = "failed"
    elif report["findings"]:
        report["status"] = "not_validated"
    else:
        report["status"] = "passed"
        report["verified_calendar_dates_sha256"] = _fingerprint(sorted(calendar))
        report["fingerprint_encoding"] = "UTF-8 json.dumps(sort_keys=True,separators=(',',':'),allow_nan=False)"
        if basis == "split_dividend_adjusted":
            # Bind future registration to the exact compared primary rows,
            # rather than accepting an unrelated passed evidence report.
            rows = [{"date": day, "ticker": ticker, "adjusted_close": float(frame.at[day, "price"])}
                    for ticker, frame in left.items() for day in frame.index]
            rows.sort(key=lambda row: (row["date"], row["ticker"]))
            report["verified_rows_sha256"] = _fingerprint(rows)


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def reconcile(manifest, base_directory):
    """Return a machine-readable audit; never mutate inputs or forecast artifacts.

    ``passed`` means only supplied scoped evidence agrees under declared rules.
    Independent human review of rights, universe and provider authenticity is
    still necessary before registering a new experiment.
    """
    report = {"schema_version": 1, "kind": "price_reconciliation", "status": "invalid",
              "input_manifest_sha256": None,
              "artifacts": [], "checks": {}, "findings": [], "limitations": [
                  "Provider/lineage/license declarations require independent human review; matching hashes establish identity only.",
                  "No price, volume, calendar session or action is imputed, repaired, dropped or rewritten.",
                  "Retrospective adjustment agreement does not establish point-in-time availability or forecast validity.",
                  "A scoped passed result does not validate the investment strategy or admit a predictive model."]}
    try:
        _require(isinstance(manifest, dict), "invalid_manifest", "Evidence manifest must be an object")
        report["input_manifest_sha256"] = _fingerprint(manifest)
        _reconcile(manifest, Path(base_directory).resolve(), report)
    except (ReconciliationError, ValueError, TypeError, KeyError, OSError) as exc:
        report["status"] = "invalid"
        _finding(report, "error", getattr(exc, "code", "invalid_input"), str(exc))
    return report
