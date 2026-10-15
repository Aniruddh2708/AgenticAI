"""Read a saved, historical development report without training or promotion."""
import json
import os
from datetime import date
from pathlib import Path

from vibefinance.data.quality import digest


def load_development_report(path=None):
    path = Path(path or os.getenv("VIBEFINANCE_DEVELOPMENT_REPORT") or
                Path(__file__).resolve().parents[2]/"docs/assets/forecast-development-v2-summary.json")
    try:
        if path.stat().st_size > 2_000_000:
            raise ValueError("Oversized report")
        report = json.loads(path.read_text(), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite report")))
        if (report["schema_version"] != 2 or report["kind"] != "forecast_development" or
                report["status"] != "exploratory_development_only" or
                report["model_id"] != digest(report["selection"]) or
                report["admission"]["passed"] is not False or
                report["selection"]["protocol_sha256"] != digest(report["protocol"])):
            raise ValueError("Invalid report identity or unsupported promotion")
        as_of = date.fromisoformat(report["as_of"])
        # Return an explicit whitelist: no source rows, filesystem paths or
        # serialized model coefficients belong in an application report.
        keys = ("kind", "status", "model_id", "as_of", "data_freshness", "development", "calibration_scope",
                "prequential_intervals", "admission", "limitations")
        result = {key: report[key] for key in keys}
        result.update(available=True, age_calendar_days=(date.today()-as_of).days,
            horizon_observations=30, probability_model=report["selection"]["probability_selection"]["chosen"],
            return_model=report["selection"]["return_selection"]["chosen"],
            portfolio_actions_changed=False, new_holdout_evaluated=False)
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return {"available": False, "status": "unavailable", "portfolio_actions_changed": False,
                "reason": "Saved development report is absent or invalid; no training or forecast was performed."}
