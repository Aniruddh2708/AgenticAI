"""Render runtime defaults and public, non-secret release identity."""
import os
from pathlib import Path
import re


def on_render():
    return os.getenv("RENDER", "").lower() == "true"


def dashboard_binding():
    host = os.getenv("VIBEFINANCE_DASHBOARD_HOST", "0.0.0.0" if on_render() else "127.0.0.1")
    port = os.getenv("VIBEFINANCE_DASHBOARD_PORT")
    if port is None:
        port = os.getenv("PORT", "8501") if on_render() else "8501"
    number = int(port)
    if not 1 <= number <= 65535:
        raise ValueError("Dashboard port must be between 1 and 65535")
    return host, number


def release_revision():
    revision = os.getenv("RENDER_GIT_COMMIT", "").lower()
    return revision if re.fullmatch(r"[0-9a-f]{7,40}", revision) else None


def forecast_report_path(state_dir):
    configured = os.getenv("VIBEFINANCE_FORECAST_REPORT")
    if configured is not None:
        return Path(configured)
    if on_render():
        # This tracked summary ships with native builds and both Docker recipes.
        # No training, raw-data download or ignored workstation state is needed.
        return Path(__file__).resolve().parent.parent / "docs/assets/forecast-followup-summary.json"
    return Path(state_dir) / "forecast/report.json"
