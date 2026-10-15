"""Synthetic protocol fixtures only: these tests establish no market evidence."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from vibefinance.evaluation import prospective as p


ROOT = Path(__file__).resolve().parents[1]


def clock(monkeypatch, day):
    monkeypatch.setattr(p, "utc_now", lambda: datetime.fromisoformat(day + "T11:00:00+00:00"))


def fixture_batch(tmp_path, days, ticker="FIXTURE.NS"):
    days = [str(pd.Timestamp(day).date()) for day in days]
    sessions = [{"date": day, "close_at": day + "T10:00:00+00:00", "observed_at": days[-1] + "T10:01:00+00:00",
                 "prices": {ticker: float(100*np.exp(index*.0001 + .01*np.sin(index*.7)))}}
                for index, day in enumerate(days)]
    artifacts = []
    for role in p.ARTIFACT_ROLES:
        path = tmp_path / (role + ".fixture.csv")
        if role in {"source_prices", "reference_prices"}:
            columns = {"date": days, "price": [row["prices"][ticker] for row in sessions], "volume": [1000]*len(days)}
            frame = pd.DataFrame(columns)
            if role == "reference_prices":
                frame = frame.rename(columns={"date": "Date", "price": "Close", "volume": "Volume"})
        elif role == "calendar":
            frame = pd.DataFrame({"date": days})
        else:
            frame = pd.DataFrame(columns=["date", "ticker", "kind", "value"])
        frame.to_csv(path, index=False)
        artifacts.append({"role": role, "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          **({"ticker": ticker} if role.endswith("prices") else {})})
    def metadata(provider, lineage):
        return {"provider": provider, "lineage": [lineage], "effective_lineage": [lineage],
                "source_url": f"https://{lineage}.example.org/data", "lineage_url": f"https://{lineage}.example.org/method",
                "license": "Explicit synthetic test fixture; no financial evidence", "license_url": f"https://{lineage}.example.org/license",
                "authorized_use": "noncommercial_research", "price_basis": "split_dividend_adjusted", "currency": "INR",
                "adjustment_method": "Explicit fixture arithmetic only", "adjustment_as_of": days[-1]}
    normalized = [{"date": row["date"], "ticker": name, "adjusted_close": float(price)}
                  for row in sessions for name, price in sorted(row["prices"].items())]
    return {"calendar_dates": days, "sessions": sessions,
            "reconciliation": {"schema_version": 1, "kind": "price_reconciliation", "status": "passed",
                "scope": {"start": days[0], "end": days[-1], "securities": [ticker],
                          "exchange_timezone": "Asia/Kolkata", "price_basis": "split_dividend_adjusted", "currency": "INR"},
                "sources": {"source": metadata("unit-fixture-one", "primaryfixture"),
                            "reference": metadata("unit-fixture-two", "referencefixture")},
                "checks": {"independent_price_lineage": True, "independent_calendar_lineage": True,
                           "independent_action_lineage": True},
                "artifacts": artifacts, "findings": [],
                "verified_rows_sha256": p.fingerprint(normalized),
                "verified_calendar_dates_sha256": p.fingerprint(days)}}


def rebind(batch):
    batch["reconciliation"]["scope"]["start"] = batch["sessions"][0]["date"]
    batch["reconciliation"]["scope"]["end"] = batch["sessions"][-1]["date"]
    normalized = [{"date": row["date"], "ticker": name, "adjusted_close": float(price)}
                  for row in batch["sessions"] for name, price in sorted(row["prices"].items())]
    batch["reconciliation"]["verified_rows_sha256"] = p.fingerprint(normalized)
    batch["reconciliation"]["verified_calendar_dates_sha256"] = p.fingerprint(batch["calendar_dates"])


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    clock(monkeypatch, "2026-10-15")
    monkeypatch.chdir(tmp_path)
    protocol = json.loads((ROOT / "data/prospective_protocol.json").read_text())
    protocol["securities"] = ["FIXTURE.NS"]
    batch = fixture_batch(tmp_path, pd.bdate_range("2010-01-01", "2023-12-29"))
    review = {"status": "reviewed_approved", "review_completed_at": "2026-10-14T11:00:00+00:00",
              "verified_securities": ["FIXTURE.NS"], "reviewer": "unit-test-fixture",
              "rights_evidence": "fixture-only", "universe_evidence": "fixture-only",
              "calendar_evidence": "fixture-only", "corporate_actions_evidence": "fixture-only"}
    directory = tmp_path / "run"
    frozen = p.register(directory, protocol, batch, review)
    return directory, protocol, batch, review, frozen


def issue(tmp_path, monkeypatch, directory):
    clock(monkeypatch, "2026-10-16")
    batch = fixture_batch(tmp_path, pd.bdate_range("2026-09-01", "2026-10-16"))
    return batch, p.record_forecast(directory, batch)


def matured(tmp_path, batch):
    future = fixture_batch(tmp_path, pd.bdate_range("2026-10-16", periods=31))
    future["sessions"][0] = copy.deepcopy(batch["sessions"][-1])
    future["sessions"][0]["observed_at"] = future["sessions"][-1]["observed_at"]
    rebind(future)
    return future


def test_registration_freezes_baselines_and_refuses_overwrite(prepared, monkeypatch):
    directory, protocol, batch, review, frozen = prepared
    assert set(frozen["models"]) == set(p.CANDIDATES)
    assert frozen["models"]["constant_half_zero"]["probability_up"] == .5
    assert all(model["radius_by_security"]["FIXTURE.NS"] >= 0 for model in frozen["models"].values())
    with pytest.raises(FileExistsError):
        p.register(directory, protocol, batch, review)
    assert p.load_registration(directory)["sha256"] == frozen["sha256"]


@pytest.mark.parametrize("change", ["past_origin", "spent", "future_label", "missing_rights", "failed_reconciliation", "missing_calendar", "mutated_artifact"])
def test_registration_rejects_temporal_and_provenance_failures(prepared, tmp_path, change):
    _, protocol, batch, review, _ = prepared
    protocol, batch, review = copy.deepcopy((protocol, batch, review))
    if change == "past_origin":
        protocol["origin_start"] = "2026-10-15"
    elif change == "spent":
        protocol["origin_start"], protocol["origin_end"] = "2024-01-01", "2025-12-31"
    elif change == "future_label":
        batch = fixture_batch(tmp_path, pd.bdate_range("2010-01-01", "2025-12-31"))
    elif change == "missing_rights":
        review["rights_evidence"] = ""
    elif change == "failed_reconciliation":
        batch["reconciliation"]["status"] = "not_validated"
    elif change == "missing_calendar":
        batch["calendar_dates"].pop()
    else:
        (tmp_path / batch["reconciliation"]["artifacts"][0]["path"]).write_text("changed")
    with pytest.raises(ValueError):
        p.register(tmp_path / "invalid", protocol, batch, review)
    assert not (tmp_path / "invalid").exists()


def test_mutated_registration_and_event_rejected(prepared, tmp_path, monkeypatch):
    directory, _, _, _, _ = prepared
    batch, forecast = issue(tmp_path, monkeypatch, directory)
    path = directory / "events/000001.json"
    event = json.loads(path.read_text())
    event["predictions"]["FIXTURE.NS"]["prior_mean"]["return"] = .9
    path.write_text(json.dumps(event))
    with pytest.raises(ValueError, match="mutated"):
        p.events(directory)
    registration = directory / "registration.json"
    frozen = json.loads(registration.read_text())
    frozen["models"]["prior_mean"]["return"] = 10
    registration.write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match="registration"):
        p.load_registration(directory)


def test_same_origin_all_baselines_and_causal_timestamp(prepared, tmp_path, monkeypatch):
    directory, _, _, _, _ = prepared
    batch, forecast = issue(tmp_path, monkeypatch, directory)
    assert set(forecast["predictions"]["FIXTURE.NS"]) == set(p.CANDIDATES)
    assert forecast["origin"] == "2026-10-16"
    assert all(np.isfinite(row["lower"]) for row in forecast["predictions"]["FIXTURE.NS"].values())
    with pytest.raises(ValueError, match="Duplicate/overlapping"):
        p.record_forecast(directory, batch)
    clock(monkeypatch, "2026-10-19")
    with pytest.raises(ValueError, match="origin date"):
        p.record_forecast(directory, batch)


def test_no_outcomes_before_forecast_or_before_thirty_sessions_mature(prepared, tmp_path, monkeypatch):
    directory, _, _, _, _ = prepared
    batch = fixture_batch(tmp_path, pd.bdate_range("2026-09-01", "2026-10-16"))
    with pytest.raises(ValueError, match="prior forecast"):
        p.record_outcome(directory, "2026-10-16", batch)
    batch, _ = issue(tmp_path, monkeypatch, directory)
    outcome = matured(tmp_path, batch)
    with pytest.raises(ValueError, match="causally available"):
        p.record_outcome(directory, "2026-10-16", outcome)
    clock(monkeypatch, outcome["sessions"][-1]["date"])
    too_short = copy.deepcopy(outcome)
    too_short["sessions"].pop()
    too_short["calendar_dates"].pop()
    rebind(too_short)
    with pytest.raises(ValueError, match="thirty subsequent"):
        p.record_outcome(directory, "2026-10-16", too_short)
    outcome["sessions"][0]["date"] = "2026-10-15"
    outcome["sessions"][0]["close_at"] = "2026-10-15T10:00:00+00:00"
    outcome["sessions"][0]["observed_at"] = outcome["sessions"][-1]["observed_at"]
    outcome["calendar_dates"][0] = "2026-10-15"
    rebind(outcome)
    with pytest.raises(ValueError, match="same origin"):
        p.record_outcome(directory, "2026-10-16", outcome)
    assert len(p.events(directory)) == 1


def test_outcome_scores_identical_rows_but_withholds_unstable_uncertainty(prepared, tmp_path, monkeypatch):
    directory, _, _, _, _ = prepared
    batch, forecast = issue(tmp_path, monkeypatch, directory)
    outcome = matured(tmp_path, batch)
    clock(monkeypatch, outcome["sessions"][-1]["date"])
    event = p.record_outcome(directory, forecast["origin"], outcome)
    with pytest.raises(ValueError, match="no existing outcome"):
        p.record_outcome(directory, forecast["origin"], outcome)
    report = p.score(directory)
    assert report["sample_size"] == 1 and report["pending_origins"] == 0
    assert set(report["metrics"]) == set(p.CANDIDATES)
    assert report["uncertainty"]["available"] is False
    assert report["paired_prior_mean_minus_baseline"] == {}
    assert report["portfolio_promotion"] is False and report["default_candidate"] == "prior_mean"
    assert report["ledger_head_sha256"] == event["sha256"]
    assert p.score(directory)["metrics"] == report["metrics"]


def test_before_close_and_future_feature_rows_fail_closed(prepared, tmp_path, monkeypatch):
    directory, _, _, _, _ = prepared
    clock(monkeypatch, "2026-10-16")
    batch = fixture_batch(tmp_path, pd.bdate_range("2026-09-01", "2026-10-16"))
    batch["sessions"][-1]["observed_at"] = "2026-10-17T10:01:00+00:00"
    with pytest.raises(ValueError, match="causally available"):
        p.record_forecast(directory, batch)
    assert p.events(directory) == []


@pytest.mark.parametrize("change", ["prices", "lineage", "calendar_hash", "missing_actions"])
def test_unrelated_or_changed_review_cannot_authorize_forecast(prepared, tmp_path, monkeypatch, change):
    directory, _, _, _, _ = prepared
    clock(monkeypatch, "2026-10-16")
    batch = fixture_batch(tmp_path, pd.bdate_range("2026-09-01", "2026-10-16"))
    if change == "prices":
        batch["sessions"][-1]["prices"]["FIXTURE.NS"] += 1
    elif change == "lineage":
        batch["reconciliation"]["sources"]["source"]["lineage"] = ["changed-feed"]
    elif change == "calendar_hash":
        batch["reconciliation"]["verified_calendar_dates_sha256"] = "0"*64
    else:
        batch["reconciliation"]["artifacts"] = [row for row in batch["reconciliation"]["artifacts"]
                                                   if row["role"] != "source_actions"]
    with pytest.raises(ValueError):
        p.record_forecast(directory, batch)
    assert p.events(directory) == []


def test_sparse_matured_development_is_not_registration(prepared, tmp_path):
    _, protocol, _, review, _ = prepared
    batch = fixture_batch(tmp_path, pd.bdate_range("2022-01-01", "2023-12-29"))
    with pytest.raises(ValueError, match="Insufficient matured"):
        p.register(tmp_path / "sparse", protocol, batch, review)
    assert not (tmp_path / "sparse").exists()


@pytest.mark.parametrize("action,restated_origin,target,expected", [
    ("two-for-one split", 50., 50., 0.),
    ("five-unit dividend offsets ex-date price drop", 95., 95., 0.),
    ("dividend reinvested at ex-date 95 then price recovers to 100", 95., 100., 100./95.-1.),
])
def test_same_vintage_split_dividend_returns_preserve_issuance(prepared, tmp_path, monkeypatch,
                                                              action, restated_origin, target, expected):
    directory, _, _, _, _ = prepared
    clock(monkeypatch, "2026-10-16")
    batch = fixture_batch(tmp_path, pd.bdate_range("2026-09-01", "2026-10-16"))
    batch["sessions"][-1]["prices"]["FIXTURE.NS"] = 100.
    rebind(batch)
    forecast = p.record_forecast(directory, batch)
    outcome = matured(tmp_path, batch)
    outcome["sessions"][0]["prices"]["FIXTURE.NS"] = restated_origin
    outcome["sessions"][-1]["prices"]["FIXTURE.NS"] = target
    # New independent evidence contains both endpoints in the later vintage.
    rebind(outcome)
    clock(monkeypatch, outcome["sessions"][-1]["date"])
    result = p.record_outcome(directory, forecast["origin"], outcome)
    assert result["returns"]["FIXTURE.NS"] == pytest.approx(expected), action
    assert result["origin_adjustment_factors"]["FIXTURE.NS"] == restated_origin/100
    assert result["outcome_adjustment_as_of"] > result["issuance_adjustment_as_of"]
    assert p.events(directory)[0] == forecast
    assert forecast["origin_prices"]["FIXTURE.NS"] == 100.


def test_skipped_origin_requires_explicit_missed_event_and_stays_incomplete(prepared, tmp_path, monkeypatch):
    directory, _, _, _, _ = prepared
    clock(monkeypatch, "2026-10-19")
    late = fixture_batch(tmp_path, pd.bdate_range("2026-09-01", "2026-10-19"))
    with pytest.raises(ValueError, match="First origin"):
        p.record_forecast(directory, late)
    missed = fixture_batch(tmp_path, pd.bdate_range("2026-09-01", "2026-10-16"))
    p.record_missed(directory, missed, "Fixture collector outage")
    report = p.score(directory)
    assert report["cohort"]["missed_scheduled_origins"] == ["2026-10-16"]
    assert report["uncertainty"]["available"] is False
    days = pd.bdate_range("2026-10-16", periods=31)
    clock(monkeypatch, str(days[-1].date()))
    next_batch = fixture_batch(tmp_path, days)
    p.record_forecast(directory, next_batch)
    assert p.score(directory)["cohort"]["issued"] == 1


def test_later_verified_calendar_reveals_matured_missing_outcome(prepared, tmp_path, monkeypatch):
    directory, _, _, _, _ = prepared
    batch, first = issue(tmp_path, monkeypatch, directory)
    days = pd.bdate_range("2026-10-16", periods=31)
    clock(monkeypatch, str(days[-1].date()))
    second = fixture_batch(tmp_path, days)
    p.record_forecast(directory, second)
    report = p.score(directory)
    assert report["cohort"]["known_matured_missing_outcomes"] == [first["origin"]]
    assert report["cohort"]["pending_maturity_not_established"] == [str(days[-1].date())]
    assert report["uncertainty"]["available"] is False


@pytest.mark.parametrize("escape", ["absolute", "traversal", "symlink"])
def test_reconciliation_artifacts_cannot_escape_root(prepared, tmp_path, monkeypatch, escape):
    directory, _, _, _, _ = prepared
    clock(monkeypatch, "2026-10-16")
    batch = fixture_batch(tmp_path, pd.bdate_range("2026-09-01", "2026-10-16"))
    artifact = batch["reconciliation"]["artifacts"][0]
    if escape == "absolute":
        artifact["path"] = str(tmp_path / artifact["path"])
    elif escape == "traversal":
        artifact["path"] = "../" + tmp_path.name + "/" + artifact["path"]
    else:
        outside = tmp_path.parent / (tmp_path.name + "-outside.csv")
        outside.write_bytes((tmp_path / artifact["path"]).read_bytes())
        link = tmp_path / "escaping-link.csv"
        link.symlink_to(outside)
        artifact["path"] = link.name
    with pytest.raises(ValueError, match="paths|symlink"):
        p.record_forecast(directory, batch, tmp_path)
    assert p.events(directory) == []


@pytest.mark.parametrize("defect", ["shared_lineage", "canonical_provider", "forged_effective_lineage", "missing_check", "false_check", "missing_provenance", "unresolved_warning"])
def test_passed_flag_cannot_bypass_independence_checks(prepared, tmp_path, monkeypatch, defect):
    directory, _, _, _, _ = prepared
    clock(monkeypatch, "2026-10-16")
    batch = fixture_batch(tmp_path, pd.bdate_range("2026-09-01", "2026-10-16"))
    report = batch["reconciliation"]
    source, reference = report["sources"]["source"], report["sources"]["reference"]
    if defect == "shared_lineage":
        reference["lineage"] = ["Primary Fixture"]
        reference["effective_lineage"] = ["primaryfixture"]
    elif defect == "canonical_provider":
        reference["provider"] = "Unit Fixture One"
    elif defect == "forged_effective_lineage":
        reference["effective_lineage"] = ["inventedindependence"]
    elif defect == "missing_check":
        report["checks"].pop("independent_calendar_lineage")
    elif defect == "false_check":
        report["checks"]["independent_action_lineage"] = False
    elif defect == "unresolved_warning":
        report["findings"] = [{"severity": "warning", "code": "missing_actions", "message": "fixture unresolved evidence"}]
    else:
        reference.pop("license_url")
    with pytest.raises(ValueError):
        p.record_forecast(directory, batch, tmp_path)
    assert p.events(directory) == []


@pytest.mark.parametrize("payload", [[], {"sessions": None}, {"sessions": [None]}])
def test_cli_malformed_input_exits_cleanly_without_traceback(prepared, tmp_path, monkeypatch, capsys, payload):
    from scripts import prospective as cli
    import sys
    directory, _, _, _, _ = prepared
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(sys, "argv", ["prospective", "forecast", "--run-dir", str(directory), "--data", str(path)])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert "Prospective workflow unavailable:" in error and "Traceback" not in error
    assert p.events(directory) == []


def test_cli_missing_local_input_reports_unavailable(prepared, tmp_path, monkeypatch, capsys):
    from scripts import prospective as cli
    import sys
    directory, _, _, _, _ = prepared
    monkeypatch.setattr(sys, "argv", ["prospective", "forecast", "--run-dir", str(directory),
                                     "--data", str(tmp_path / "missing-input.json")])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert "Prospective workflow unavailable:" in error and "Traceback" not in error
