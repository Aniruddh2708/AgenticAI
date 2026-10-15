"""Pre-register simple baselines and collect causal prospective observations.

This local audit ledger is not a trusted timestamp service or proof of source
accuracy. Independent reconciliation and an operator's evidence review remain
prerequisites. Nothing here changes portfolio decisions or trains on outcomes.
"""
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from vibefinance.data import reconciliation as evidence
from vibefinance.evaluation.forecast_selection import paired_loss_comparison
from vibefinance.evaluation.uncertainty import residual_quantile


SPENT_PERIODS = (("2019-01-01", "2020-12-31"), ("2024-01-01", "2025-12-31"))
CANDIDATES = ("prior_mean", "constant_half_zero", "always_up_zero")
ARTIFACT_ROLES = {"source_prices", "reference_prices", "calendar", "source_actions", "reference_actions"}


def utc_now():
    return datetime.now(timezone.utc)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def _day(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Use ISO session dates")
    return parsed


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
        raise ValueError("Need a finite numeric price or parameter")
    return float(value)


def implementation_hashes():
    root = Path(__file__).resolve().parents[2]
    names = ("vibefinance/evaluation/prospective.py", "scripts/prospective.py",
             "vibefinance/evaluation/uncertainty.py", "vibefinance/evaluation/forecast_selection.py",
             "data/prospective_protocol.json", "vibefinance/data/reconciliation.py")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def _protocol(protocol):
    template = json.loads((Path(__file__).resolve().parents[2] / "data/prospective_protocol.json").read_text())
    if set(protocol) != set(template):
        raise ValueError("Protocol needs all predeclared fields and no hidden options")
    # Only study identity, dates, universe and stricter sample requirements may vary.
    flexible = {"name", "securities", "origin_start", "origin_end",
                "minimum_training_origins_per_security", "minimum_calibration_origins_per_security",
                "minimum_origins_per_security", "minimum_calendar_quarters",
                "minimum_origins_per_regime_per_security"}
    if any(protocol[key] != value for key, value in template.items() if key not in flexible):
        raise ValueError("Methodology is fixed; changing it requires a new version and review")
    if (not protocol["name"] or not protocol["securities"] or
            len(set(protocol["securities"])) != len(protocol["securities"]) or
            not all(isinstance(ticker, str) and ticker for ticker in protocol["securities"])):
        raise ValueError("Need a named study and unique declared securities")
    for key in flexible - {"name", "securities", "origin_start", "origin_end"}:
        if type(protocol[key]) is not int or protocol[key] < template[key]:
            raise ValueError("Sample requirements may only become stricter")
    start, end = _day(protocol["origin_start"]), _day(protocol["origin_end"])
    if start > end or any(start <= _day(hi) and end >= _day(lo) for lo, hi in SPENT_PERIODS):
        raise ValueError("Prospective origins cannot intersect either spent period")


def _reconciliation(report, securities, start, end, artifact_root):
    scope = report.get("scope", {})
    if (report.get("schema_version") != 1 or report.get("kind") != "price_reconciliation" or
            report.get("status") != "passed" or set(scope.get("securities", [])) != set(securities) or
            scope.get("exchange_timezone") != "Asia/Kolkata" or scope.get("currency") != "INR" or
            scope.get("price_basis") != "split_dividend_adjusted" or
            _day(scope["start"]) > _day(start) or _day(scope["end"]) < _day(end)):
        raise ValueError("Independent price/calendar reconciliation is unavailable for the entire input scope")
    sources = report.get("sources", {})
    primary, reference = sources.get("source", {}), sources.get("reference", {})
    # Recheck the same canonical identities as F1, including inferred Yahoo ancestry.
    for source in (primary, reference):
        identity = evidence._identity(source)
        if (not isinstance(source.get("effective_lineage"), list) or
                source["effective_lineage"] != sorted(identity)):
            raise ValueError("Effective source lineage differs from the independently reviewed identity")
    if not evidence._independent(primary, reference):
        raise ValueError("Need independently reviewed, distinct provider lineage")
    checks = report.get("checks", {})
    if any(checks.get(key) is not True for key in
           ("independent_price_lineage", "independent_calendar_lineage", "independent_action_lineage")):
        raise ValueError("Independent price, calendar and action checks must all have passed")
    artifacts = report.get("artifacts", [])
    if not ARTIFACT_ROLES.issubset({item.get("role") for item in artifacts}):
        raise ValueError("Missing independent prices, calendar or corporate-action artifacts")
    root = Path(artifact_root).resolve()
    for item in artifacts:
        # F1's reader enforces local relative paths, no traversal/symlink escape,
        # valid hashes, existing files, and supported CSV/Parquet structure.
        evidence._read_artifact(item, root, item["role"], {"artifacts": []}, item.get("ticker"))
    if not isinstance(report.get("findings"), list) or report["findings"]:
        raise ValueError("A passed F1 report must have no unresolved reconciliation findings")
    return (primary["provider"], reference["provider"])


def _source_identity(report):
    # Dated/versioned exports may change path/query on the approved HTTPS origin.
    # Full snapshot URLs remain in the sealed report; all other declarations stay fixed.
    identities = {}
    for role in ("source", "reference"):
        identity = {key: value for key, value in report["sources"][role].items()
                    if key != "adjustment_as_of"}
        url = urlparse(identity["source_url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("Snapshot URLs require an approved HTTPS origin without user information")
        identity["source_url"] = {"origin": (url.scheme, url.hostname, url.port or 443), "fragment": url.fragment}
        identities[role] = identity
    return identities


def _vintage(report):
    sources = report["sources"]
    left, right = sources["source"].get("adjustment_as_of"), sources["reference"].get("adjustment_as_of")
    if not left or left != right:
        raise ValueError("Both sources need the identical documented adjustment vintage")
    return _day(left)


def _sessions(batch, protocol, now, artifact_root):
    sessions = batch.get("sessions", [])
    if not sessions:
        raise ValueError("Need dated independently reconciled sessions; no synthetic fallback")
    days = [row["date"] for row in sessions]
    if days != sorted(set(days)):
        raise ValueError("Session dates must be unique and chronological")
    zone = ZoneInfo(protocol["timezone"])
    for row in sessions:
        day = _day(row["date"])
        close, observed = _time(row["close_at"]), _time(row["observed_at"])
        if close.astimezone(zone).date() != day or not close <= observed <= now:
            raise ValueError("Session close/observation must be dated, already closed and causally available")
        if set(row["prices"]) != set(protocol["securities"]):
            raise ValueError("Every session needs the complete declared security universe")
        if any(_number(price) <= 0 for price in row["prices"].values()):
            raise ValueError("Adjusted prices must be positive")
    _reconciliation(batch.get("reconciliation", {}), protocol["securities"], days[0], days[-1], artifact_root)
    normalized = [{"date": row["date"], "ticker": ticker, "adjusted_close": float(price)}
                  for row in sessions for ticker, price in sorted(row["prices"].items())]
    report = batch["reconciliation"]
    vintage = _vintage(report)
    if not _day(days[-1]) <= vintage <= now.astimezone(zone).date():
        raise ValueError("Adjustment vintage must cover every input session and cannot come from the future")
    if any(_time(row["observed_at"]).astimezone(zone).date() < vintage for row in sessions):
        raise ValueError("Observation timestamps cannot predate the supplied adjusted-data vintage")
    if (report.get("verified_rows_sha256") != fingerprint(normalized) or
            report.get("verified_calendar_dates_sha256") != fingerprint(days)):
        raise ValueError("Session prices/calendar are not the exact independently reconciled rows")
    calendar = batch.get("calendar_dates", [])
    if calendar != days:
        raise ValueError("Prices must match every independently verified exchange session; missing dates fail closed")
    return sessions


def _write_new(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


@contextmanager
def _writer(directory):
    lock = Path(directory) / ".writer.lock"
    lock.mkdir()  # refuse concurrent writers or an interrupted, unreconciled append
    try:
        yield
    finally:
        lock.rmdir()


def _seal(value):
    return {**value, "sha256": fingerprint(value)}


def load_registration(directory):
    frozen = json.loads((Path(directory) / "registration.json").read_text())
    identity = frozen.pop("sha256")
    if fingerprint(frozen) != identity or frozen["implementation_sha256"] != implementation_hashes():
        raise ValueError("Frozen registration or implementation changed; preserve and close the old study")
    _protocol(frozen["protocol"])
    frozen["sha256"] = identity
    return frozen


def events(directory, registration=None):
    frozen = registration or load_registration(directory)
    previous, records = frozen["sha256"], []
    for index, path in enumerate(sorted((Path(directory) / "events").glob("*.json")), 1):
        if path.name != f"{index:06d}.json":
            raise ValueError("Ledger has a missing or reordered event")
        record = json.loads(path.read_text())
        identity = record.pop("sha256")
        if fingerprint(record) != identity or record.get("previous_sha256") != previous:
            raise ValueError("Ledger event was mutated or its chain changed")
        if record["recorded_at_utc"] < (records[-1]["recorded_at_utc"] if records else frozen["registered_at_utc"]):
            raise ValueError("Ledger timestamps must be chronological")
        record["sha256"] = identity
        records.append(record)
        previous = identity
    return records


def _append(directory, frozen, records, kind, payload, now):
    previous_time = records[-1]["recorded_at_utc"] if records else frozen["registered_at_utc"]
    if now < _time(previous_time):
        raise ValueError("Clock moved backward; ledger timestamps must remain chronological")
    record = _seal({"kind": kind, "recorded_at_utc": now.isoformat(),
                    "registration_sha256": frozen["sha256"],
                    "previous_sha256": records[-1]["sha256"] if records else frozen["sha256"], **payload})
    _write_new(Path(directory) / "events" / f"{len(records)+1:06d}.json", record)
    return record


def register(directory, protocol, development_batch, review, artifact_root="."):
    """Fit baseline parameters/calibration on predeclared, matured development only."""
    now = utc_now()
    _protocol(protocol)
    if _day(protocol["origin_start"]) <= now.astimezone(ZoneInfo(protocol["timezone"])).date():
        raise ValueError("Prospective origins must begin after registration, never by backdating a new directory")
    if (review.get("status") != "reviewed_approved" or _time(review["review_completed_at"]) > now or
            set(review.get("verified_securities", [])) != set(protocol["securities"]) or
            any(not review.get(key) for key in ("reviewer", "rights_evidence", "universe_evidence",
                                                "calendar_evidence", "corporate_actions_evidence"))):
        raise ValueError("Independent rights/calendar/actions/universe review is unavailable")
    sessions = _sessions(development_batch, protocol, now, artifact_root)
    if sessions[-1]["date"] > protocol["calibration_end"]:
        raise ValueError("Registration input must stop at the fixed calibration end; evaluation outcomes are excluded")
    rows, horizon = [], protocol["horizon_sessions"]
    # Deterministic non-overlapping origins, with calibration separately anchored.
    for start_key, end_key, kind in (("development_start", "development_end", "train"),
                                     ("calibration_start", "calibration_end", "calibration")):
        block = [row for row in sessions if protocol[start_key] <= row["date"] <= protocol[end_key]]
        for index in range(20, len(block)-horizon, horizon):
            origin, target = block[index], block[index+horizon]
            for ticker in protocol["securities"]:
                past = np.array([row["prices"][ticker] for row in block[index-20:index+1]], float)
                rows.append({"ticker": ticker, "kind": kind,
                             "return": target["prices"][ticker]/origin["prices"][ticker]-1,
                             "volatility": float(np.std(np.diff(np.log(past)), ddof=1))})
    for ticker in protocol["securities"]:
        for kind, key in (("train", "minimum_training_origins_per_security"),
                          ("calibration", "minimum_calibration_origins_per_security")):
            if sum(row["ticker"] == ticker and row["kind"] == kind for row in rows) < protocol[key]:
                raise ValueError("Insufficient matured non-overlapping development/calibration origins")
    train = [row for row in rows if row["kind"] == "train"]
    prior = float(np.mean([row["return"] > 0 for row in train]))
    mean = float(np.mean([row["return"] for row in train]))
    models = {"prior_mean": {"probability_up": prior, "return": mean},
              "constant_half_zero": {"probability_up": .5, "return": 0.},
              "always_up_zero": {"probability_up": 1., "return": 0.}}
    for model in models.values():
        model["radius_by_security"] = {ticker: residual_quantile(
            [abs(row["return"]-model["return"]) for row in rows
             if row["kind"] == "calibration" and row["ticker"] == ticker], protocol["interval_alpha"])
            for ticker in protocol["securities"]}
    frozen = _seal({"schema_version": 1, "kind": "prospective_baseline_registration",
        "registered_at_utc": now.isoformat(), "protocol": protocol, "review": review,
        "review_sha256": fingerprint(review), "development_batch_sha256": fingerprint(development_batch),
        "reconciliation": development_batch["reconciliation"], "models": models,
        "regime_threshold_by_security": {ticker: float(np.median([row["volatility"] for row in train
            if row["ticker"] == ticker])) for ticker in protocol["securities"]},
        "training_origins": len(train), "calibration_origins": len(rows)-len(train),
        "spent_periods": SPENT_PERIODS, "implementation_sha256": implementation_hashes(),
        "model_readiness": "research_only", "source_accuracy": "operator-reviewed; hashes establish identity only",
        "timestamp_limitation": "Local clock/files do not attest origin timing; independently timestamp and archive before origins"})
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "events").mkdir()
    _write_new(directory / "registration.json", frozen)
    return frozen


def _scheduled_origin(protocol, records, sessions):
    days = [row["date"] for row in sessions]
    planned = [row for row in records if row["kind"] in {"forecast", "missed_origin"}]
    if planned:
        previous = planned[-1]["origin"]
        if previous not in days or len(days)-1-days.index(previous) != protocol["horizon_sessions"]:
            raise ValueError("Duplicate/overlapping/skipped origin: issue or record the exact next thirty-session origin")
    else:
        if days[0] > protocol["origin_start"]:
            raise ValueError("First-origin evidence must start at or before the registered origin boundary")
        scheduled = next((day for day in days if day >= protocol["origin_start"]), None)
        if scheduled != days[-1]:
            raise ValueError("First origin must be the first verified session on/after the registered start; record missed origins")


def record_missed(directory, batch, reason, artifact_root="."):
    """Account for a scheduled issuance failure; never backfill its forecast."""
    now = utc_now()
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("A missed scheduled origin needs a documented reason")
    with _writer(directory):
        frozen = load_registration(directory)
        protocol, records = frozen["protocol"], events(directory, frozen)
        sessions = _sessions(batch, protocol, now, artifact_root)
        origin = sessions[-1]["date"]
        if not protocol["origin_start"] <= origin <= protocol["origin_end"]:
            raise ValueError("Missed origin must be inside the registered schedule")
        if _source_identity(batch["reconciliation"]) != _source_identity(frozen["reconciliation"]):
            raise ValueError("Source lineage changed after registration")
        if _vintage(batch["reconciliation"]) < _vintage(frozen["reconciliation"]):
            raise ValueError("Adjustment vintage precedes registration")
        _scheduled_origin(protocol, records, sessions)
        return _append(directory, frozen, records, "missed_origin", {"origin": origin, "reason": reason,
            "verified_session_dates": [row["date"] for row in sessions],
            "batch_sha256": fingerprint(batch), "reconciliation": batch["reconciliation"],
            "status": "not issued; no backfilled forecast or scored outcome; final completeness fails"}, now)


def record_forecast(directory, batch, artifact_root="."):
    now = utc_now()
    with _writer(directory):
        frozen = load_registration(directory)
        protocol, records = frozen["protocol"], events(directory, frozen)
        sessions = _sessions(batch, protocol, now, artifact_root)
        origin = sessions[-1]["date"]
        if _vintage(batch["reconciliation"]) < _vintage(frozen["reconciliation"]):
            raise ValueError("Adjustment vintage cannot precede the frozen registration")
        if _source_identity(batch["reconciliation"]) != _source_identity(frozen["reconciliation"]):
            raise ValueError("Source lineage changed after registration; independently review a new study")
        if (_day(origin) != now.astimezone(ZoneInfo(protocol["timezone"])).date() or
                not protocol["origin_start"] <= origin <= protocol["origin_end"] or
                now <= _time(frozen["registered_at_utc"])):
            raise ValueError("Forecasts must be recorded after close on their prospective origin date")
        if len(sessions) < 21:
            raise ValueError("Need twenty past session returns for the frozen causal regime rule")
        _scheduled_origin(protocol, records, sessions)
        predictions, regimes = {}, {}
        for ticker in protocol["securities"]:
            past = np.array([row["prices"][ticker] for row in sessions[-21:]], float)
            volatility = float(np.std(np.diff(np.log(past)), ddof=1))
            regimes[ticker] = "elevated" if volatility > frozen["regime_threshold_by_security"][ticker] else "calm"
            predictions[ticker] = {}
            for name, model in frozen["models"].items():
                radius = model["radius_by_security"][ticker]
                predictions[ticker][name] = {"probability_up": model["probability_up"], "return": model["return"],
                                            "lower": max(-1., model["return"]-radius), "upper": model["return"]+radius}
        return _append(directory, frozen, records, "forecast", {"origin": origin,
            "origin_prices": sessions[-1]["prices"], "origin_session": sessions[-1],
            "verified_session_dates": [row["date"] for row in sessions],
            "batch_sha256": fingerprint(batch), "reconciliation": batch["reconciliation"],
            "predictions": predictions, "regimes": regimes}, now)


def record_outcome(directory, origin, batch, artifact_root="."):
    now = utc_now()
    with _writer(directory):
        frozen = load_registration(directory)
        records = events(directory, frozen)
        matching = [row for row in records if row["kind"] == "forecast" and row["origin"] == origin]
        if len(matching) != 1 or any(row["kind"] == "outcome" and row["origin"] == origin for row in records):
            raise ValueError("Need exactly one prior forecast and no existing outcome for this origin")
        forecast = matching[0]
        sessions = _sessions(batch, frozen["protocol"], now, artifact_root)
        if _vintage(batch["reconciliation"]) < _vintage(frozen["reconciliation"]):
            raise ValueError("Adjustment vintage cannot precede the frozen registration")
        if _source_identity(batch["reconciliation"]) != _source_identity(frozen["reconciliation"]):
            raise ValueError("Source lineage changed after registration; independently review a new study")
        # Reconcile origin and target in ONE outcome vintage; keep issuance evidence immutable.
        if (len(sessions) != frozen["protocol"]["horizon_sessions"]+1 or
                sessions[0]["date"] != forecast["origin"] or
                sessions[0]["close_at"] != forecast["origin_session"]["close_at"] or
                _time(forecast["recorded_at_utc"]) >= _time(sessions[1]["close_at"])):
            raise ValueError("Outcome needs the same origin date/close and thirty subsequent matured sessions after forecast issuance")
        if _vintage(batch["reconciliation"]) < _vintage(forecast["reconciliation"]):
            raise ValueError("Outcome adjustment vintage cannot precede its issuance vintage")
        if (sessions[0]["prices"] != forecast["origin_prices"] and
                _vintage(batch["reconciliation"]) == _vintage(forecast["reconciliation"])):
            raise ValueError("Origin prices changed without a new independently reconciled adjustment vintage")
        target = sessions[-1]
        outcomes = {ticker: target["prices"][ticker]/sessions[0]["prices"][ticker]-1
                    for ticker in frozen["protocol"]["securities"]}
        return _append(directory, frozen, records, "outcome", {"origin": origin, "target_end": target["date"],
            "forecast_sha256": forecast["sha256"], "returns": outcomes,
            "verified_session_dates": [row["date"] for row in sessions],
            "issuance_adjustment_as_of": str(_vintage(forecast["reconciliation"])),
            "outcome_adjustment_as_of": str(_vintage(batch["reconciliation"])),
            "outcome_origin_prices": sessions[0]["prices"], "outcome_target_prices": target["prices"],
            "origin_adjustment_factors": {ticker: sessions[0]["prices"][ticker]/forecast["origin_prices"][ticker]
                                          for ticker in frozen["protocol"]["securities"]},
            "batch_sha256": fingerprint(batch), "reconciliation": batch["reconciliation"]}, now)


def _metrics(rows, candidate, alpha):
    target = np.array([row["target"] for row in rows])
    prediction = [row["predictions"][candidate] for row in rows]
    probability = np.array([row["probability_up"] for row in prediction])
    mean = np.array([row["return"] for row in prediction])
    low, high = np.array([row["lower"] for row in prediction]), np.array([row["upper"] for row in prediction])
    return {"brier": (probability-(target > 0))**2, "mae_return": np.abs(mean-target),
            "coverage": ((target >= low) & (target <= high)).astype(float), "mean_width": high-low,
            "interval_score": high-low+2/alpha*(np.maximum(low-target, 0)+np.maximum(target-high, 0))}


def score(directory):
    """Descriptive interim report; never select a winner or refit on this ledger."""
    frozen = load_registration(directory)
    protocol, records = frozen["protocol"], events(directory, frozen)
    forecasts = {row["origin"]: row for row in records if row["kind"] == "forecast"}
    rows = []
    for outcome in (row for row in records if row["kind"] == "outcome"):
        forecast = forecasts[outcome["origin"]]
        for ticker, target in outcome["returns"].items():
            rows.append({"as_of": pd.Timestamp(outcome["origin"]), "ticker": ticker,
                         "target": target, "regime": forecast["regimes"][ticker],
                         "predictions": forecast["predictions"][ticker]})
    observed_dates = sorted({day for record in records for day in record.get("verified_session_dates", [])})
    completed = {record["origin"] for record in records if record["kind"] == "outcome"}
    known_matured = {origin for origin in forecasts if sum(day > origin for day in observed_dates) >= protocol["horizon_sessions"]}
    overdue = sorted(known_matured-completed)
    pending = sorted(set(forecasts)-completed-known_matured)
    missed = [record["origin"] for record in records if record["kind"] == "missed_origin"]
    quarters = len({str(row["as_of"].to_period("Q")) for row in rows})
    by_ticker = {ticker: sum(row["ticker"] == ticker for row in rows) for ticker in protocol["securities"]}
    regimes = {ticker: {regime: sum(row["ticker"] == ticker and row["regime"] == regime for row in rows)
                       for regime in ("calm", "elevated")} for ticker in protocol["securities"]}
    adequate = (not overdue and not missed and min(by_ticker.values()) >= protocol["minimum_origins_per_security"] and
                quarters >= protocol["minimum_calendar_quarters"] and
                all(min(counts.values()) >= protocol["minimum_origins_per_regime_per_security"] for counts in regimes.values()))
    losses = {name: _metrics(rows, name, protocol["interval_alpha"]) for name in CANDIDATES} if rows else {}
    metrics = {name: {key: float(values.mean()) for key, values in entry.items()} for name, entry in losses.items()}
    paired, uncertainty = {}, {}
    if adequate:
        frame = pd.DataFrame(rows)
        for name in CANDIDATES:
            uncertainty[name] = {}
            for metric in protocol["metrics"]:
                result = paired_loss_comparison(frame, losses[name][metric], np.zeros(len(rows)))
                result.pop("eligible", None)
                result.pop("reason", None)
                uncertainty[name][metric] = result
        for baseline in CANDIDATES[1:]:
            paired[baseline] = {}
            for metric in protocol["metrics"]:
                result = paired_loss_comparison(frame, losses["prior_mean"][metric], losses[baseline][metric])
                result.pop("eligible", None)
                result.pop("reason", None)
                paired[baseline][metric] = result
    return {"schema_version": 1, "kind": "prospective_baseline_monitoring", "registration_sha256": frozen["sha256"],
        "ledger_head_sha256": records[-1]["sha256"] if records else frozen["sha256"],
        "generated_at_utc": utc_now().isoformat(), "sample_size": len(rows), "origins_by_security": by_ticker,
        "calendar_quarters": quarters, "regime_origins_by_security": regimes,
        "pending_origins": len(forecasts)-len(completed),
        "cohort": {"issued": len(forecasts), "outcome_recorded": len(completed),
            "known_matured": len(known_matured), "known_matured_missing_outcomes": overdue,
            "pending_maturity_not_established": pending, "missed_scheduled_origins": missed,
            "maturity_evidence_through": observed_dates[-1] if observed_dates else None,
            "qualification": "Maturity uses only ingested independently verified calendars; no inferred weekday calendar or silent complete-cohort claim"},
        "metrics": metrics, "metric_uncertainty": uncertainty, "paired_prior_mean_minus_baseline": paired,
        "by_calendar_quarter": {quarter: {"sample_size": len(group),
            "metrics": {name: {key: float(value.mean()) for key, value in _metrics(
                group, name, protocol["interval_alpha"]).items()} for name in CANDIDATES}}
            for quarter in sorted({str(row["as_of"].to_period("Q")) for row in rows})
            for group in [[row for row in rows if str(row["as_of"].to_period("Q")) == quarter]]},
        "by_regime": {regime: {"sample_size": len(group),
            "metrics": {name: {key: float(value.mean()) for key, value in _metrics(
                group, name, protocol["interval_alpha"]).items()} for name in CANDIDATES}}
            for regime in ("calm", "elevated") for group in [[row for row in rows if row["regime"] == regime]] if group},
        "by_security": {ticker: {name: {key: float(value.mean()) for key, value in _metrics(
            [row for row in rows if row["ticker"] == ticker], name, protocol["interval_alpha"]).items()}
            for name in CANDIDATES} for ticker in protocol["securities"] if by_ticker[ticker]},
        "uncertainty": {"available": adequate, "reason": "Minimum origins, quarters and predeclared regimes met" if adequate else
                        "Insufficient independent origins/quarters/regime support, missed origins or known-matured missing outcomes; no confidence bounds or validation claim",
                        "method": protocol["uncertainty"]},
        "status": "descriptive_interim; repeated monitoring is not a new untouched test",
        "criteria_assessment": {"status": "withheld_interim_manual_final_review_required",
            "fixed_origin_end": protocol["origin_end"],
            "reason": "No automatic final significance decision; preserve monitoring history and conduct the declared fixed-endpoint review",
            "planned_criteria": {
                "prior_mean_brier_and_mae_paired_upper_bound_against_each_baseline_strictly_below": {
                    "brier": -protocol["minimum_paired_brier_improvement"],
                    "mae_return": -protocol["minimum_paired_mae_improvement"]},
                "prior_mean_coverage_lower_bound_at_least": 1-protocol["interval_alpha"]-protocol["coverage_tolerance_below_nominal"],
                "prior_mean_interval_score_paired_upper_bound_against_each_baseline_at_most": protocol["maximum_paired_interval_score_increase"]}},
        "model_readiness": "research_only", "default_candidate": "prior_mean", "portfolio_promotion": False,
        "limitations": ["No automatic winner, refit, selection or portfolio admission.",
            "Local hashes detect accidental edits, not malicious rewrites/truncation without an independently archived witness; they do not attest origin timing.",
            "Operator-reviewed data provenance and session close/observation timestamps are external attestations, never established by a checksum.",
            "Quarter bootstrap is approximate; adjacent periods and securities can remain dependent.",
            "Only the predeclared universe is represented; nominal 90% is not guaranteed coverage."]}
