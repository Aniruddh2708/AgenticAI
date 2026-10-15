"""Evidence-gate tests use explicit fixtures, never investment-performance claims."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from vibefinance.data.reconciliation import reconcile


def _metadata(provider, lineage):
    return {"provider": provider, "lineage": [lineage],
            "source_url": f"https://{lineage}.example.org/download",
            "lineage_url": f"https://{lineage}.example.org/method",
            "license": "Synthetic unit fixture only, no real prices",
            "license_url": f"https://{lineage}.example.org/license",
            "authorized_use": "noncommercial_research"}


def _artifact(tmp_path, name, frame):
    path = tmp_path / name
    frame.to_csv(path, index=False)
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture
def evidence(tmp_path):
    dates = ["2020-11-13", "2020-11-14", "2020-11-17"]  # Declared special Saturday session.
    source = pd.DataFrame({"Date": dates, "Close": [100., 101., 102.], "Volume": [1000, 1100, 1200]})
    reference = pd.DataFrame({"date": dates, "close": [100., 101., 102.], "volume": [1000, 1100, 1200]})
    source_spec = {**_metadata("Primary fixture", "primary"), "currency": "INR", "price_basis": "split_dividend_adjusted",
                   "adjustment_method": "Synthetic fixture, no adjustment", "adjustment_as_of": "2020-12-31",
                   "files": [{"ticker": "TCS.NS", **_artifact(tmp_path, "source.csv", source),
                              "columns": {"date": "Date", "price": "Close", "volume": "Volume"}}]}
    reference_spec = {**_metadata("Independent fixture", "exchange"), "currency": "INR", "price_basis": "split_dividend_adjusted",
                      "adjustment_method": "Synthetic fixture, no adjustment", "adjustment_as_of": "2020-12-31",
                      "files": [{"ticker": "TCS.NS", **_artifact(tmp_path, "reference.csv", reference),
                                 "columns": {"date": "date", "price": "close", "volume": "volume"}}]}
    calendar = {**_metadata("Exchange fixture", "exchange"), **_artifact(tmp_path, "calendar.csv", pd.DataFrame({"date": dates})),
                "coverage_start": dates[0], "coverage_end": dates[-1], "exchange_timezone": "Asia/Kolkata"}
    actions = pd.DataFrame({"date": [dates[0]], "ticker": ["TCS.NS"], "kind": ["cash_dividend"], "value": [1.5]})
    source_actions = {**_metadata("Primary fixture", "primary"), **_artifact(tmp_path, "source-actions.csv", actions),
                      "coverage_start": dates[0], "coverage_end": dates[-1], "securities": ["TCS.NS"], "currency": "INR"}
    reference_actions = {**_metadata("Independent fixture", "exchange"), **_artifact(tmp_path, "reference-actions.csv", actions),
                         "coverage_start": dates[0], "coverage_end": dates[-1], "securities": ["TCS.NS"], "currency": "INR"}
    return {"schema_version": 1, "start": dates[0], "end": dates[-1], "exchange_timezone": "Asia/Kolkata",
            "securities": ["TCS.NS"], "absolute_tolerance": .01, "relative_tolerance": .0001,
            "stale_run_sessions": 3, "source": source_spec, "reference": reference_spec,
            "calendar": calendar, "source_actions": source_actions, "reference_actions": reference_actions}


def _change(tmp_path, artifact, change):
    path = tmp_path / artifact["path"]
    frame = pd.read_csv(path)
    changed = change(frame)
    (frame if changed is None else changed).to_csv(path, index=False)
    artifact["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def _codes(report):
    return {finding["code"] for finding in report["findings"]}


def test_independent_scoped_evidence_matches_without_mutating_files(tmp_path, evidence):
    original = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "passed"
    assert report["scope"]["price_basis"] == "split_dividend_adjusted"
    assert report["comparisons"]["TCS.NS"]["common_dates"] == 3
    assert report["checks"]["independent_price_lineage"]
    for role in ("source", "reference"):
        assert report["sources"][role]["adjustment_as_of"] == "2020-12-31"
        assert report["sources"][role]["price_basis"] == "split_dividend_adjusted"
        assert report["sources"][role]["currency"] == "INR"
        assert report["sources"][role]["adjustment_method"] == evidence[role]["adjustment_method"]
    assert {x["role"] for x in report["artifacts"]} == {
        "source_prices", "reference_prices", "calendar", "source_actions", "reference_actions"}
    assert all(path.read_bytes() == original[path.name] for path in tmp_path.iterdir())
    json.dumps(report, allow_nan=False)
    rows = [{"date": day, "ticker": "TCS.NS", "adjusted_close": value}
            for day, value in [("2020-11-13", 100.), ("2020-11-14", 101.), ("2020-11-17", 102.)]]
    fingerprint = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    assert report["verified_rows_sha256"] == fingerprint(rows)
    assert report["verified_calendar_dates_sha256"] == fingerprint([row["date"] for row in rows])


@pytest.mark.parametrize("mask", ["lineage", "provider", "url"])
def test_yahoo_mirrors_do_not_establish_independence(tmp_path, evidence, mask):
    evidence["source"]["lineage"] = ["yahoo_finance"]
    evidence["source_actions"]["lineage"] = ["yahoo_finance"]
    if mask == "lineage":
        evidence["reference"]["lineage"] = ["YFinance"]
    elif mask == "provider":
        evidence["reference"]["provider"] = "Different GitHub Yahoo archive"
    else:
        evidence["reference"]["source_url"] = "https://query1.finance.yahoo.com/download"
    evidence["reference_actions"]["lineage"] = evidence["reference"]["lineage"].copy()
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "failed"
    assert "same_lineage" in _codes(report)


def test_identical_price_artifact_not_accepted_as_independent(tmp_path, evidence):
    evidence["reference"]["files"] = copy.deepcopy(evidence["source"]["files"])
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "failed"
    assert "identical_source_artifact" in _codes(report)


def test_missing_calendar_actions_never_claims_validation(tmp_path, evidence):
    for key in ("calendar", "source_actions", "reference_actions"):
        evidence.pop(key)
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "not_validated"
    assert {"missing_calendar", "missing_actions"}.issubset(_codes(report))


def test_calendar_catches_missing_weekend_session_without_fabricated_fills(tmp_path, evidence):
    _change(tmp_path, evidence["source"]["files"][0], lambda frame: frame.drop(index=1))
    before = (tmp_path / "source.csv").read_bytes()
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "failed"
    assert {"date_mismatch", "calendar_mismatch"}.issubset(_codes(report))
    assert report["comparisons"]["TCS.NS"]["source_missing_sessions"] == ["2020-11-14"]
    assert report["comparisons"]["TCS.NS"]["source_rows"] == 2
    assert (tmp_path / "source.csv").read_bytes() == before


@pytest.mark.parametrize("defect", ["nan", "inf", "negative_price", "negative_volume", "duplicate", "unordered", "intraday", "ambiguous_date"])
def test_invalid_data_is_rejected_not_repaired(tmp_path, evidence, defect):
    def change(frame):
        if defect == "nan": frame.loc[1, "Close"] = np.nan
        elif defect == "inf": frame.loc[1, "Close"] = np.inf
        elif defect == "negative_price": frame.loc[1, "Close"] = -1
        elif defect == "negative_volume": frame.loc[1, "Volume"] = -1
        elif defect == "duplicate": frame.loc[1, "Date"] = frame.loc[0, "Date"]
        elif defect == "unordered": return frame.iloc[::-1]
        elif defect == "intraday": frame.loc[1, "Date"] = "2020-11-14 12:30:00"
        else: frame.loc[1, "Date"] = "14/11/2020"
    _change(tmp_path, evidence["source"]["files"][0], change)
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "invalid"
    assert len(report["findings"]) >= 1
    json.dumps(report, allow_nan=False)


def test_zero_volume_and_stale_prices_require_review_no_silent_filter(tmp_path, evidence):
    def change(frame):
        frame["Close"] = 100.
        frame.loc[1, "Volume"] = 0
    _change(tmp_path, evidence["source"]["files"][0], change)
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "failed"
    assert {"zero_volume", "stale_price_run", "price_mismatch"}.issubset(_codes(report))
    assert report["comparisons"]["TCS.NS"]["source_rows"] == 3


@pytest.mark.parametrize("defect,code", [("basis", "incompatible_basis"), ("vintage", "adjustment_vintage"),
    ("currency", "incompatible_currency"), ("license", "missing_provenance"), ("rights", "missing_rights"),
    ("hash", "checksum_mismatch"), ("scope", "calendar_scope"), ("path", "invalid_path")])
def test_metadata_and_identity_fail_closed(tmp_path, evidence, defect, code):
    if defect == "basis": evidence["reference"]["price_basis"] = "raw"
    elif defect == "vintage": evidence["reference"]["adjustment_as_of"] = "2021-12-31"
    elif defect == "currency": evidence["reference"]["currency"] = "USD"
    elif defect == "license": evidence["reference"].pop("license")
    elif defect == "rights": evidence["reference"]["authorized_use"] = "unknown"
    elif defect == "hash": evidence["reference"]["files"][0]["sha256"] = "0" * 64
    elif defect == "scope": evidence["calendar"]["coverage_end"] = "2020-11-14"
    else: evidence["source"]["files"][0]["path"] = "../source.csv"
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "invalid"
    assert code in _codes(report)


def test_declared_tolerance_applies_to_identical_dates(tmp_path, evidence):
    _change(tmp_path, evidence["reference"]["files"][0],
            lambda frame: frame.assign(close=frame.close + .015))
    assert reconcile(evidence, tmp_path)["status"] == "passed"  # .01 + .0001 * ~100.
    evidence["relative_tolerance"] = 0
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "failed"
    assert "price_mismatch" in _codes(report)


def test_corporate_action_disagreement_blocks_pass(tmp_path, evidence):
    _change(tmp_path, evidence["reference_actions"], lambda frame: frame.assign(value=3.))
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "failed"
    assert "action_mismatch" in _codes(report)


def test_header_only_action_evidence_is_explicit_no_events(tmp_path, evidence):
    for key in ("source_actions", "reference_actions"):
        _change(tmp_path, evidence[key], lambda frame: frame.iloc[:0])
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "passed"
    assert report["checks"]["corporate_action_counts"] == {"source": 0, "reference": 0}


def test_reference_action_lineage_cannot_be_unrelated(tmp_path, evidence):
    evidence["reference_actions"]["lineage"] = ["unrelated"]
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "invalid"
    assert "reference_action_lineage" in _codes(report)


def test_duplicate_csv_headers_rejected_before_pandas_renames_them(tmp_path, evidence):
    artifact = evidence["source"]["files"][0]
    path = tmp_path / artifact["path"]
    path.write_text("Date,Close,Volume,Close\n2020-11-13,100,1000,999\n")
    artifact["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "invalid"
    assert "duplicate_columns" in _codes(report)


@pytest.mark.parametrize("value", [[], None, {"schema_version": float("nan")}])
def test_programmatic_invalid_manifest_returns_failure(value, tmp_path):
    report = reconcile(value, tmp_path)
    assert report["status"] == "invalid"
    json.dumps(report, allow_nan=False)


def test_cli_writes_new_json_report_and_refuses_overwrite(tmp_path, evidence):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(evidence))
    output = tmp_path / "report.json"
    script = Path(__file__).resolve().parent.parent / "scripts/reconcile_prices.py"
    command = [sys.executable, str(script), "--manifest", str(manifest), "--output", str(output)]
    first = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stdout + first.stderr
    before = output.read_bytes()
    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert second.returncode == 2
    assert json.loads(second.stdout)["code"] == "output_not_created"
    assert output.read_bytes() == before


def test_cli_invalid_manifest_produces_machine_readable_failure(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"schema_version": NaN}')
    script = Path(__file__).resolve().parent.parent / "scripts/reconcile_prices.py"
    process = subprocess.run([sys.executable, str(script), "--manifest", str(manifest)],
                             capture_output=True, text=True, check=False)
    assert process.returncode == 2
    assert json.loads(process.stdout)["status"] == "invalid"


def test_disjoint_dates_report_missing_sessions_without_nonfinite_metrics(tmp_path, evidence):
    _change(tmp_path, evidence["source"]["files"][0], lambda frame: frame.iloc[:1])
    _change(tmp_path, evidence["reference"]["files"][0], lambda frame: frame.iloc[1:])
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "failed"
    assert report["comparisons"]["TCS.NS"]["common_dates"] == 0
    assert report["comparisons"]["TCS.NS"]["max_absolute_difference"] is None
    assert "verified_rows_sha256" not in report
    json.dumps(report, allow_nan=False)


def test_artifact_symlink_cannot_escape_manifest_directory(tmp_path, evidence):
    outside = tmp_path.parent / f"outside-{tmp_path.name}.csv"
    outside.write_text("Date,Close,Volume\n2020-11-13,100,1000\n")
    link = tmp_path / "escaped.csv"
    link.symlink_to(outside)
    evidence["source"]["files"][0].update(path=link.name,
        sha256=hashlib.sha256(outside.read_bytes()).hexdigest())
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "invalid"
    assert "invalid_path" in _codes(report)


def test_boolean_prices_are_not_numeric_market_prices(tmp_path, evidence):
    _change(tmp_path, evidence["source"]["files"][0], lambda frame: frame.assign(Close=True))
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "invalid"
    assert "invalid_numeric" in _codes(report)


def test_new_adjustment_vintage_keeps_lineage_identity_and_freezes_prior_report(tmp_path, evidence):
    old_report = reconcile(evidence, tmp_path)
    old_identity = json.dumps(old_report, sort_keys=True)
    # Fixture-only later restatement: both independent providers use one new
    # common adjustment vintage. Nothing mutates the prior evidence/report.
    for role in ("source", "reference"):
        evidence[role]["adjustment_as_of"] = "2021-01-31"
        column = evidence[role]["files"][0]["columns"]["price"]
        _change(tmp_path, evidence[role]["files"][0],
                lambda frame: frame.assign(**{column: frame[column] * .5}))
    new_report = reconcile(evidence, tmp_path)
    assert new_report["status"] == "passed"
    assert new_report["verified_rows_sha256"] != old_report["verified_rows_sha256"]
    assert new_report["verified_calendar_dates_sha256"] == old_report["verified_calendar_dates_sha256"]
    for role in ("source", "reference"):
        assert new_report["sources"][role]["adjustment_as_of"] == "2021-01-31"
        assert new_report["sources"][role]["effective_lineage"] == old_report["sources"][role]["effective_lineage"]
    assert json.dumps(old_report, sort_keys=True) == old_identity


@pytest.mark.parametrize("vintage", ["2020-11-13", "9999-12-31"])
def test_adjustment_vintage_must_cover_full_scope_without_future_claims(tmp_path, evidence, vintage):
    for role in ("source", "reference"):
        evidence[role]["adjustment_as_of"] = vintage
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "invalid"
    assert "adjustment_vintage_scope" in _codes(report)


def test_actions_must_cover_outcome_origin_and_target_in_one_snapshot(tmp_path, evidence):
    # A source action file reviewed only through the origin cannot certify a
    # later-vintage origin/target comparison whose horizon crosses new actions.
    evidence["source_actions"]["coverage_end"] = evidence["start"]
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "invalid"
    assert "action_scope" in _codes(report)
    assert "verified_rows_sha256" not in report


def test_real_reconciliation_report_binds_prospective_sessions_prices_and_calendar(tmp_path, evidence):
    from datetime import datetime, timezone
    from vibefinance.evaluation import prospective

    # Actual F1 report, not a manually authored passed-report fixture. This is
    # boundary validation only; the explicit synthetic prices are not research.
    report = reconcile(evidence, tmp_path)
    assert report["status"] == "passed"
    prices = pd.read_csv(tmp_path / evidence["source"]["files"][0]["path"])
    sessions = [{"date": row.Date, "close_at": f"{row.Date}T10:00:00+00:00",
                 "observed_at": "2020-12-31T11:00:00+00:00", "prices": {"TCS.NS": float(row.Close)}}
                for row in prices.itertuples(index=False)]
    days = [row["date"] for row in sessions]
    assert "2020-11-14" in days  # Declared Muhurat Saturday is retained.
    batch = {"sessions": sessions, "calendar_dates": days, "reconciliation": report}
    protocol = {"securities": ["TCS.NS"], "timezone": "Asia/Kolkata"}
    now = datetime(2026, 10, 15, 11, tzinfo=timezone.utc)
    assert prospective._sessions(batch, protocol, now, tmp_path) == sessions

    changed_price = copy.deepcopy(batch)
    changed_price["sessions"][0]["prices"]["TCS.NS"] += 1.
    with pytest.raises(ValueError, match="exact independently reconciled rows"):
        prospective._sessions(changed_price, protocol, now, tmp_path)
    changed_calendar = copy.deepcopy(batch)
    changed_calendar["calendar_dates"].remove("2020-11-14")
    with pytest.raises(ValueError, match="every independently verified exchange session"):
        prospective._sessions(changed_calendar, protocol, now, tmp_path)
