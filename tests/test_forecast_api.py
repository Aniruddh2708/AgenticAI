"""A saved forecast audit must remain read-only, honest about absence, and private."""

import copy
import json
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from vibefinance.api import create_app
from vibefinance.evaluation import forecast_report


@pytest.fixture(autouse=True)
def local_configuration(monkeypatch):
    monkeypatch.delenv("VIBEFINANCE_API_TOKEN", raising=False)
    monkeypatch.delenv("VIBEFINANCE_FORECAST_REPORT", raising=False)
    monkeypatch.setenv("VIBEFINANCE_EMBEDDINGS", "0")


@pytest.fixture
def saved_report(tmp_path, monkeypatch):
    report = {
        "schema_version": 1,
        "kind": "historical_price_forecast",
        "model_readiness": "production",  # An artifact cannot promote the model.
        "protocol": {"train_end": "2018-12-31", "validation_start": "2019-01-01",
                     "validation_end": "2020-12-31", "test_start": "2021-01-01",
                     "test_end": "2022-12-31", "horizon_sessions": 30},
        "data": [{"ticker": "SYNTHETIC_TEST_FIXTURE", "source": "endpoint contract fixture"}],
        "validation": {"sample_size": 10, "metrics": {"prior": {"brier": .26}}},
        "test": {"sample_size": 5, "as_of_start": "2021-01-04", "as_of_end": "2022-11-01",
                 "target_end": "2022-12-13", "metrics": {
                     "prior": {"brier": .27, "log_loss": .75, "accuracy": .4},
                     "ridge": {"mae_return": .08, "rmse_return": .10}},
                 "calibration": [], "uncertainty": {}, "rows": [{"private": "row-level record"}]},
        "selection": {"probability_model": "prior", "return_model": "ridge",
                      "admission": {"passed": False, "reason": "Did not beat baseline."}},
        "limitations": ["Endpoint contract fixture, not real performance evidence."],
        "test_rows": [{"private": "row-level record"}],
        "internal_path": "/private/operator/path",
        "model_id": "fixture-model-fingerprint",
        "selection_id": "fixture-selection-fingerprint",
        "evaluated_at_utc": "2023-01-01T00:00:00+00:00",
        "runtime": {"python": "3.11.0"},
        "features": ["return_20"],
        "calibration": {"sample_size": 10, "method": "fixture"},
    }
    path = tmp_path / "saved-report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setenv("VIBEFINANCE_FORECAST_REPORT", str(path))
    return path, report


@pytest.fixture
def saved_followup_report(tmp_path, monkeypatch, saved_report):
    _, original = saved_report
    report = copy.deepcopy(original)
    report.update(
        experiment_version=2,
        period_status="2024-2025 evaluated once and now spent; subsequent analysis is exploratory",
        horizon_definition="30 observed positive-volume vendor rows",
        development_status="2019-2020 is spent development data",
        original_selection_id="original-selection-fingerprint",
        analysis_status="Exploratory correction from saved predictions; no refit or row changes",
        data_quality={"finding": "Contract fixture: vendor calendars differ across securities"},
        correction={"method": "Complete declared security origins only; partial groups excluded and counted"},
    )
    report["protocol"].update(test_start="2024-01-01", test_end="2025-12-31")
    report["selection"] = {
        "probability_model": "prior", "return_model": "mean",
        "admission": {"passed": False, "reason": "Baseline retained; no feature-model superiority established."},
    }
    interval = {"coverage": .95, "nominal_coverage": .9, "mean_width": .2,
                "simultaneous_coverage_details": {"coverage": .6, "complete_forecast_dates": 10,
                    "excluded_partial_forecast_dates": 12, "calendar_quarters": 5},
                "interval_score": .3, "uncertainty": {
                    "coverage": {"estimate": .95, "low": .8, "high": 1.0,
                                 "method": "Contract fixture, not real performance evidence"}}}
    report["test"].update(as_of_start="2024-01-02", as_of_end="2025-11-01",
                          target_end="2025-12-15", primary_interval_method="security_vol_scaled",
                          interval=interval, intervals={
                              "selected": {"security_vol_scaled": interval},
                              "prior_mean": {"security_vol_scaled": copy.deepcopy(interval)}})
    path = tmp_path / "saved-followup-report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setenv("VIBEFINANCE_FORECAST_REPORT", str(path))
    return path, report


def test_missing_report_is_useful_without_fabricated_metrics_or_created_files(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    monkeypatch.setattr(forecast_report, "STATE_DIR", state_dir)
    with TestClient(create_app(tmp_path / "api.sqlite3")) as client:
        response = client.get("/evaluation/forecast")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "unavailable"
    assert result["reason"] == "not_generated"
    assert result["model_readiness"] == "research_only"
    assert "test" not in result and "metrics" not in result
    assert not state_dir.exists()
    assert str(tmp_path) not in response.text


def test_saved_audit_exposes_summary_without_rows_or_promotion(tmp_path, saved_report):
    path, original = saved_report
    before = path.read_bytes()
    with TestClient(create_app(tmp_path / "api.sqlite3")) as client:
        response = client.get("/evaluation/forecast")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "available"
    assert result["model_readiness"] == "research_only"
    assert result["test"]["metrics"] == original["test"]["metrics"]
    assert result["test"]["sample_size"] == 5
    assert result["selection"]["admission"]["passed"] is False
    assert "test_rows" not in result and "rows" not in result["test"]
    assert "internal_path" not in result
    assert "private" not in response.text
    for key in ("model_id", "selection_id", "evaluated_at_utc", "runtime", "features", "calibration"):
        assert result[key] == original[key]
    assert path.read_bytes() == before


def test_followup_summary_keeps_spent_period_metadata_and_original_artifact(tmp_path, monkeypatch, saved_report, saved_followup_report):
    original_path, original = saved_report
    before = original_path.read_bytes()
    followup_path, report = saved_followup_report
    with TestClient(create_app(tmp_path / "api.sqlite3")) as client:
        result = client.get("/evaluation/forecast").json()
        for key in ("experiment_version", "period_status", "horizon_definition", "development_status",
                    "original_selection_id", "analysis_status", "data_quality", "correction"):
            assert result[key] == report[key]
        assert result["status"] == "available"
        assert result["model_readiness"] == "research_only"
        assert result["selection"]["probability_model"] == "prior"
        assert result["selection"]["admission"]["passed"] is False
        assert result["test"]["interval"] == report["test"]["interval"]
        assert result["test"]["intervals"] == report["test"]["intervals"]
        assert "rows" not in result["test"] and "test_rows" not in result
        monkeypatch.setenv("VIBEFINANCE_FORECAST_REPORT", str(original_path))
        restored = client.get("/evaluation/forecast").json()
        assert restored["test"]["metrics"] == original["test"]["metrics"]
        assert "experiment_version" not in restored
    assert original_path.read_bytes() == before
    assert followup_path.exists()


@pytest.mark.parametrize("content", ["{malformed", "[]", "\ufeff{}", "{\"score\": NaN}"])
def test_unreadable_or_malformed_report_has_no_sensitive_error_details(tmp_path, monkeypatch, content):
    path = tmp_path / "private-sensitive-file-name.json"
    path.write_text(content, encoding="utf-8")
    monkeypatch.setenv("VIBEFINANCE_FORECAST_REPORT", str(path))
    with TestClient(create_app(tmp_path / "api.sqlite3")) as client:
        response = client.get("/evaluation/forecast")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["reason"] == "invalid_report"
    assert "private-sensitive" not in response.text
    assert str(tmp_path) not in response.text
    assert "metrics" not in response.json()


@pytest.mark.parametrize("mutation", [
    lambda report: report.update(schema_version=2),
    lambda report: report.update(schema_version=True),
    lambda report: report.update(kind="simulated_evaluation"),
    lambda report: report.update(data={}),
    lambda report: report.update(limitations="Unsupported claim"),
    lambda report: report["selection"].update(admission={"passed": "yes", "reason": "Invalid"}),
    lambda report: report["test"].update(sample_size=True),
    lambda report: report["test"].update(sample_size=-1),
    lambda report: report["test"].update(metrics=[]),
    lambda report: report["test"]["metrics"]["prior"].update(brier=-.1),
    lambda report: report["test"]["metrics"]["prior"].update(brier=1.1),
    lambda report: report["test"]["metrics"]["prior"].update(accuracy="high"),
    lambda report: report["test"]["metrics"]["ridge"].update(mae_return=float("inf")),
    lambda report: report["test"].update(interval=[]),
    lambda report: report["test"].update(interval={"coverage": "high"}),
    lambda report: report["test"].update(interval={"nominal_coverage": 1.1}),
    lambda report: report["test"].update(interval={"mean_width": -.1}),
    lambda report: report["test"].update(interval={"interval_score": True}),
    lambda report: report["test"].update(intervals=[]),
    lambda report: report["test"].update(intervals={"selected": []}),
    lambda report: report["test"].update(intervals={"selected": {"scaled": {"coverage": -.1}}}),
    lambda report: report["test"].update(interval={"simultaneous_coverage_details": []}),
    lambda report: report["test"].update(interval={"simultaneous_coverage_details": {"coverage": 1.1}}),
    lambda report: report["test"].update(interval={"simultaneous_coverage_details": {"complete_forecast_dates": -1}}),
])
def test_unsupported_or_invalid_schema_returns_unavailable(saved_report, mutation):
    path, original = saved_report
    report = copy.deepcopy(original)
    mutation(report)
    path.write_text(json.dumps(report), encoding="utf-8")
    result = forecast_report.load_forecast_report()
    assert result["status"] == "unavailable"
    assert result["reason"] == "invalid_report"
    assert "test" not in result


def test_default_report_location_works_without_environment_override(tmp_path, saved_report, monkeypatch):
    _, original = saved_report
    monkeypatch.delenv("VIBEFINANCE_FORECAST_REPORT")
    monkeypatch.setattr(forecast_report, "STATE_DIR", tmp_path)
    path = tmp_path / "forecast" / "report.json"
    path.parent.mkdir()
    path.write_text(json.dumps(original), encoding="utf-8")
    assert forecast_report.load_forecast_report()["status"] == "available"


def test_forecast_audit_preserves_optional_bearer_authentication(tmp_path, monkeypatch, saved_report):
    monkeypatch.setenv("VIBEFINANCE_API_TOKEN", "synthetic-test-token")
    with TestClient(create_app(tmp_path / "api.sqlite3")) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/evaluation/forecast").status_code == 401
        assert client.get("/evaluation/forecast", headers={"Authorization": "Bearer wrong"}).status_code == 401
        response = client.get("/evaluation/forecast", headers={"Authorization": "Bearer synthetic-test-token"})
        assert response.status_code == 200
        assert response.json()["status"] == "available"


@pytest.mark.parametrize("available", [False, True])
def test_dashboard_audit_load_is_explicit_and_handles_saved_or_missing_report(tmp_path, monkeypatch, saved_report, available):
    if not available:
        monkeypatch.setenv("VIBEFINANCE_FORECAST_REPORT", str(tmp_path / "absent.json"))
    calls = []
    with TestClient(create_app(tmp_path / "dashboard.sqlite3")) as client:
        def request(method, url, **kwargs):
            calls.append((method, urlsplit(url).path))
            kwargs.pop("timeout", None)
            return client.request(method, urlsplit(url).path, **kwargs)

        monkeypatch.setattr("httpx.request", request)
        app = AppTest.from_string(
            "from vibefinance.dashboard import render_forecast_audit\nrender_forecast_audit()",
            default_timeout=30,
        ).run()
        assert not app.exception
        assert calls == []
        next(button for button in app.button if button.label == "Load real-history forecast audit").click().run()
        assert not app.exception
        assert calls == [("GET", "/evaluation/forecast")]
        if available:
            assert app.dataframe
            assert any("failed" in element.value for element in app.markdown)
            assert any("Recorded evaluation period: 2021-01-04" in element.value and "N = 5" in element.value for element in app.markdown)
            assert any("period is now spent" in element.value for element in app.caption)
            assert not any("Untouched" in element.value for element in app.markdown)
        else:
            assert not app.dataframe
            assert any("No saved real-history forecast audit" in element.value for element in app.info)


def test_dashboard_followup_shows_interval_tradeoffs_and_baseline_without_promotion(tmp_path, monkeypatch, saved_followup_report):
    with TestClient(create_app(tmp_path / "dashboard.sqlite3")) as client:
        def request(method, url, **kwargs):
            kwargs.pop("timeout", None)
            return client.request(method, urlsplit(url).path, **kwargs)

        monkeypatch.setattr("httpx.request", request)
        app = AppTest.from_string(
            "from vibefinance.dashboard import render_forecast_audit\nrender_forecast_audit()",
            default_timeout=30,
        ).run()
        next(button for button in app.button if button.label == "Load real-history forecast audit").click().run()
    assert not app.exception
    rendered = " ".join(element.value for element in app.markdown)
    assert "Recorded evaluation period: 2024-01-02" in rendered
    assert "Observed return-interval coverage:" in rendered and "95.00%" in rendered
    assert "Nominal coverage target:" in rendered and "90.00%" in rendered
    assert "Mean interval width:" in rendered and "20.00 return percentage points" in rendered
    assert "Interval score:" in rendered and "30.00 return percentage points" in rendered
    assert "Baseline retained; no feature-model superiority established." in rendered
    assert "Selected probability model:" in rendered and "prior" in rendered
    assert "Selected return model:" in rendered and "mean" in rendered
    assert "Primary interval simultaneous security coverage:" in rendered and "60.00%" in rendered
    assert "Complete forecast dates:" in rendered and "10" in rendered
    assert "excluded partial forecast dates:" in rendered and "12" in rendered
    assert "calendar quarters:" in rendered and "5" in rendered
    captions = " ".join(element.value for element in app.caption)
    assert "spent" in captions and "exploratory" in captions
    assert "same calibration dates" in captions and "simultaneous coverage" in captions
    assert "Wider intervals can increase coverage" in captions
    assert "Exploratory correction from saved predictions; no refit or row changes" in captions
    assert "These scores have been reported and inspected" in captions
    assert "Partial groups are excluded and counted" in captions
    assert "research only" in captions
    assert "Untouched" not in rendered
    comparisons = app.dataframe[1].value
    assert set(comparisons["Point method"]) == {"selected", "prior_mean"}
    assert comparisons["Observed coverage (%)"].tolist() == [95.0, 95.0]
    assert app.json
