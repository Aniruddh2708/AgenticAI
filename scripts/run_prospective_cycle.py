"""Run explicit verified prospective operations; never register, fetch or backdate."""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vibefinance.evaluation import prospective as core


EXPECTED_ERRORS = (ValueError, KeyError, TypeError, AttributeError, OSError)
REQUIREMENTS = ["genuine passed independent prices/calendar/corporate-actions reconciliation",
                "operator rights, point-in-time universe and evidence review",
                "new registration before its first prospective origin",
                "independently witnessed registration receipt before issuance"]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _local(base, name, directory=False):
    if not isinstance(name, str) or not name or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("Input paths must be relative and confined to the inputs-manifest directory")
    path = (base / name).resolve()
    if not path.is_relative_to(base) or not (path.is_dir() if directory else path.is_file()):
        raise ValueError("Missing input or path/symlink escapes the inputs-manifest directory")
    return path


def _snapshot(path):
    raw = Path(path).read_bytes()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def _read(path):
    return _snapshot(path)[0]


def _head(frozen, records):
    return records[-1]["sha256"] if records else frozen["sha256"]


def _receipt(value, frozen, records, now):
    if (not isinstance(value, dict) or value.get("registration_sha256") != frozen["sha256"] or
            any(not isinstance(value.get(key), str) or not value[key].strip()
                for key in ("witnessed_at_utc", "provider", "evidence_ref", "reviewed_by"))):
        raise ValueError("Registration witness receipt must identify this registration, witness and independent reviewer")
    witnessed = core._time(value["witnessed_at_utc"])
    if not core._time(frozen["registered_at_utc"]) <= witnessed <= now:
        raise ValueError("Witness receipt timestamp must follow registration and cannot be in the future")
    issued = [record for record in records if record["kind"] == "forecast"]
    if issued and witnessed >= min(core._time(record["recorded_at_utc"]) for record in issued):
        raise ValueError("Registration must have been independently witnessed before its first issued forecast")
    url = urlparse(value["evidence_ref"])
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("Witness evidence requires an HTTPS reference without URL user information")


def _existing(operation, records):
    kind = "missed_origin" if operation["kind"] == "missed" else operation["kind"]
    matching = [record for record in records if record["kind"] == kind and record["origin"] == operation["origin"]]
    if len(matching) > 1:
        raise ValueError("Duplicate ledger operations require independent reconciliation")
    if matching and (matching[0]["batch_sha256"] != operation["batch_sha256"] or
                     kind == "missed_origin" and matching[0]["reason"] != operation.get("reason")):
        raise ValueError("Existing operation uses different evidence or reason; preserve it instead of overwriting")
    return matching[0] if matching else None


def _load_inputs(path, frozen, records, now):
    path = Path(path).resolve()
    manifest, manifest_hash = _snapshot(path)
    base = path.parent
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or not isinstance(manifest.get("operations"), list):
        raise ValueError("Use cycle inputs schema_version 1 with an explicit operations list")
    receipt_path = _local(base, manifest.get("registration_witness"))
    receipt, receipt_hash = _snapshot(receipt_path)
    _receipt(receipt, frozen, records, now)
    files = {str(path): manifest_hash, str(receipt_path): receipt_hash}
    operations, batches, keys = [], [], set()
    for specification in manifest["operations"]:
        if not isinstance(specification, dict) or specification.get("kind") not in {"forecast", "missed", "outcome"}:
            raise ValueError("Operations must explicitly name forecast, missed or outcome")
        data_path = _local(base, specification.get("data"))
        artifact_root = _local(base, specification.get("artifact_root", "."), directory=True)
        batch, batch_file_hash = _snapshot(data_path)
        sessions = core._sessions(batch, frozen["protocol"], now, artifact_root)
        if core._source_identity(batch["reconciliation"]) != core._source_identity(frozen["reconciliation"]):
            raise ValueError("Verified batch source contract differs from the registered study")
        if core._vintage(batch["reconciliation"]) < core._vintage(frozen["reconciliation"]):
            raise ValueError("Verified batch adjustment vintage predates registration")
        origin = specification.get("origin") if specification["kind"] == "outcome" else sessions[-1]["date"]
        core._day(origin)
        operation = {"kind": specification["kind"], "origin": origin, "data": str(data_path),
                     "artifact_root": str(artifact_root), "batch_sha256": core.fingerprint(batch), "batch": batch}
        if operation["kind"] == "missed":
            if not isinstance(specification.get("reason"), str) or not specification["reason"].strip():
                raise ValueError("Missed-origin operations require an explicit issuance-failure reason")
            operation["reason"] = specification["reason"]
        key = (operation["kind"], origin)
        if key in keys:
            raise ValueError("A cycle may not contain duplicate operations")
        keys.add(key)
        files[str(data_path)] = batch_file_hash
        operation["operation_id"] = core.fingerprint({key: value for key, value in operation.items() if key != "batch"})
        operations.append(operation)
        batches.append(batch)
    if manifest.get("calendar_batch"):
        descriptor = manifest["calendar_batch"]
        data_path = _local(base, descriptor["data"])
        root = _local(base, descriptor.get("artifact_root", "."), directory=True)
        batch, batch_file_hash = _snapshot(data_path)
        core._sessions(batch, frozen["protocol"], now, root)
        if core._source_identity(batch["reconciliation"]) != core._source_identity(frozen["reconciliation"]):
            raise ValueError("Calendar batch source contract differs from the registered study")
        files[str(data_path)] = batch_file_hash
        batches.append(batch)
    return {"manifest_path": str(path), "manifest_sha256": manifest_hash, "receipt": receipt,
            "operations": operations, "batches": batches, "files": files}


def _preflight(frozen, records, operations, now):
    virtual = list(records)
    protocol = frozen["protocol"]
    for operation in operations:
        if _existing(operation, virtual):
            continue
        batch, origin = operation["batch"], operation["origin"]
        sessions = batch["sessions"]
        if operation["kind"] in {"forecast", "missed"}:
            if not protocol["origin_start"] <= origin <= protocol["origin_end"]:
                raise ValueError("Scheduled origin lies outside the registered observation window")
            core._scheduled_origin(protocol, virtual, sessions)
            if operation["kind"] == "forecast" and (core._day(origin) != now.astimezone(ZoneInfo(protocol["timezone"])).date() or len(sessions) < 21):
                raise ValueError("A forecast needs today's closed scheduled origin and twenty causal past returns; overdue issuance requires an explicit missed operation")
            virtual.append({"kind": "missed_origin" if operation["kind"] == "missed" else "forecast", "origin": origin,
                            "batch_sha256": operation["batch_sha256"], "reason": operation.get("reason"),
                            "origin_session": sessions[-1], "recorded_at_utc": now.isoformat(),
                            "reconciliation": batch["reconciliation"]})
        else:
            forecasts = [record for record in virtual if record["kind"] == "forecast" and record["origin"] == origin]
            if len(forecasts) != 1:
                raise ValueError("Outcome requires a previously issued forecast; never create retrospective forecasts")
            forecast = forecasts[0]
            if (len(sessions) != protocol["horizon_sessions"]+1 or sessions[0]["date"] != origin or
                    sessions[0]["close_at"] != forecast["origin_session"]["close_at"] or
                    core._time(sessions[1]["close_at"]) <= core._time(forecast["recorded_at_utc"])):
                raise ValueError("Outcome requires the issued origin plus exactly thirty subsequently closed verified sessions")
            if core._vintage(batch["reconciliation"]) < core._vintage(forecast["reconciliation"]):
                raise ValueError("Outcome adjustment vintage predates issuance")


def _schedule(frozen, records, batches):
    """Derive dates only over overlapping, independently reconciled calendar scopes."""
    protocol = frozen["protocol"]
    today = core.utc_now().astimezone(ZoneInfo(protocol["timezone"])).date()
    evidence = [record for record in records if "verified_session_dates" in record]
    spans = [(record["reconciliation"]["scope"]["start"], record["reconciliation"]["scope"]["end"]) for record in evidence]
    spans += [(batch["reconciliation"]["scope"]["start"], batch["reconciliation"]["scope"]["end"]) for batch in batches]
    days = {day for record in evidence for day in record["verified_session_dates"]}
    days.update(row["date"] for batch in batches for row in batch["sessions"])
    def after(anchor, include=False):
        end = anchor
        covered = False
        for start, stop in sorted(spans):
            if start <= end and stop >= anchor:
                covered, end = True, max(end, stop)
        return sorted(day for day in days if (day >= anchor if include else day > anchor) and day <= end) if covered else []
    planned = [record for record in records if record["kind"] in {"forecast", "missed_origin"}]
    if planned:
        observed = after(planned[-1]["origin"])
        remaining = max(0, protocol["horizon_sessions"]-len(observed))
        due = observed[protocol["horizon_sessions"]-1] if not remaining else None
    else:
        observed = after(protocol["origin_start"], include=True)
        due, remaining = (observed[0] if observed else None), (0 if observed else None)
    completed = {record["origin"] for record in records if record["kind"] == "outcome"}
    pending = []
    for record in records:
        if record["kind"] != "forecast" or record["origin"] in completed:
            continue
        observed = after(record["origin"])
        target = observed[protocol["horizon_sessions"]-1] if len(observed) >= protocol["horizon_sessions"] else None
        pending.append({"origin": record["origin"], "verified_future_sessions": min(len(observed), protocol["horizon_sessions"]),
                        "verified_sessions_still_needed": max(0, protocol["horizon_sessions"]-len(observed)),
                        "target_date": target, "calendar_days_until_target": (core._day(target)-today).days if target else None,
                        "maturity": "matured_in_supplied_evidence" if target else "not_established_without_more_verified_sessions"})
    if due and due > protocol["origin_end"]:
        due = None
    return {"next_origin": due, "origin_boundary": protocol["origin_start"],
            "verified_sessions_until_next_origin": remaining, "calendar_days_until_next_origin": (core._day(due)-today).days if due else None,
            "pending_outcomes": pending, "qualification": "No future exchange sessions or completion dates are invented; missing calendar evidence is not an unexpired-target assertion"}


def _required_actions(schedule, records, operations, protocol, now):
    covered = {(operation["kind"], operation["origin"]) for operation in operations}
    actions = [{"kind": "outcome", "origin": pending["origin"], "target_date": pending["target_date"],
                "reason": "Issued target has matured in the supplied verified calendar but no outcome is recorded"}
               for pending in schedule["pending_outcomes"] if pending["target_date"]
               and ("outcome", pending["origin"]) not in covered]
    due = schedule["next_origin"]
    today = now.astimezone(ZoneInfo(protocol["timezone"])).date().isoformat()
    if due and due <= today and not ({("forecast", due), ("missed", due)} & covered):
        actions.append({"kind": "forecast_or_missed" if due == today else "missed", "origin": due,
                        "reason": "Scheduled origin is due; overdue forecasts may only be accounted for as missed"})
    return actions


def _cohort(records, schedule):
    return {"issued": sum(record["kind"] == "forecast" for record in records),
            "outcome_recorded": sum(record["kind"] == "outcome" for record in records),
            "missed_scheduled_origins": [record["origin"] for record in records if record["kind"] == "missed_origin"],
            "known_matured_missing_outcomes": [pending["origin"] for pending in schedule["pending_outcomes"] if pending["target_date"]],
            "maturity_not_established": [pending["origin"] for pending in schedule["pending_outcomes"] if not pending["target_date"]],
            "scope": "Supplied verified calendar evidence only; this does not certify the final planned cohort"}


def readiness(run_dir, inputs=None):
    now, directory = core.utc_now(), Path(run_dir)
    result = {"schema_version": 1, "kind": "prospective_cycle_readiness", "checked_at_utc": now.isoformat(),
              "run_directory": str(directory.resolve()), "status": "blocked", "missing_prerequisites": [],
              "registration_requirements": REQUIREMENTS, "portfolio_promotion": False,
              "limitations": ["Witness and timestamp authenticity remain independently reviewed external evidence.",
                              "Fresh outcomes require actual issued forecasts and thirty observed verified sessions; they cannot be completed today by changing clocks or directories."]}
    if not (directory / "registration.json").is_file():
        result["missing_prerequisites"] = ["registered_study", "genuine_independent_data_and_operator_review", "registration_witness", "verified_cycle_inputs"]
        result["schedule"] = {"next_origin": None, "pending_outcomes": [], "calendar_days_until_next_origin": None}
        return result, None
    try:
        frozen = core.load_registration(directory)
        records = core.events(directory, frozen)
    except EXPECTED_ERRORS as error:
        result["missing_prerequisites"].append("valid_unchanged_registration_and_ledger")
        result["error"] = str(error)
        return result, None
    result["registration_sha256"] = frozen["sha256"]
    result["ledger_head_sha256"] = _head(frozen, records)
    result["schedule"] = _schedule(frozen, records, [])
    for lock in (".writer.lock", ".cycle.lock"):
        if (directory / lock).exists():
            result["missing_prerequisites"].append("reconciled_unlocked_ledger:"+lock)
    loaded = None
    if not inputs:
        result["missing_prerequisites"] += ["verified_cycle_inputs_manifest", "registration_witness_receipt"]
    else:
        try:
            loaded = _load_inputs(inputs, frozen, records, now)
            _preflight(frozen, records, loaded["operations"], now)
            result["schedule"] = _schedule(frozen, records, loaded["batches"])
            result["witness"] = {"registration_sha256": loaded["receipt"]["registration_sha256"], "authenticity": "operator-reviewed; not independently authenticated by this command"}
            result["operations"] = [{key: value for key, value in operation.items() if key != "batch"} for operation in loaded["operations"]]
        except EXPECTED_ERRORS as error:
            result["missing_prerequisites"].append("valid_verified_cycle_inputs_and_witness")
            result["error"] = str(error)
    result["cohort"] = _cohort(records, result["schedule"])
    result["required_operations_not_in_inputs"] = _required_actions(
        result["schedule"], records, loaded["operations"] if loaded else [], frozen["protocol"], now)
    if not result["missing_prerequisites"]:
        result["status"] = "ready" if loaded["operations"] else ("action_required" if result["required_operations_not_in_inputs"] else "waiting")
    context = {"frozen": frozen, "records": records, "loaded": loaded} if loaded else None
    return result, context


def _sealed(path):
    if Path(path).is_symlink():
        raise ValueError("Cycle audit artifacts must not be symlinks")
    value = _read(path)
    expected = value.pop("sha256")
    if core.fingerprint(value) != expected:
        raise ValueError("Cycle audit artifact changed; retain and independently reconcile it")
    return {**value, "sha256": expected}


def _write(path, value):
    core._write_new(path, core._seal(value))


@contextmanager
def _cycle_lock(directory):
    lock = directory / ".cycle.lock"
    lock.mkdir()
    try:
        yield
    finally:
        lock.rmdir()


def _check_files(loaded, runner_hash):
    if _sha(__file__) != runner_hash or any(_sha(path) != expected for path, expected in loaded["files"].items()):
        raise ValueError("Cycle inputs or runner changed after intent; preserve the partial cycle and reconcile")


def run_cycle(run_dir, inputs):
    check, context = readiness(run_dir, inputs)
    if check["status"] in {"blocked", "action_required"}:
        return check
    directory = Path(run_dir).resolve()
    frozen, loaded = context["frozen"], context["loaded"]
    runner_hash = _sha(__file__)
    identity = {"registration_sha256": frozen["sha256"], "runner_sha256": runner_hash,
                "inputs_manifest_sha256": loaded["manifest_sha256"], "input_files": loaded["files"],
                "operations": [{key: value for key, value in operation.items() if key != "batch"} for operation in loaded["operations"]]}
    cycle_id = core.fingerprint(identity)  # deliberately excludes current ledger head/time: stable on resume
    audit_root = (directory / "cycles").resolve()
    if not audit_root.is_relative_to(directory):
        raise ValueError("Cycle audit directory must remain inside the registered study")
    audit_root.mkdir(exist_ok=True)
    audit = (audit_root / cycle_id).resolve()
    if not audit.is_relative_to(directory):
        raise ValueError("Cycle intent directory must remain inside the registered study")
    audit.mkdir(exist_ok=True)
    with _cycle_lock(directory):
        intent_path = audit / "intent.json"
        if intent_path.exists():
            intent = _sealed(intent_path)
            if intent["identity"] != identity:
                raise ValueError("Cycle intent differs from the supplied evidence")
        else:
            _write(intent_path, {"kind": "prospective_cycle_intent", "cycle_id": cycle_id, "identity": identity,
                                 "created_at_utc": core.utc_now().isoformat(), "initial_ledger_head_sha256": _head(frozen, core.events(directory, frozen))})
        _check_files(loaded, runner_hash)
        completion = audit / "completed.json"
        if completion.exists():
            report = _sealed(completion)
            for index, (operation, step) in enumerate(zip(loaded["operations"], report["steps"], strict=True), 1):
                saved_step = _sealed(audit / f"step-{index:04d}.json")
                if {key: value for key, value in saved_step.items() if key != "sha256"} != {key: value for key, value in step.items() if key != "sha256"}:
                    raise ValueError("Completed cycle step receipt differs from its completion record")
                existing = _existing(operation, core.events(directory, frozen))
                if not existing or existing["sha256"] != step["event_sha256"]:
                    raise ValueError("Completed cycle no longer matches its ledger events")
            return report
        attempt = len(list(audit.glob("attempt-*.started.json")))+1
        _write(audit / f"attempt-{attempt:04d}.started.json", {"kind": "prospective_cycle_attempt", "cycle_id": cycle_id,
            "started_at_utc": core.utc_now().isoformat(), "ledger_head_sha256": _head(frozen, core.events(directory, frozen))})
        steps = []
        try:
            for index, operation in enumerate(loaded["operations"], 1):
                _check_files(loaded, runner_hash)
                records = core.events(directory, frozen)
                event = _existing(operation, records)
                disposition = "reconciled_existing" if event else "recorded"
                if event is None:
                    if operation["kind"] == "forecast":
                        event = core.record_forecast(directory, operation["batch"], operation["artifact_root"])
                    elif operation["kind"] == "missed":
                        event = core.record_missed(directory, operation["batch"], operation["reason"], operation["artifact_root"])
                    else:
                        event = core.record_outcome(directory, operation["origin"], operation["batch"], operation["artifact_root"])
                step_path = audit / f"step-{index:04d}.json"
                step = {"kind": "prospective_cycle_step", "operation_id": operation["operation_id"],
                        "event_sha256": event["sha256"], "disposition": disposition,
                        "reconciled_at_utc": core.utc_now().isoformat()}
                if step_path.exists():
                    prior = _sealed(step_path)
                    if prior["operation_id"] != step["operation_id"] or prior["event_sha256"] != step["event_sha256"]:
                        raise ValueError("Cycle step differs from its immutable ledger event")
                    step = prior
                else:
                    _write(step_path, step)
                steps.append(step)
            _check_files(loaded, runner_hash)
            current_records = core.events(directory, frozen)
            current_schedule = _schedule(frozen, current_records, loaded["batches"])
            report = {"kind": "prospective_cycle_completed", "status": "completed", "cycle_id": cycle_id,
                      "registration_sha256": frozen["sha256"], "steps": steps,
                      "completed_at_utc": core.utc_now().isoformat(), "ledger_head_sha256": _head(frozen, core.events(directory, frozen)),
                      "cohort": _cohort(current_records, current_schedule),
                      "schedule_after": current_schedule,
                      "required_operations_remaining": _required_actions(current_schedule, current_records, [], frozen["protocol"], core.utc_now()),
                      "portfolio_promotion": False, "interpretation": "Operational recording only; no model winner, new validation claim or automatic promotion"}
            _write(completion, report)
            return _sealed(completion)
        except EXPECTED_ERRORS as error:
            report = {"kind": "prospective_cycle_partial", "status": "blocked_partial_progress", "cycle_id": cycle_id,
                      "steps": steps, "error": str(error), "failed_at_utc": core.utc_now().isoformat(),
                      "instruction": "Preserve intent, evidence and ledger; rerun identical inputs to reconcile existing events, never backfill forecasts"}
            _write(audit / f"attempt-{attempt:04d}.failed.json", report)
            return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("ready", "run"))
    parser.add_argument("--run-dir", default=".runtime/prospective/baselines-v1")
    parser.add_argument("--inputs", help="Local cycle-inputs JSON with explicit verified operations and witness receipt")
    parser.add_argument("--output", help="Exclusive-create readiness/result JSON; never overwrite")
    args = parser.parse_args()
    try:
        result = readiness(args.run_dir, args.inputs)[0] if args.stage == "ready" else run_cycle(args.run_dir, args.inputs)
        if args.output:
            core._write_new(args.output, result)
    except EXPECTED_ERRORS as error:
        result = {"kind": "prospective_cycle_unavailable", "status": "blocked", "error": str(error)}
    print(json.dumps(result, indent=2, allow_nan=False))
    if result["status"] in {"blocked", "blocked_partial_progress", "action_required"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
