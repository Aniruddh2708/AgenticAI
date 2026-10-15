"""Exercise default-view explanations against actual analysis and saved-report routes."""
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from vibefinance.api import create_app


def widget(elements, label):
    return next(element for element in elements if element.label == label)


def rendered_text(app):
    return "\n".join(item.value for item in app.markdown)


@pytest.fixture
def dashboard(monkeypatch, tmp_path):
    monkeypatch.setenv("VIBEFINANCE_API_TOKEN", "")
    monkeypatch.setenv("VIBEFINANCE_EMBEDDINGS", "0")
    monkeypatch.setenv("VIBEFINANCE_FORECAST_REPORT", str(
        Path(__file__).resolve().parents[1] / "docs/assets/forecast-followup-summary.json"))
    calls = []
    with TestClient(create_app(tmp_path / "state.sqlite3")) as client:
        def request(method, url, **kwargs):
            path = urlsplit(url).path
            calls.append((method, path))
            kwargs.pop("timeout", None)
            return client.request(method, path, **kwargs)

        monkeypatch.setattr("httpx.request", request)
        app = AppTest.from_file("vibefinance/dashboard.py", default_timeout=60).run()
        assert not app.exception
        yield app, calls


def test_plain_language_view_exposes_actual_reasoning_evidence_and_trace(dashboard):
    app, _ = dashboard
    assert widget(app.toggle, "Plain-language mode").value is True
    session = app.session_state["analysis"]
    recommendation = session["recommendation"]
    strength = widget(app.metric, "Evidence strength")
    assert strength.value == f"{100 * recommendation['confidence']:.0f}/100"
    assert any("not a calibrated probability of profit or of a correct action" in caption.value
               for caption in app.caption)
    expanders = {expander.label for expander in app.expander}
    assert {"Full numbered reasoning", "Agent evidence and latency", "Pipeline trace"} <= expanders
    text = rendered_text(app)
    for step in recommendation["reasoning_chain"]:
        assert step in text
    for agent in recommendation["agent_outputs"]:
        for evidence in agent["evidence"]:
            assert evidence in text
    for step in session["trace"]:
        assert step["detail"] in text
    assert any("Filings/news are fabricated" in caption.value for caption in app.caption)


def test_portfolio_override_remains_distinct_from_missing_market_evidence(dashboard):
    app, _ = dashboard
    widget(app.selectbox, "Investor").set_value("meera")
    widget(app.selectbox, "NSE ticker").set_value("ITC.NS")
    widget(app.toggle, "Missing filing for ticker").set_value(True).run()
    assert not app.exception
    rec = app.session_state["analysis"]["recommendation"]
    assert rec["action"] == "REDUCE"
    assert rec["decision_basis"] == "portfolio_policy"
    assert "single_stock_limit" in rec["policy_rules"]
    assert any(caption.value == "Decision basis: portfolio safeguards." for caption in app.caption)
    assert any("No filing retrieved" in warning.value for warning in app.warning)
    assert "makes no claim about future price direction" in rendered_text(app)


def test_saved_audit_is_rendered_and_survives_a_later_page_rerun(dashboard):
    app, calls = dashboard
    widget(app.button, "Load real-history forecast audit").click().run()
    assert not app.exception
    assert sum(path == "/evaluation/forecast" for _, path in calls) == 1
    assert any(heading.value == "Real-history price forecasting research" for heading in app.subheader)
    text = rendered_text(app)
    assert "N = 80" in text
    assert "91.25%" in text
    assert "failed" in text
    assert any("now spent" in caption.value for caption in app.caption)
    assert any("research only" in caption.value.lower() for caption in app.caption)
    app.run()
    assert not app.exception
    assert any(heading.value == "Real-history price forecasting research" for heading in app.subheader)
    assert sum(path == "/evaluation/forecast" for _, path in calls) == 1
