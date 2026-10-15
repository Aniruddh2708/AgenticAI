"""Explicit unit fixtures; operational checks create no genuine market evidence."""
import copy
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

from scripts import run_prospective_cycle as cycle
from vibefinance.evaluation import prospective as core
from test_prospective import clock, fixture_batch, prepared


def add_batch(tmp_path, name, days, origin_session=None):
    directory = tmp_path / name
    directory.mkdir()
    batch = fixture_batch(directory, days)
    if origin_session:
        batch["sessions"][0]["prices"] = copy.deepcopy(origin_session["prices"])
        from test_prospective import rebind
        rebind(batch)
    path = directory / "batch.json"
    path.write_text(json.dumps(batch))
    return {"data": str(path.relative_to(tmp_path)), "artifact_root": name}, batch


def manifest(tmp_path, frozen, operations, calendar=None):
    receipt = {"registration_sha256": frozen["sha256"], "witnessed_at_utc": frozen["registered_at_utc"],
               "provider": "explicit unit-fixture witness only", "evidence_ref": "https://witness.example.org/fixture",
               "reviewed_by": "unit-fixture reviewer"}
    (tmp_path / "witness.json").write_text(json.dumps(receipt))
    inputs = {"schema_version": 1, "registration_witness": "witness.json", "operations": operations}
    if calendar:
        inputs["calendar_batch"] = calendar
    path = tmp_path / "cycle-inputs.json"
    path.write_text(json.dumps(inputs))
    return path


def first_cycle(prepared, tmp_path, monkeypatch):
    directory, _, _, _, frozen = prepared
    clock(monkeypatch, "2026-10-16")
    descriptor, batch = add_batch(tmp_path, "origin", pd.bdate_range("2026-09-01", "2026-10-16"))
    inputs = manifest(tmp_path, frozen, [{"kind": "forecast", **descriptor}])
    return directory, inputs, batch


def test_missing_study_lists_unfulfilled_real_prerequisites_without_writes(tmp_path):
    run = tmp_path / "absent"
    report, context = cycle.readiness(run)
    assert report["status"] == "blocked" and context is None
    assert set(report["missing_prerequisites"]) == {"registered_study", "genuine_independent_data_and_operator_review",
                                                   "registration_witness", "verified_cycle_inputs"}
    assert report["schedule"]["next_origin"] is None
    assert not run.exists()


def test_registration_without_inputs_reports_witness_and_manifest(prepared):
    directory, _, _, _, _ = prepared
    report, _ = cycle.readiness(directory)
    assert report["status"] == "blocked"
    assert "registration_witness_receipt" in report["missing_prerequisites"]
    assert report["schedule"]["calendar_days_until_next_origin"] is None
    assert not (directory / "cycles").exists()


def test_forecast_cycle_records_stable_intent_before_event_and_is_idempotent(prepared, tmp_path, monkeypatch):
    directory, inputs, _ = first_cycle(prepared, tmp_path, monkeypatch)
    original = core.record_forecast
    def assert_intent(*args):
        intent = list((directory / "cycles").glob("*/intent.json"))
        assert len(intent) == 1 and cycle._sealed(intent[0])["kind"] == "prospective_cycle_intent"
        return original(*args)
    monkeypatch.setattr(core, "record_forecast", assert_intent)
    report = cycle.run_cycle(directory, inputs)
    assert report["status"] == "completed" and len(core.events(directory)) == 1
    complete_path = directory / "cycles" / report["cycle_id"] / "completed.json"
    original_bytes = complete_path.read_bytes()
    clock(monkeypatch, "2026-10-19")
    repeated = cycle.run_cycle(directory, inputs)
    assert repeated == report and complete_path.read_bytes() == original_bytes
    assert len(core.events(directory)) == 1


@pytest.mark.parametrize("change", ["missing", "wrong_registration", "future", "after_first_forecast"])
def test_witness_is_required_and_must_precede_issuance(prepared, tmp_path, monkeypatch, change):
    directory, inputs, _ = first_cycle(prepared, tmp_path, monkeypatch)
    witness = tmp_path / "witness.json"
    receipt = json.loads(witness.read_text())
    if change == "after_first_forecast":
        assert cycle.run_cycle(directory, inputs)["status"] == "completed"
        receipt["witnessed_at_utc"] = "2026-10-16T11:00:00+00:00"
    elif change == "wrong_registration":
        receipt["registration_sha256"] = "0"*64
    elif change == "future":
        receipt["witnessed_at_utc"] = "2026-10-17T11:00:00+00:00"
    if change == "missing":
        witness.unlink()
    else:
        witness.write_text(json.dumps(receipt))
    report, _ = cycle.readiness(directory, inputs)
    assert report["status"] == "blocked"
    assert "valid_verified_cycle_inputs_and_witness" in report["missing_prerequisites"]


def test_calendar_readiness_counts_verified_sessions_without_forecasting_dates(prepared, tmp_path, monkeypatch):
    directory, inputs, first = first_cycle(prepared, tmp_path, monkeypatch)
    cycle.run_cycle(directory, inputs)
    days = pd.bdate_range("2026-10-16", periods=16)
    clock(monkeypatch, str(days[-1].date()))
    descriptor, _ = add_batch(tmp_path, "partial-calendar", days)
    inputs = manifest(tmp_path, prepared[-1], [], calendar=descriptor)
    report, _ = cycle.readiness(directory, inputs)
    assert report["status"] == "waiting"
    assert report["schedule"]["next_origin"] is None
    assert report["schedule"]["verified_sessions_until_next_origin"] == 15
    pending = report["schedule"]["pending_outcomes"][0]
    assert pending["verified_future_sessions"] == 15 and pending["verified_sessions_still_needed"] == 15
    assert pending["target_date"] is None and pending["calendar_days_until_target"] is None
    assert len(core.events(directory)) == 1


def test_unissued_outcome_and_early_sessions_fail_without_ledger_mutation(prepared, tmp_path, monkeypatch):
    directory, _, _, _, frozen = prepared
    days = pd.bdate_range("2026-10-16", periods=31)
    clock(monkeypatch, str(days[-1].date()))
    descriptor, _ = add_batch(tmp_path, "unissued", days)
    inputs = manifest(tmp_path, frozen, [{"kind": "outcome", "origin": "2026-10-16", **descriptor}])
    report = cycle.run_cycle(directory, inputs)
    assert report["status"] == "blocked" and "previously issued" in report["error"]
    assert core.events(directory) == [] and not (directory / "cycles").exists()
    clock(monkeypatch, "2026-10-16")
    report, _ = cycle.readiness(directory, inputs)
    assert report["status"] == "blocked" and "causally available" in report["error"]


def test_old_forecast_cannot_be_backfilled_but_missed_issuance_is_visible(prepared, tmp_path, monkeypatch):
    directory, inputs, _ = first_cycle(prepared, tmp_path, monkeypatch)
    clock(monkeypatch, "2026-10-19")
    report = cycle.run_cycle(directory, inputs)
    assert report["status"] == "blocked" and "overdue issuance" in report["error"]
    assert core.events(directory) == []
    value = json.loads(inputs.read_text())
    value["operations"][0].update(kind="missed", reason="Fixture collector outage; no forecast existed")
    inputs.write_text(json.dumps(value))
    assert cycle.run_cycle(directory, inputs)["status"] == "completed"
    assert core.events(directory)[0]["kind"] == "missed_origin"
    assert core.score(directory)["cohort"]["missed_scheduled_origins"] == ["2026-10-16"]


def test_append_without_step_audit_resumes_existing_event_after_origin_date(prepared, tmp_path, monkeypatch):
    directory, inputs, _ = first_cycle(prepared, tmp_path, monkeypatch)
    original = cycle._write
    injected = []
    def interrupt(path, value):
        if Path(path).name == "step-0001.json" and not injected:
            injected.append(True)
            raise OSError("Fixture interruption after ledger append")
        return original(path, value)
    monkeypatch.setattr(cycle, "_write", interrupt)
    first = cycle.run_cycle(directory, inputs)
    assert first["status"] == "blocked_partial_progress" and len(core.events(directory)) == 1
    clock(monkeypatch, "2026-10-19")
    resumed = cycle.run_cycle(directory, inputs)
    assert resumed["status"] == "completed" and resumed["cycle_id"] == first["cycle_id"]
    assert resumed["steps"][0]["disposition"] == "reconciled_existing"
    assert len(core.events(directory)) == 1
    assert len(list((directory / "cycles" / first["cycle_id"]).glob("attempt-*.started.json"))) == 2


def test_two_outcomes_resume_partial_cycle_without_repeating_first(prepared, tmp_path, monkeypatch):
    directory, inputs, _ = first_cycle(prepared, tmp_path, monkeypatch)
    cycle.run_cycle(directory, inputs)
    first_forecast = core.events(directory)[0]
    second_days = pd.bdate_range("2026-10-16", periods=31)
    clock(monkeypatch, str(second_days[-1].date()))
    second_descriptor, second = add_batch(tmp_path, "second-origin", second_days)
    second_forecast = core.record_forecast(directory, second, tmp_path / second_descriptor["artifact_root"])
    final_days = pd.bdate_range(second_forecast["origin"], periods=31)
    clock(monkeypatch, str(final_days[-1].date()))
    first_outcome, _ = add_batch(tmp_path, "first-outcome", second_days, first_forecast["origin_session"])
    second_outcome, _ = add_batch(tmp_path, "second-outcome", final_days, second_forecast["origin_session"])
    inputs = manifest(tmp_path, prepared[-1], [
        {"kind": "outcome", "origin": first_forecast["origin"], **first_outcome},
        {"kind": "outcome", "origin": second_forecast["origin"], **second_outcome}])
    original = core.record_outcome
    def interrupt(directory, origin, *args):
        if origin == second_forecast["origin"]:
            raise OSError("Fixture unavailable second artifact")
        return original(directory, origin, *args)
    monkeypatch.setattr(core, "record_outcome", interrupt)
    partial = cycle.run_cycle(directory, inputs)
    assert partial["status"] == "blocked_partial_progress" and len(core.events(directory)) == 3
    monkeypatch.setattr(core, "record_outcome", original)
    result = cycle.run_cycle(directory, inputs)
    assert result["status"] == "completed" and len(core.events(directory)) == 4
    assert result["steps"][0]["event_sha256"] == partial["steps"][0]["event_sha256"]
    assert len([record for record in core.events(directory) if record["kind"] == "outcome"]) == 2


@pytest.mark.parametrize("kind", ["data", "artifact_root", "registration_witness", "symlink"])
def test_input_paths_cannot_escape_manifest_directory(prepared, tmp_path, monkeypatch, kind):
    directory, inputs, _ = first_cycle(prepared, tmp_path, monkeypatch)
    value = json.loads(inputs.read_text())
    if kind == "symlink":
        outside = tmp_path.parent / (tmp_path.name + "-outside.json")
        outside.write_text((tmp_path / "witness.json").read_text())
        (tmp_path / "outside-link.json").symlink_to(outside)
        value["registration_witness"] = "outside-link.json"
    elif kind == "registration_witness":
        value[kind] = "../" + tmp_path.name + "/witness.json"
    else:
        value["operations"][0][kind] = "../escape"
    inputs.write_text(json.dumps(value))
    assert cycle.run_cycle(directory, inputs)["status"] == "blocked"
    assert core.events(directory) == []


def test_known_matured_missing_outcome_is_exposed_by_readiness(prepared, tmp_path, monkeypatch):
    directory, inputs, _ = first_cycle(prepared, tmp_path, monkeypatch)
    cycle.run_cycle(directory, inputs)
    days = pd.bdate_range("2026-10-16", periods=31)
    clock(monkeypatch, str(days[-1].date()))
    descriptor, _ = add_batch(tmp_path, "mature-calendar", days)
    inputs = manifest(tmp_path, prepared[-1], [], calendar=descriptor)
    report, _ = cycle.readiness(directory, inputs)
    assert report["status"] == "action_required"
    assert {operation["kind"] for operation in report["required_operations_not_in_inputs"]} == {"outcome", "forecast_or_missed"}
    pending = report["schedule"]["pending_outcomes"][0]
    assert pending["target_date"] == str(days[-1].date())
    assert pending["maturity"] == "matured_in_supplied_evidence"
    assert report["schedule"]["next_origin"] == str(days[-1].date())
    assert core.score(directory)["cohort"]["known_matured_missing_outcomes"] == []  # readiness did not mutate the ledger


def test_cycle_lock_and_changed_core_implementation_fail_closed(prepared, tmp_path, monkeypatch):
    directory, inputs, _ = first_cycle(prepared, tmp_path, monkeypatch)
    (directory / ".cycle.lock").mkdir()
    report, _ = cycle.readiness(directory, inputs)
    assert "reconciled_unlocked_ledger:.cycle.lock" in report["missing_prerequisites"]
    (directory / ".cycle.lock").rmdir()
    monkeypatch.setattr(core, "implementation_hashes", lambda: {})
    assert cycle.run_cycle(directory, inputs)["missing_prerequisites"] == ["valid_unchanged_registration_and_ledger"]


def test_cli_missing_prerequisites_are_json_and_nonzero_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_prospective_cycle", "ready", "--run-dir", str(tmp_path / "absent")])
    with pytest.raises(SystemExit) as failure:
        cycle.main()
    assert failure.value.code == 2
    output = capsys.readouterr()
    assert json.loads(output.out)["status"] == "blocked" and "Traceback" not in output.err


def test_disconnected_calendar_is_not_used_to_skip_unknown_sessions(prepared, tmp_path, monkeypatch):
    directory, inputs, _ = first_cycle(prepared, tmp_path, monkeypatch)
    cycle.run_cycle(directory, inputs)
    later_days = pd.bdate_range("2027-01-01", periods=31)
    clock(monkeypatch, str(later_days[-1].date()))
    descriptor, _ = add_batch(tmp_path, "disconnected-calendar", later_days)
    inputs = manifest(tmp_path, prepared[-1], [], calendar=descriptor)
    report, _ = cycle.readiness(directory, inputs)
    pending = report["schedule"]["pending_outcomes"][0]
    assert pending["verified_future_sessions"] == 0 and pending["target_date"] is None
    assert report["schedule"]["next_origin"] is None


def test_audit_symlink_escape_fails_before_any_ledger_event(prepared, tmp_path, monkeypatch):
    directory, inputs, _ = first_cycle(prepared, tmp_path, monkeypatch)
    outside = tmp_path / "outside-audits"
    outside.mkdir()
    (directory / "cycles").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="audit directory"):
        cycle.run_cycle(directory, inputs)
    assert core.events(directory) == [] and list(outside.iterdir()) == []



def test_changed_completed_step_audit_is_rejected_without_duplicate_events(prepared, tmp_path, monkeypatch):
    directory, inputs, _ = first_cycle(prepared, tmp_path, monkeypatch)
    report = cycle.run_cycle(directory, inputs)
    step_path = directory / "cycles" / report["cycle_id"] / "step-0001.json"
    changed = json.loads(step_path.read_text())
    changed["event_sha256"] = "0"*64
    step_path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="audit artifact changed"):
        cycle.run_cycle(directory, inputs)
    assert len(core.events(directory)) == 1
