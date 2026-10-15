"""Read saved research summaries without training or downloading during a request."""

import json
import math
import os
from pathlib import Path

from vibefinance.config import STATE_DIR


_PUBLIC_FIELDS = (
    "schema_version", "kind", "protocol", "data", "validation", "test",
    "selection", "limitations",
)
_OPTIONAL_PUBLIC_FIELDS = (
    "model_id", "selection_id", "evaluated_at_utc", "runtime", "features", "calibration",
    "experiment_version", "period_status", "horizon_definition", "development_status",
    "original_selection_id", "analysis_status", "data_quality", "correction",
)
_METRICS = {"brier", "log_loss", "accuracy", "mae_return", "rmse_return"}
_INTERVAL_RATES = {"coverage", "observed_coverage", "nominal_coverage", "lower_miss_rate", "upper_miss_rate"}
_INTERVAL_VALUES = _INTERVAL_RATES | {"mean_width", "interval_score", "radius_return"}
_MAX_REPORT_BYTES = 32 * 1024 * 1024


def _unavailable(reason):
    return {
        "status": "unavailable", "reason": reason,
        "model_readiness": "research_only",
        "message": (
            "No saved real-history forecast audit is available. Run the documented "
            "offline forecast evaluation to generate a report."
            if reason == "not_generated" else
            "The saved real-history forecast audit is unreadable or has an unsupported schema. "
            "Regenerate it with the documented offline forecast evaluation."
        ),
    }


def _reject_json_constant(value):
    raise ValueError("Non-finite JSON number")


def _valid_interval(interval):
    if not isinstance(interval, dict):
        return False
    for key in _INTERVAL_VALUES & interval.keys():
        value = interval[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            return False
        if key in _INTERVAL_RATES and value > 1:
            return False
    if "simultaneous_coverage_details" in interval:
        details = interval["simultaneous_coverage_details"]
        if not isinstance(details, dict) or not _valid_interval(details):
            return False
        for key in ("complete_forecast_dates", "excluded_partial_forecast_dates", "calendar_quarters"):
            if key in details and (type(details[key]) is not int or details[key] < 0):
                return False
    return True


def _valid_summary(report):
    """Check the publication contract, not the report's scientific conclusions."""
    if not isinstance(report, dict):
        return False
    if type(report.get("schema_version")) is not int or report["schema_version"] != 1:
        return False
    if report.get("kind") != "historical_price_forecast":
        return False
    if any(not isinstance(report.get(key), dict) for key in ("protocol", "selection")):
        return False
    if not isinstance(report.get("data"), list) or not all(isinstance(item, dict) for item in report["data"]):
        return False
    if not isinstance(report.get("limitations"), list) or not all(isinstance(item, str) for item in report["limitations"]):
        return False
    admission = report["selection"].get("admission")
    if not isinstance(admission, dict) or type(admission.get("passed")) is not bool or not isinstance(admission.get("reason"), str):
        return False
    for name in ("validation", "test"):
        period = report.get(name)
        if not isinstance(period, dict) or type(period.get("sample_size")) is not int or period["sample_size"] < 0:
            return False
        metrics = period.get("metrics")
        if not isinstance(metrics, dict):
            return False
        if "interval" in period and not _valid_interval(period["interval"]):
            return False
        if "intervals" in period:
            if not isinstance(period["intervals"], dict):
                return False
            for point_method, intervals in period["intervals"].items():
                if not isinstance(point_method, str) or not isinstance(intervals, dict):
                    return False
                if any(not isinstance(method, str) or not _valid_interval(values)
                       for method, values in intervals.items()):
                    return False
        for method, values in metrics.items():
            if not isinstance(method, str) or not isinstance(values, dict):
                return False
            for metric in _METRICS & values.keys():
                value = values[metric]
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    return False
                if metric in {"accuracy", "brier"} and value > 1:
                    return False
    return True


def load_forecast_report():
    """Return a public report summary or a useful absence/invalid status.

    The path is configured by the operator, never by a request parameter. The
    endpoint only reads an artifact: it cannot train a model, fetch market data,
    change portfolio policies, or promote a research model into recommendations.
    """
    path = Path(os.getenv("VIBEFINANCE_FORECAST_REPORT", str(STATE_DIR / "forecast/report.json")))
    try:
        if path.stat().st_size > _MAX_REPORT_BYTES:
            return _unavailable("invalid_report")
        report = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
        if not _valid_summary(report):
            return _unavailable("invalid_report")
    except FileNotFoundError:
        return _unavailable("not_generated")
    except (OSError, UnicodeError, ValueError, RecursionError):
        return _unavailable("invalid_report")
    summary = {key: report[key] for key in _PUBLIC_FIELDS}
    summary.update({key: report[key] for key in _OPTIONAL_PUBLIC_FIELDS if key in report})
    # Row-level records belong in the offline artifact, not the interactive API.
    # Strip nested rows too, so a report writer cannot accidentally publish them.
    for period in ("validation", "test"):
        summary[period] = {key: value for key, value in summary[period].items()
                           if key not in {"rows", "test_rows", "validation_rows"}}
    return {"status": "available", **summary, "model_readiness": "research_only"}
