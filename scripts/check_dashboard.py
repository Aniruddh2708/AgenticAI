"""Exercise rendered Streamlit interactions against the running local API."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from streamlit.testing.v1 import AppTest


def button(app, label):
    return next(b for b in app.button if b.label == label)


def assert_clean(app):
    assert not app.exception, [exc.message for exc in app.exception]


def main():
    root = Path(__file__).resolve().parent.parent
    app = AppTest.from_file(str(root / "vibefinance/dashboard.py"), default_timeout=30).run()
    assert_clean(app)
    assert any("ACCUMULATE" in s.value for s in app.subheader)
    button(app, "Compare all three profiles").click().run()
    assert_clean(app)
    labels = {m.label for m in app.metric}
    assert {"BUY", "REDUCE", "ACCUMULATE"} <= labels
    button(app, "Show source passage").click().run()
    assert_clean(app)
    assert len(app.code) >= 1
    button(app, "Save decision").click().run()
    assert_clean(app)
    assert any("Decision saved" in s.value for s in app.success)
    button(app, "Scan personalized watchlist").click().run()
    assert_clean(app)
    for toggle in app.toggle:
        if toggle.label in {"Simulate sentiment feed outage", "Missing filing for ticker"}:
            toggle.set_value(True)
    app.run()
    assert_clean(app)
    assert any("WATCH" in s.value for s in app.subheader)
    assert any("Sentiment feed unavailable" in w.value for w in app.warning)
    assert any("No filing retrieved" in w.value for w in app.warning)
    # Verify conflict and seed outage presentation as separate rendered paths.
    for toggle in app.toggle:
        if toggle.label in {"Simulate sentiment feed outage", "Missing filing for ticker"}:
            toggle.set_value(False)
    next(s for s in app.selectbox if s.label == "NSE ticker").set_value("TCS.NS")
    app.run()
    assert_clean(app)
    assert any("HOLD" in s.value for s in app.subheader)
    assert any("opposes" in w.value for w in app.warning)
    next(s for s in app.selectbox if s.label == "NSE ticker").set_value("ITC.NS")
    app.run()
    assert_clean(app)
    assert any("Sentiment feed unavailable" in w.value for w in app.warning)
    print("Dashboard interactions passed: recommendation, comparison, source passage, decision, watchlist, failure toggles, conflict and seed outage.")


if __name__ == "__main__":
    main()
