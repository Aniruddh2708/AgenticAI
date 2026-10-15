"""Render configuration and packaged-report checks; no cloud credentials."""
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from vibefinance import deployment
from vibefinance.api import create_app
from vibefinance.evaluation.forecast_report import load_forecast_report


@pytest.fixture(autouse=True)
def isolated_deployment_settings(monkeypatch):
    for name in ("RENDER", "PORT", "RENDER_GIT_COMMIT", "VIBEFINANCE_DASHBOARD_HOST",
                 "VIBEFINANCE_DASHBOARD_PORT", "VIBEFINANCE_FORECAST_REPORT"):
        monkeypatch.delenv(name, raising=False)


def test_render_binds_platform_port_without_local_override(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("PORT", "10000")
    assert deployment.dashboard_binding() == ("0.0.0.0", 10000)
    monkeypatch.setenv("VIBEFINANCE_DASHBOARD_PORT", "9000")
    assert deployment.dashboard_binding() == ("0.0.0.0", 9000)


def test_local_port_and_interface_remain_loopback(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    assert deployment.dashboard_binding() == ("127.0.0.1", 8501)


@pytest.mark.parametrize("value", ["0", "65536", "invalid"])
def test_invalid_dashboard_ports_fail_before_service_start(monkeypatch, value):
    monkeypatch.setenv("VIBEFINANCE_DASHBOARD_PORT", value)
    with pytest.raises(ValueError): deployment.dashboard_binding()


def test_render_loads_tracked_corrected_research_summary(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    report = load_forecast_report()
    assert report["status"] == "available"
    assert report["test"]["sample_size"] == 80
    assert report["test"]["interval"]["coverage"] == .9125
    assert report["test"]["interval"]["simultaneous_coverage_details"]["complete_forecast_dates"] == 10
    assert report["analysis_status"].startswith("Exploratory")
    assert report["model_readiness"] == "research_only"
    assert report["selection"]["admission"]["passed"] is False
    assert "test_rows" not in report


def test_explicit_report_override_is_preserved_even_when_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("VIBEFINANCE_FORECAST_REPORT", str(tmp_path / "missing.json"))
    assert load_forecast_report()["status"] == "unavailable"


def test_commit_identity_visible_before_private_login_without_api_requests(monkeypatch):
    revision = "abcdef012345" + "0" * 28
    monkeypatch.setenv("RENDER_GIT_COMMIT", revision)
    monkeypatch.setenv("VIBEFINANCE_API_TOKEN", "synthetic-local-test-password")
    def no_api_request(*args, **kwargs):
        pytest.fail("Private API should not be queried before demo login")
    monkeypatch.setattr("httpx.request", no_api_request)
    app = AppTest.from_file("vibefinance/dashboard.py", default_timeout=30).run()
    assert not app.exception
    assert any("Deployed revision: abcdef012345" in caption.value for caption in app.caption)
    assert any(field.label == "Demo access token" for field in app.text_input)


def test_health_exposes_only_valid_public_revision(monkeypatch, tmp_path):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "e0b67fd56d92edfef8b44dc3977f18de81f4da9a")
    with TestClient(create_app(tmp_path / "state.sqlite3")) as client:
        assert client.get("/health").json()["revision"].startswith("e0b67fd")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "invalid-sensitive-value")
    assert deployment.release_revision() is None
