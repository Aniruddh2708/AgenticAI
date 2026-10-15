import json

from fastapi.testclient import TestClient

from vibefinance.api import create_app
from vibefinance.evaluation.development_report import load_development_report


def test_saved_research_report_has_explicit_historical_scope_and_no_promotion():
    report = load_development_report()
    assert report["available"] is True
    assert report["admission"]["passed"] is False
    assert report["new_holdout_evaluated"] is False
    assert report["age_calendar_days"] > 0
    assert report["horizon_observations"] == 30
    assert "models" not in report and "development_rows" not in report


def test_absent_tampered_or_nonfinite_report_fails_without_training(tmp_path):
    path = tmp_path/"report.json"
    assert load_development_report(path)["available"] is False
    path.write_text('{"schema_version": NaN}')
    assert load_development_report(path)["available"] is False
    path.write_text(json.dumps({"schema_version": 2}))
    assert load_development_report(path)["available"] is False


def test_new_research_endpoint_requires_existing_authentication(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBEFINANCE_API_TOKEN", "fixture-only-token")
    monkeypatch.setenv("VIBEFINANCE_EMBEDDINGS", "0")
    with TestClient(create_app(tmp_path/"state.sqlite3")) as client:
        assert client.get("/evaluation/forecast/development").status_code == 401
        response = client.get("/evaluation/forecast/development", headers={"Authorization": "Bearer fixture-only-token"})
        assert response.status_code == 200 and response.json()["available"]
        assert client.get("/history/arjun", headers={"Authorization": "Bearer fixture-only-token"}).json() == []
