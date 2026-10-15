"""Exercise profile editing, plain-language UI and recoverable failures offline.

Uses the real API with an isolated temporary SQLite database. Selected HTTP
failures are injected at the dashboard boundary; successful routes stay real.
No running API server or browser installation is required.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vibefinance.api import create_app
from vibefinance.dashboard import highlighted_document


def widget(elements, label):
    return next(element for element in elements if element.label == label)


def assert_clean(app):
    assert not app.exception, [exception.message for exception in app.exception]


class DashboardAPI:
    def __init__(self, client):
        self.client = client
        self.failures = set()
        self.failed_operations = set()
        self.unsaved = False
        self.calls = []

    def request(self, method, url, **kwargs):
        path = urlsplit(url).path
        self.calls.append((method, path, kwargs.get("json")))
        kwargs.pop("timeout", None)
        if (method, path) in self.failed_operations or any(path.startswith(failure) for failure in self.failures):
            return httpx.Response(503, json={"detail": "Injected service/storage failure"}, request=httpx.Request(method, url))
        response = self.client.request(method, path, **kwargs)
        if self.unsaved and path == "/analyze" and response.is_success:
            session = response.json()
            session["persistence"] = {"status": "failed", "error": "Injected persistence failure"}
            return httpx.Response(200, json=session, request=httpx.Request(method, url))
        return response


def main():
    root = Path(__file__).resolve().parent.parent
    rendered = highlighted_document('before <script>alert("x")</script> cited & text after', 'cited & text')
    assert '<script>' not in rendered and '&lt;script&gt;' in rendered
    assert '<mark>cited &amp; text</mark>' in rendered
    with tempfile.TemporaryDirectory(prefix="vibefinance-dashboard-") as directory:
        with patch.dict(os.environ, {"VIBEFINANCE_API_TOKEN": ""}):
            with TestClient(create_app(Path(directory) / "state.sqlite3")) as client:
                api = DashboardAPI(client)
                with patch("httpx.request", side_effect=api.request):
                    app = AppTest.from_file(str(root / "vibefinance/dashboard.py"), default_timeout=60).run()
                    assert_clean(app)
                    assert any(metric.label == "Evidence strength" and metric.value.endswith("/100") for metric in app.metric)
                    for label in ("Full numbered reasoning", "Agent evidence and latency", "Pipeline trace"):
                        assert any(expander.label == label for expander in app.expander)
                    assert not any(item.value == "Walk-forward technical direction evaluation" for item in app.subheader)

                    # Existing profile edits invalidate analysis and re-run against saved data.
                    before = sum(path == "/analyze" for _, path, _ in api.calls)
                    widget(app.text_input, "Investor name").set_value("Arjun edited in dashboard")
                    widget(app.button, "Save investor profile").click().run()
                    assert_clean(app)
                    assert client.get("/profiles/arjun").json()["name"] == "Arjun edited in dashboard"
                    assert sum(path == "/analyze" for _, path, _ in api.calls) > before
                    assert any("profile saved" in message.value.lower() for message in app.success)

                    # Invalid holdings are explained before issuing a PUT request.
                    saves_before = sum(method == "PUT" for method, _, _ in api.calls)
                    widget(app.text_area, "Equity holdings (%) as JSON").set_value(json.dumps({"RELIANCE.NS": 120}))
                    widget(app.button, "Save investor profile").click().run()
                    assert_clean(app)
                    assert app.error
                    assert sum(method == "PUT" for method, _, _ in api.calls) == saves_before

                    # A failed profile write does not display a saved success state.
                    widget(app.text_area, "Equity holdings (%) as JSON").set_value('{"RELIANCE.NS": 10}')
                    api.failed_operations = {("PUT", "/profiles/arjun")}
                    widget(app.button, "Save investor profile").click().run()
                    assert_clean(app)
                    assert any("save the investor profile" in error.value for error in app.error)
                    api.failed_operations = set()

                    # Create a profile through the dashboard, preserving the seed users.
                    widget(app.radio, "Profile operation").set_value("Create profile").run()
                    widget(app.text_input, "Profile ID").set_value("dashboard_test")
                    widget(app.text_input, "Investor name").set_value("Dashboard test investor")
                    widget(app.text_area, "Equity holdings (%) as JSON").set_value('{"RELIANCE.NS": 10}')
                    widget(app.button, "Save investor profile").click().run()
                    assert_clean(app)
                    assert client.get("/profiles/dashboard_test").status_code == 200

                    # Analyst mode adds technical evaluation; core evidence is available in both views.
                    widget(app.toggle, "Plain-language mode").set_value(False).run()
                    assert_clean(app)
                    assert any(metric.label == "Evidence strength" for metric in app.metric)
                    assert any(expander.label == "Agent evidence and latency" for expander in app.expander)
                    assert any(item.value == "Walk-forward technical direction evaluation" for item in app.subheader)
                    widget(app.button, "Run point-in-time policy replay").click().run()
                    assert_clean(app)
                    assert any(subheader.value == "Full-agent synthetic policy replay" for subheader in app.subheader)
                    widget(app.button, "Measure parallel versus sequential agents").click().run()
                    assert_clean(app)
                    assert any(metric.label == "Measured sequential median" for metric in app.metric)

                    # Failed post-startup routes produce actionable errors, never exceptions.
                    api.failures = {"/evaluation", "/history/"}
                    app.run()
                    assert_clean(app)
                    assert any("evaluation" in error.value for error in app.error)
                    assert any("history" in error.value for error in app.error)
                    for route, label in (("/watchlist", "Scan personalized watchlist"),
                                         ("/compare", "Compare all three profiles"),
                                         ("/evaluation/policies", "Run point-in-time policy replay"),
                                         ("/benchmark", "Measure parallel versus sequential agents")):
                        api.failures = {route}
                        widget(app.button, label).click().run()
                        assert_clean(app)
                        assert any("HTTP 503" in error.value for error in app.error)

                    api.failures = {"/sessions/"}
                    widget(app.button, "Show source passage").click().run()
                    assert_clean(app)
                    assert app.code, "Inline source must remain visible after source endpoint failure"
                    widget(app.button, "Save decision").click().run()
                    assert_clean(app)
                    assert not any("Decision saved" in success.value for success in app.success)

                    # Unsaved sessions expose inline sources and disable decision writes.
                    api.failures = set()
                    api.unsaved = True
                    widget(app.button, "Run analysis").click().run()
                    assert_clean(app)
                    assert widget(app.button, "Save decision").disabled
                    assert any("not been saved" in warning.value for warning in app.warning)
                    calls_before = len(api.calls)
                    widget(app.button, "Show source passage").click().run()
                    assert_clean(app)
                    assert app.code
                    assert not any("/sources/" in path for _, path, _ in api.calls[calls_before:])

                    api.failures = {"/analyze"}
                    widget(app.button, "Run analysis").click().run()
                    assert_clean(app)
                    assert any("run analysis" in error.value for error in app.error)
                    api.failures = {"/profiles"}
                    app.run()
                    assert_clean(app)
                    assert any("load investor profiles" in error.value for error in app.error)
        # Enabling shared protection must gate the dashboard before any API data request.
        with patch.dict(os.environ, {"VIBEFINANCE_API_TOKEN": "dashboard-test-credential"}):
            with TestClient(create_app(Path(directory) / "protected.sqlite3")) as client:
                api = DashboardAPI(client)
                with patch("httpx.request", side_effect=api.request):
                    app = AppTest.from_file(str(root / "vibefinance/dashboard.py"), default_timeout=60).run()
                    assert_clean(app)
                    assert not api.calls, "Protected dashboard must not fetch data before login"
                    widget(app.text_input, "Demo access token").set_value("incorrect")
                    widget(app.button, "Open protected demo").click().run()
                    assert_clean(app)
                    assert not api.calls
                    assert app.error
                    widget(app.text_input, "Demo access token").set_value("dashboard-test-credential")
                    widget(app.button, "Open protected demo").click().run()
                    assert_clean(app)
                    assert any(path == "/profiles" for _, path, _ in api.calls)
                    assert any(subheader.value.startswith("RELIANCE") for subheader in app.subheader)
    print("Extended dashboard checks passed: profile edit/create, cache refresh, input validation, beginner/analyst visibility, safe source highlighting, unsaved sources, disabled decisions, shared-token login and API failure containment.")


if __name__ == "__main__":
    main()
