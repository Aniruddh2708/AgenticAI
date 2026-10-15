import hashlib
import hmac
import html
import json
import math
import os
import time
from urllib.parse import quote, unquote

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from vibefinance.config import DISCLAIMER, TICKERS
from vibefinance.data.market_sim import generate_market
from vibefinance.deployment import release_revision
from vibefinance.auth import (
    AuthenticationError, AuthConfigurationError, AuthSession, AuthSettings,
    SupabaseAuth, dashboard_authorization, verified_dashboard_identity,
)

API = os.getenv("VIBEFINANCE_API_URL", "http://127.0.0.1:8000").rstrip("/")


def call(method, path, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    settings = AuthSettings.from_env()
    if settings.mode == "supabase":
        session = require_account_login(settings)
        headers["Authorization"] = "Bearer " + session.access_token
    elif settings.mode == "oidc":
        require_oidc_login(settings)
        headers["Authorization"] = dashboard_authorization(
            st.user, settings, method=method.upper(), path=unquote(path))
    elif token := os.getenv("VIBEFINANCE_API_TOKEN"):
        headers["Authorization"] = "Bearer " + token
    response = httpx.request(method, API + path, timeout=60, headers=headers, **kwargs)
    response.raise_for_status()
    return response.json()


def request_or_error(method, path, purpose, **kwargs):
    """Contain each API failure, including interactions after initial startup."""
    try:
        return call(method, path, **kwargs)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = ""
        try:
            body = exc.response.json()
            if isinstance(body, dict) and isinstance(body.get("detail"), str):
                detail = " " + body["detail"][:300]
        except (ValueError, TypeError):
            pass
        if status in {401, 403} and AuthSettings.from_env().mode != "demo":
            clear_account_state()
            st.session_state.account_notice = "Your sign-in could not be authorized. Sign in again."
            st.rerun()
        advice = (" Configure the same VIBEFINANCE_API_TOKEN for the API and dashboard."
                  if status in {401, 403} else " Check the API logs, correct the input or restore storage, then retry.")
        st.error(f"Could not {purpose} (HTTP {status}).{detail}{advice}")
    except httpx.TimeoutException:
        st.error(f"Could not {purpose}: the API timed out. Check the API logs and retry.")
    except httpx.HTTPError:
        st.error(f"Could not {purpose}: API connection failed. Start both services with `make demo` and check VIBEFINANCE_API_URL.")
    except (ValueError, TypeError):
        st.error(f"Could not {purpose}: the API returned an invalid response. Check API logs and matching application versions.")
    return None


def profile_signature(profile):
    return hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()


def clear_profile_results():
    for key in ("analysis", "analysis_key", "watchlist", "watchlist_key", "comparison", "comparison_key"):
        st.session_state.pop(key, None)


def clear_account_state():
    """Forget every account's results, form values and credentials on transition."""
    for key in list(st.session_state):
        st.session_state.pop(key, None)


@st.cache_resource
def account_auth_client(settings):
    """Share only a stateless public-config client and its bounded signing keys."""
    return SupabaseAuth(settings)


def bind_account(principal, session=None):
    previous = st.session_state.get("individual_account")
    if previous != principal.account_id:
        clear_account_state()
    st.session_state.individual_account = principal.account_id
    if session is not None:
        st.session_state.individual_session = session
    return previous is not None and previous != principal.account_id


def submit_account_login(operation):
    # Callback runs before the next page render. Remove the password before the
    # provider call, including rejected credentials and provider outages.
    password = st.session_state.pop("account_password", "")
    email = st.session_state.get("account_email", "").strip()
    try:
        settings = AuthSettings.from_env()
        if settings.mode != "supabase":
            raise AuthenticationError("Individual sign-in is unavailable.")
        client = account_auth_client(settings)
        session = client.sign_up(email, password) if operation == "sign_up" else client.sign_in(email, password)
        if session is None:
            clear_account_state()
            st.session_state.account_notice = "Check your email for a confirmation link, then return here to sign in. An active account has not been confirmed."
        else:
            client.validate_session(session)
            bind_account(session.principal, session)
    except Exception:
        clear_account_state()
        st.session_state.account_notice = "Sign-in could not be completed. Check your credentials or confirmation email and retry. New accounts need a password of at least 12 characters."
    finally:
        password = None
        st.session_state.pop("account_password", None)


def logout_account():
    """Local logout succeeds even when the identity provider is unavailable."""
    session = st.session_state.get("individual_session")
    clear_account_state()
    try:
        settings = AuthSettings.from_env()
        if settings.mode == "supabase" and isinstance(session, AuthSession):
            account_auth_client(settings).sign_out(session.access_token)
        elif settings.mode == "oidc":
            st.logout()
    except Exception:
        st.session_state.account_notice = "Signed out of this app. The identity provider could not confirm remote sign-out; close this browser session if using a shared device."


def require_account_login(settings, *, controls=False):
    session = st.session_state.get("individual_session")
    if session is not None:
        try:
            client = account_auth_client(settings)
            if not isinstance(session, AuthSession):
                raise AuthenticationError("Sign in again.")
            if session.expires_at - time.time() <= 30:
                renewed = client.refresh(session.refresh_token)
                verified = client.validate_session(renewed)
                if (verified.account_id != session.principal.account_id
                        or renewed.expires_at - time.time() <= 30):
                    raise AuthenticationError("Sign in again.")
                session, principal = renewed, verified
            else:
                principal = client.validate_session(session)
            if bind_account(principal, session):
                st.rerun()
        except Exception:
            clear_account_state()
            st.session_state.account_notice = "Your sign-in expired or could not be verified. Sign in again."
            # Full rerun also removes any old account data outside a fragment.
            st.rerun()
        if controls:
            with st.sidebar:
                st.caption("Personal account · profiles and history are private to your sign-in.")
                st.button("Sign out", on_click=logout_account)
        return session
    if st.session_state.get("individual_account"):
        clear_account_state()
        st.rerun()
    if notice := st.session_state.pop("account_notice", None):
        st.info(notice)
    st.info("Sign in to your personal account. Your investor profiles and history are separate from other accounts.")
    st.caption("Analysis still uses the disclosed demo market inputs and synthetic company documents. A personal account does not establish forecasting accuracy.")
    with st.form("account-login", clear_on_submit=True):
        st.text_input("Email", key="account_email")
        st.text_input("Password", type="password", key="account_password")
        st.form_submit_button("Sign in", on_click=submit_account_login, args=("sign_in",))
        st.form_submit_button("Create free account", on_click=submit_account_login, args=("sign_up",))
    st.stop()


def require_oidc_login(settings, *, controls=False):
    try:
        principal = verified_dashboard_identity(st.user, settings)
    except AuthenticationError:
        had_account = bool(st.session_state.get("individual_account"))
        clear_account_state()
        if had_account:
            st.rerun()
        if st.user.get("is_logged_in") is True:
            st.info("Your sign-in expired or could not be verified. Sign in again.")
            try:
                st.logout()
            except Exception:
                st.error("Sign-out could not be completed. Close this browser session before signing in again.")
            st.stop()
        st.info("Sign in to access your personal investor profiles and history.")
        if st.button("Sign in with your account"):
            st.login("oidc")
        st.stop()
    if bind_account(principal):
        st.rerun()
    if controls:
        with st.sidebar:
            st.caption("Personal account · profiles and history are private to your sign-in.")
            st.button("Sign out", on_click=logout_account)
    return principal


def require_demo_login(*, controls=True):
    """Retain the demo entry point while failing closed in account modes."""
    try:
        settings = AuthSettings.from_env()
    except AuthConfigurationError:
        had_account = bool(st.session_state.get("individual_account") or st.session_state.get("individual_session"))
        clear_account_state()
        if had_account:
            st.rerun()
        st.error("Account configuration is unavailable. Ask the operator to check the authentication settings.")
        st.stop()
    if settings.mode == "supabase":
        require_account_login(settings, controls=controls)
        return
    if settings.mode == "oidc":
        require_oidc_login(settings, controls=controls)
        return
    if st.session_state.get("individual_account") or st.session_state.get("individual_session"):
        clear_account_state()
    token = os.getenv("VIBEFINANCE_API_TOKEN")
    if not token:
        return
    fingerprint = hashlib.sha256(token.encode()).hexdigest()
    if st.session_state.get("demo_authentication") == fingerprint:
        st.session_state.pop("demo_login_secret", None)
        return
    st.info("This demo requires its access token. Ask the operator for access; do not use a GitHub token or personal API key.")
    st.caption("Shared demo access is not a personal account or per-user privacy boundary. Authorized viewers can see the demo investor profiles.")
    with st.form("demo-login"):
        entered = st.text_input("Demo access token", type="password", key="demo_login_secret")
        submitted = st.form_submit_button("Open protected demo")
    if submitted:
        if hmac.compare_digest(entered.encode(), token.encode()):
            st.session_state.demo_authentication = fingerprint
            st.rerun()
        else:
            st.error("Access token does not match. Check with the demo operator and retry.")
    st.stop()


def render_profile_form(profile, profiles):
    with st.expander("Create or edit an investor profile"):
        create = st.radio("Profile operation", ["Edit selected investor", "Create profile"], horizontal=True) == "Create profile"
        current = {} if create else (profile or {})
        if not create and not current:
            st.info("Choose Create profile to add your first investor.")
            return
        form_key = "profile-form-" + ("new" if create else current["user_id"])
        with st.form(form_key):
            user_id = st.text_input("Profile ID", value=current.get("user_id", ""), disabled=not create,
                                    help="Use a unique short identifier such as demo_investor.")
            name = st.text_input("Investor name", value=current.get("name", ""))
            tolerances = ["conservative", "moderate", "aggressive"]
            tolerance = st.selectbox("Risk tolerance", tolerances, index=tolerances.index(current.get("risk_tolerance", "moderate")))
            horizon = st.number_input("Investment horizon (months)", min_value=1, max_value=600,
                                      value=int(current.get("horizon_months", 36)))
            limit = st.number_input("Maximum single-stock allocation (%)", min_value=0.0, max_value=100.0,
                                    value=float(current.get("max_single_stock_pct", .25) * 100), step=1.0)
            holdings_text = st.text_area("Equity holdings (%) as JSON", value=json.dumps(
                {ticker: round(weight * 100, 6) for ticker, weight in current.get("holdings", {}).items() if ticker != "CASH"}, indent=2),
                help='Example: {"RELIANCE.NS": 10, "TCS.NS": 15}. Total must be at most 100; the remainder is cash.')
            behavior = current.get("behavior", {})
            panic = st.number_input("Prior panic sells", min_value=0, value=int(behavior.get("panic_sell_count", 0)))
            days = st.number_input("Average holding period (days)", min_value=0, value=int(behavior.get("avg_hold_days", 180)))
            chasing = st.checkbox("Often chase momentum", value=bool(behavior.get("chases_momentum", False)))
            submitted = st.form_submit_button("Save investor profile")
        if submitted:
            try:
                if not user_id.strip() or not name.strip():
                    raise ValueError("Profile ID and investor name are required.")
                if limit <= 0:
                    raise ValueError("Maximum single-stock allocation must be greater than zero.")
                if create and user_id.strip() in {p["user_id"] for p in profiles}:
                    raise ValueError("That profile ID already exists. Use Edit selected investor or choose a different ID.")
                percentages = json.loads(holdings_text)
                if not isinstance(percentages, dict):
                    raise ValueError("Holdings must be a JSON object mapping tickers to percentages.")
                for symbol, weight in percentages.items():
                    if symbol not in TICKERS:
                        raise ValueError(f"Use one of the supported demo tickers: {', '.join(TICKERS)}.")
                    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or not 0 <= weight <= 100:
                        raise ValueError("Each equity weight must be a finite percentage from 0 to 100.")
                if sum(percentages.values()) > 100.000001:
                    raise ValueError("Equity holdings cannot total more than 100%; the remainder is cash.")
                payload = {"user_id": user_id.strip(), "name": name.strip(), "risk_tolerance": tolerance,
                           "horizon_months": int(horizon), "holdings": {s: w / 100 for s, w in percentages.items()},
                           "max_single_stock_pct": limit / 100, "behavior": {
                               **behavior, "panic_sell_count": int(panic), "avg_hold_days": int(days), "chases_momentum": chasing}}
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
            else:
                saved = request_or_error("PUT", "/profiles/" + quote(payload["user_id"], safe=""), "save the investor profile", json=payload)
                if saved is not None:
                    clear_profile_results()
                    st.session_state.profile_saved = True
                    st.rerun()


def signal_table(session, beginner=False):
    readable = {"BULLISH": "Price trend is positive", "BEARISH": "Price trend is negative",
                "NEUTRAL": "No clear direction", "POSITIVE": "Available text tone is positive",
                "NEGATIVE": "Available text tone is negative", "MIXED": "No clear text tone",
                "SUPPORTIVE": "Filings have supportive facts",
                "CAUTIONARY": "Filings contain risks", "SPIKE_UP": "Trading participation increased",
                "DIVERGENCE": "Price and participation disagree", "RISK_LOW": "Lower portfolio risk",
                "RISK_MED": "Review portfolio exposure", "RISK_HIGH": "Portfolio limits need attention",
                "UNKNOWN": "Evidence unavailable"}
    if beginner:
        rows = [{"Dimension": a["dimension"].title(), "Assessment": readable.get(a["label"], a["label"].replace("_", " ").title()),
                 "Availability": "Available" if a["status"] == "ok" else "Limited"} for a in session["recommendation"]["agent_outputs"]]
        st.dataframe(rows, hide_index=True, use_container_width=True)
        return
    rows = [{"Dimension": a["dimension"].title(), "Signal": a["label"],
             "Confidence": a["confidence"], "Status": a["status"]} for a in session["recommendation"]["agent_outputs"]]
    colors = {"BULLISH": "#c8e6c9", "POSITIVE": "#c8e6c9", "SUPPORTIVE": "#c8e6c9", "SPIKE_UP": "#c8e6c9",
              "BEARISH": "#ffcdd2", "NEGATIVE": "#ffcdd2", "CAUTIONARY": "#ffcdd2", "RISK_HIGH": "#ffcdd2"}
    style = pd.DataFrame(rows).style.map(lambda value: f"background-color: {colors.get(value, '#fff3cd')}; color: #151515", subset=["Signal"])
    st.dataframe(style, hide_index=True, use_container_width=True,
                 column_config={"Confidence": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1)})


def highlighted_document(document, excerpt):
    """Only our fixed markup is HTML; escape document text and every cited span."""
    parts = document.split(excerpt) if excerpt else [document]
    highlighted = ("<mark>" + html.escape(excerpt) + "</mark>").join(html.escape(part) for part in parts)
    return '<div style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:32rem;overflow:auto">' + highlighted + "</div>"


def session_saved(session):
    return session.get("persistence", {"status": "saved"})["status"] == "saved"


def render_sources(session, beginner=False):
    st.caption("Filings/news are fabricated. Market and profile citations are input snapshots, not external documents. Source identity does not establish the truth of a company claim.")
    inline = {source["chunk_id"]: source for source in session.get("sources", [])}
    for citation in session["recommendation"]["citations"]:
        with st.expander(citation["doc_title"]):
            caption = f"{citation['source_id']} · {citation['date']}"
            if not beginner:
                caption += f" · retrieval relevance {citation['score']:.3f} (not a probability)"
            st.caption(caption)
            st.write(citation["excerpt"])
            source_key = f"{session['session_id']}:{citation['chunk_id']}"
            if st.button("Show source passage", key="passage-" + source_key):
                source = inline.get(citation["chunk_id"])
                if session_saved(session):
                    remote = request_or_error("GET", f"/sessions/{session['session_id']}/sources/{quote(citation['chunk_id'], safe='')}", "load the saved source passage")
                    source = remote or source
                if source is None:
                    st.error("This source is unavailable. Run analysis again after retrieval and storage recover.")
                else:
                    st.session_state.setdefault("opened_sources", {})[source_key] = source
            source = st.session_state.get("opened_sources", {}).get(source_key)
            if source:
                st.markdown("**Exact registered source passage**")
                st.code(source["excerpt"], language=None)
                st.success("Displayed excerpt matches the session source registry.")
                document = source.get("document_text")
                if document:
                    st.markdown("**Source document — cited passage highlighted**")
                    st.markdown(highlighted_document(document, source["excerpt"]), unsafe_allow_html=True)
                    if source["excerpt"] not in document:
                        st.warning("The passage is not an exact span of this document; no highlight was added.")
                else:
                    st.caption("Full document unavailable; the exact source snapshot is displayed above.")


@st.fragment
def render_forecast_audit():
    """Load the report without rerunning the page and resetting its selected tab."""
    require_demo_login(controls=False)
    if st.button("Load real-history forecast audit"):
        report = request_or_error("GET", "/evaluation/forecast", "load the saved real-history forecast audit")
        if report is not None:
            st.session_state.forecast_audit = report
    report = st.session_state.get("forecast_audit")
    if report is None:
        return
    st.subheader("Real-history price forecasting research")
    st.caption("This saved chronological audit measures historical price forecasts. Five-agent recommendation confidence remains a heuristic score; research forecasts are not used to change recommendations or portfolio safeguards.")
    if report.get("status") != "available":
        st.info(report.get("message", "No saved real-history forecast audit is available."))
        return
    test = report["test"]
    protocol = report["protocol"]
    start = test.get("as_of_start", protocol.get("test_start", "unspecified"))
    end = test.get("as_of_end", protocol.get("test_end", "unspecified"))
    st.write(f"Recorded evaluation period: {start} to {end} · N = {test['sample_size']}")
    st.caption("These scores have been reported and inspected. This evaluation period is now spent; further analysis of it is exploratory and must not be used to tune a model for a new confirmatory claim.")
    if report.get("period_status"):
        st.caption(report["period_status"])
    if report.get("analysis_status"):
        st.caption(report["analysis_status"])
    if test.get("target_end"):
        st.write("Final outcome date:", test["target_end"])
    labels = {"brier": "Brier score", "log_loss": "Log loss", "accuracy": "Direction accuracy",
              "mae_return": "Return MAE", "rmse_return": "Return RMSE"}
    rows = [{"Method": method, **{labels[key]: value for key, value in metrics.items() if key in labels}}
            for method, metrics in test["metrics"].items()]
    if rows:
        st.dataframe(rows, hide_index=True)
        st.caption("Lower Brier score, log loss and return errors are better; higher direction accuracy is better. All methods use identical evaluation dates and outcomes.")
    interval = test.get("interval", {})
    coverage = interval.get("coverage", interval.get("observed_coverage"))
    if coverage is not None:
        nominal = interval.get("nominal_coverage")
        st.write("Observed return-interval coverage:", f"{coverage:.2%}")
        if nominal is not None:
            st.write("Nominal coverage target:", f"{nominal:.2%}")
        if test.get("primary_interval_method"):
            st.write("Predeclared primary interval:", test["primary_interval_method"])
        if interval.get("mean_width") is not None:
            st.write("Mean interval width:", f"{100 * interval['mean_width']:.2f} return percentage points")
        if interval.get("interval_score") is not None:
            st.write("Interval score:", f"{100 * interval['interval_score']:.2f} return percentage points")
        st.caption("Nominal coverage is a target, not a guarantee. Wider intervals can increase coverage; lower interval score balances width against missed outcomes. Market regime changes and a small number of independent forecast dates limit these estimates.")
    interval_rows = []
    interval_labels = {"coverage": "Observed coverage (%)", "nominal_coverage": "Nominal target (%)",
                       "mean_width": "Mean width (return pp)", "interval_score": "Interval score (return pp)"}
    for point_method, methods in test.get("intervals", {}).items():
        for interval_method, values in methods.items():
            interval_rows.append({"Point method": point_method, "Interval method": interval_method,
                                  **{label: 100 * values[key] for key, label in interval_labels.items() if key in values}})
    if interval_rows:
        with st.expander("Interval comparisons and uncertainty"):
            st.dataframe(interval_rows, hide_index=True)
            st.caption("Comparisons use identical evaluation dates. Follow-up intervals use the same calibration dates for each point predictor; the frozen legacy interval retains its original calibration. Joint intervals target simultaneous coverage across securities and should be assessed separately from marginal intervals.")
            joint_details = interval.get("simultaneous_coverage_details", {})
            if joint_details:
                if joint_details.get("coverage") is not None:
                    st.write("Primary interval simultaneous security coverage:", f"{joint_details['coverage']:.2%}")
                st.write("Complete forecast dates:", joint_details.get("complete_forecast_dates", "unspecified"),
                         "· excluded partial forecast dates:", joint_details.get("excluded_partial_forecast_dates", "unspecified"),
                         "· calendar quarters:", joint_details.get("calendar_quarters", "unspecified"))
                st.caption("Simultaneous coverage scores only forecast dates containing every declared security. Partial groups are excluded and counted; these complete dates may represent fewer periods than the marginal evaluation.")
            st.json({"primary_interval_uncertainty": interval.get("uncertainty", {}),
                     "primary_interval_simultaneous_coverage": joint_details,
                     "paired_comparisons": test.get("uncertainty", {})})
    admission = report["selection"]["admission"]
    st.write("Research acceptance check:", "passed" if admission["passed"] else "failed", "—", admission["reason"])
    st.caption("Model readiness: research only. A passed research check does not establish investment performance.")
    st.write("Selected probability model:", report["selection"].get("probability_model", "unspecified"))
    st.write("Selected return model:", report["selection"].get("return_model", "unspecified"))
    for limitation in report["limitations"]:
        st.caption(limitation)
    with st.expander("Chronological protocol, provenance and validation"):
        st.json({key: report[key] for key in (
            "protocol", "data", "validation", "model_id", "selection_id", "evaluated_at_utc",
            "runtime", "features", "calibration", "experiment_version", "period_status",
            "horizon_definition", "development_status", "original_selection_id", "analysis_status",
            "data_quality", "correction") if key in report})
    with st.expander("Held-out calibration and uncertainty"):
        st.json({key: test[key] for key in ("calibration", "uncertainty") if key in test})


def render_evaluation(beginner):
    render_forecast_audit()
    if beginner:
        st.write("Evaluation uses simulated data, so it does not establish investment performance. Recommendation confidence is a heuristic score; it is not a calibrated chance of profit.")
        st.caption("Turn off Plain-language mode to inspect sample sizes, baselines, uncertainty and timing measurements.")
        return
    evaluation = request_or_error("GET", "/evaluation", "load evaluation results")
    if evaluation is not None:
        st.subheader("Walk-forward technical direction evaluation")
        st.dataframe([{ "Method": "Momentum", "Hit rate": evaluation["hit_rate"]},
                      {"Method": "Seeded random", "Hit rate": evaluation["random_hit_rate"]},
                      {"Method": "Always predicts up", "Hit rate": evaluation["buy_hold_hit_rate"]}], hide_index=True)
        st.write(f"N = {evaluation['sample_size']} · Brier score {evaluation['brier_score']:.4f}")
        if evaluation.get("hit_rate_intervals"):
            st.write("Directional accuracy uncertainty intervals:", evaluation["hit_rate_intervals"])
        if evaluation.get("confidence_intervals"):
            st.write("Directional accuracy uncertainty intervals:", evaluation["confidence_intervals"])
        if evaluation.get("uncertainty_intervals"):
            st.write("Simulation uncertainty intervals:", evaluation["uncertainty_intervals"])
        if evaluation.get("paired_hit_rate_differences"):
            st.write("Paired accuracy differences versus baselines:", evaluation["paired_hit_rate_differences"])
        if evaluation.get("baselines"):
            st.write("Baseline definitions and probability scores:", evaluation["baselines"])
        st.write("Average forward return by signal label:", evaluation["mean_forward_return_by_label"])
        bins = [entry for entry in evaluation["calibration"] if entry["count"] > 0]
        if bins:
            fig = px.scatter(pd.DataFrame(bins), x="mean_probability_up", y="realized_up_rate", size="count",
                             hover_data=["bucket", "count"], title="Momentum up-direction probability calibration")
            fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration"))
            st.plotly_chart(fig, use_container_width=True)
        for key in ("calibration_definition", "recommendation_confidence", "full_pipeline", "policy_evaluation", "methodology"):
            if evaluation.get(key):
                st.write(key.replace("_", " ").title() + ":", evaluation[key])
        st.caption(evaluation["limitations"])
    if AuthSettings.from_env().mode != "demo":
        st.caption("Synthetic policy replay and timing benchmarks run in the offline research environment.")
        return
    if st.button("Run point-in-time policy replay"):
        replay = request_or_error("GET", "/evaluation/policies", "evaluate the full-agent policy replay")
        if replay is not None:
            st.session_state.policy_replay = replay
    if "policy_replay" in st.session_state:
        replay = st.session_state.policy_replay
        st.subheader("Full-agent synthetic policy replay")
        st.write(f"{replay['sample_size']} profile analyses across {replay['distinct_market_windows']} distinct market windows.")
        st.dataframe([{"Check": check.replace("_", " "), **counts} for check, counts in replay["policy_checks"].items()], hide_index=True)
        st.write("Action counts:", replay["action_counts"])
        st.caption(replay["limitations"])
        with st.expander("Point-in-time replay records"):
            st.dataframe(replay["rows"], hide_index=True)
    if st.button("Measure parallel versus sequential agents"):
        benchmark = request_or_error("GET", "/benchmark", "measure agent execution")
        if benchmark is not None:
            st.session_state.measured_benchmark = benchmark
    if "measured_benchmark" in st.session_state:
        measured = st.session_state.measured_benchmark
        medians = measured.get("median_wall_time_ms")
        if medians:
            parallel, sequential, ratio = st.columns(3)
            parallel.metric("Measured parallel median", f"{medians['parallel']:.2f} ms")
            sequential.metric("Measured sequential median", f"{medians['sequential']:.2f} ms")
            ratio.metric("Sequential / parallel time", f"{measured['measured_speedup']:.2f}×")
            st.write("A ratio below one means the parallel path was slower for this workload.")
            st.write("Timing uncertainty:", measured.get("speedup_interval"))
        with st.expander("Measured benchmark details"):
            st.json(measured)
        st.caption(measured.get("limitations", "Actual timings can be noisy; parallel execution is not guaranteed to be faster for these small local calculations."))


def main():
    st.set_page_config(page_title="VibeFinance", page_icon="📈", layout="wide")
    st.title("VibeFinance")
    if revision := release_revision():
        st.caption(f"Deployed revision: {revision[:12]}")
    st.caption("Explainable market intelligence · Indian retail investor demo")
    st.info("Default demo uses seeded simulated prices and synthetic company documents. Optional live prices do not make the fabricated filings real. No LLM or API key is required for the default demo.")
    st.caption(DISCLAIMER)
    require_demo_login()
    personal = AuthSettings.from_env().mode != "demo"
    profiles = request_or_error("GET", "/profiles", "load investor profiles")
    if profiles is None:
        st.stop()
    if st.session_state.pop("profile_saved", False):
        st.success("Investor profile saved. Analysis and comparison caches were cleared.")
    labels = {p["user_id"]: p["name"] for p in profiles}
    with st.sidebar:
        st.header("Analysis controls")
        user = st.selectbox("Investor", list(labels), format_func=labels.get,
                            index=list(labels).index("arjun") if "arjun" in labels else 0) if labels else None
        profile = next((p for p in profiles if p["user_id"] == user), None)
        render_profile_form(profile, profiles)
        ticker = st.selectbox("NSE ticker", TICKERS)
        sentiment_outage = st.toggle("Simulate sentiment feed outage")
        missing_filing = st.toggle("Missing filing for ticker")
        beginner = st.toggle("Plain-language mode", value=True)
        live = st.checkbox("Try live prices (optional)", help="Downloads only prices; documents remain synthetic. On failure, disclosed simulated data is used. Live availability is not guaranteed.")
        run = st.button("Run analysis", type="primary", use_container_width=True, disabled=profile is None)
        st.caption("ITC always simulates a sentiment outage. HDFCBANK has no filing in the corpus.")
    if profile is None:
        st.info("Create an investor profile in the sidebar to begin.")
        st.stop()
    request = {"user_id": user, "ticker": ticker, "sentiment_outage": sentiment_outage, "missing_filing": missing_filing, "live": live}
    signature = profile_signature(profile)
    key = (user, ticker, sentiment_outage, missing_filing, live, signature)
    if run or st.session_state.get("analysis_key") != key:
        with st.spinner("Retrieving sources and running five agents…"):
            session = request_or_error("POST", "/analyze", "run analysis", json=request)
        if session is None:
            st.session_state.pop("analysis_key", None)
            st.stop()
        st.session_state.analysis = session
        st.session_state.analysis_key = key
    session = st.session_state.analysis
    rec = session["recommendation"]
    if session["warnings"]:
        st.warning(" · ".join(session["warnings"]))
    if not session_saved(session):
        st.warning("This result has not been saved. Sources remain available in this browser session; decisions and persistent history require working storage.")
    readable = {"BUY": "The available signal supports considering an entry after reviewing your portfolio limits.",
                "ACCUMULATE": "Consider staged entries rather than a single large trade.",
                "HOLD": "Wait while the evidence or portfolio constraints settle.",
                "REDUCE": "Review a gradual reduction in exposure; a known portfolio limit can matter even when market evidence is missing.",
                "AVOID": "The available evidence or risk constraints do not support new exposure.",
                "WATCH": "Important evidence is missing; gather more information before taking new exposure."}
    left, right = st.columns([3, 1])
    with left:
        st.subheader(f"{ticker.removesuffix('.NS')} · {rec['action']}")
        st.write(readable[rec["action"]] if beginner else " ".join(rec["personalization_notes"][:2]))
    with right:
        st.metric("Evidence strength", f"{100 * rec['confidence']:.0f}/100")
        st.caption("Heuristic market evidence score; not a calibrated probability of profit or of a correct action.")
        basis = {"market_evidence": "market evidence", "portfolio_policy": "portfolio safeguards",
                 "incomplete_evidence": "incomplete evidence", "conflict_resolution": "conflicting evidence"}
        st.caption("Decision basis: " + basis.get(rec.get("decision_basis"), "review the reasoning below") + ".")
    tabs = st.tabs(["Analysis", "Sources", "Portfolio & watchlist", "Compare my profiles" if personal else "Compare users", "Metrics", "History"])
    with tabs[0]:
        signal_table(session, beginner)
        rows = session.get("market_rows")
        if rows:
            frame = pd.DataFrame(rows)
            frame["date"] = pd.to_datetime(frame["date"])
            title = "Live downloaded price · INR" if session.get("data_mode") == "live" else "Seeded simulated price · INR"
        elif session.get("data_mode") == "simulated":
            frame, title = generate_market(ticker), "Seeded simulated price · INR"
        else:
            frame = None
        if frame is not None and not frame.empty:
            fig = px.line(frame, x="date", y="close", title=title)
            fig.add_trace(go.Scatter(x=[frame.date.iloc[-1]], y=[frame.close.iloc[-1]], mode="markers", marker={"size": 12}, name=rec["action"]))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("A price chart is unavailable for this input; no replacement prices are displayed.")
        with st.expander("Decision explanation", expanded=True):
            if beginner:
                st.write(readable[rec["action"]])
                st.write("The result combines price trend, participation, news, filings and your portfolio constraints. Missing evidence lowers assurance; an action is not a promise of returns.")
                policy_explanations = {
                    "single_stock_limit": "The position has reached or exceeded your single-stock allocation limit. The profile constraint takes priority over new purchases.",
                    "sector_limit": "Your exposure to this sector has reached the demo limit, so adding another position here would increase a known concentration.",
                    "equity_concentration": "Your equity positions are concentrated. The demo pauses additions to the largest position.",
                    "cash_funding": "The illustrated entry needs available cash. A funded reallocation would require a separate decision.",
                    "short_horizon_volatility": "The price volatility is too high for the selected short investment horizon under the demo rules.",
                    "momentum_chasing_confirmation": "Your momentum-chasing history requires supportive filing evidence before increasing exposure.",
                }
                for rule in rec.get("policy_rules", []):
                    if rule in policy_explanations:
                        st.write(policy_explanations[rule])
                if profile.get("behavior", {}).get("panic_sell_count", 0) >= 2:
                    st.write("Past panic sells suggest reviewing a gradual rebalance rather than an abrupt exit.")
                if rec["conflicts"]:
                    st.write("Some agents disagree. Read the source passages before interpreting the result.")
                if any(a["status"] != "ok" for a in rec["agent_outputs"]):
                    st.write("Some evidence is unavailable or degraded. The warning above explains which input failed.")
            else:
                for note in rec["personalization_notes"]:
                    st.write(note)
        with st.expander("Full numbered reasoning"):
            st.caption("These are the recorded deterministic rules and evidence summaries, not a forecast of returns.")
            for step in rec["reasoning_chain"]:
                st.write(step)
        if rec["conflicts"]:
            st.subheader("Agent disagreement")
            for conflict in rec["conflicts"]:
                st.warning("The price signal opposes the filing or news assessment. Review both sources." if beginner else conflict)
        with st.expander("Agent evidence and latency"):
            st.caption("Agent scores describe heuristic evidence strength. Timings are measured for this analysis; neither scores nor timings establish predictive accuracy.")
            for agent in rec["agent_outputs"]:
                st.markdown(f"**{agent['dimension'].title()} · {agent['label']}**")
                st.caption(f"Evidence strength {100 * agent['confidence']:.1f}/100 · {agent['status']} · {agent['latency_ms']:.2f} ms")
                for bullet in agent["evidence"]:
                    st.write("• " + bullet)
        with st.expander("Pipeline trace"):
            st.caption("Recorded processing steps and source checks; source identity does not independently verify a company claim.")
            for index, step in enumerate(session["trace"], 1):
                st.write(f"{index}. **{step['step']}** — {step['detail']}")
    with tabs[1]:
        render_sources(session, beginner)
    with tabs[2]:
        metrics = session["metrics"]
        holdings = metrics["holdings_before"]
        if beginner:
            equities = [s.removesuffix(".NS") for s, w in holdings.items() if s != "CASH" and w > 0]
            st.write("Your portfolio holds " + ", ".join(equities) + "." if equities else "Your portfolio currently holds cash and no equity positions.")
            st.write("Cash and equity concentration are assessed separately. Holding cash does not automatically create high equity risk.")
        else:
            chart = pd.DataFrame({"Holding": list(holdings), "Weight": list(holdings.values())})
            st.plotly_chart(px.pie(chart, names="Holding", values="Weight", title="Portfolio allocation including cash"), use_container_width=True)
            st.write(f"Single-stock limit: {profile['max_single_stock_pct']:.0%}; risk tolerance: {profile['risk_tolerance']}.")
        st.subheader("Portfolio what-if")
        if beginner:
            st.write("This illustrates how a small hypothetical allocation change would affect concentration. No holdings are changed and no trade is placed.")
        else:
            st.write(f"Illustrative {metrics['trade_weight']:+.1%} portfolio-weight trade in {ticker}, funded from cash.")
            a, b, c = st.columns(3)
            a.metric("Equity-only HHI before → after", f"{metrics.get('equity_hhi_before', metrics['hhi_before']):.3f} → {metrics.get('equity_hhi_after', metrics['hhi_after']):.3f}")
            b.metric("Largest equity holding", f"{metrics['top_holding_before']:.0%} → {metrics['top_holding_after']:.0%}")
            c.metric("Cash allocation", f"{metrics.get('cash_weight_before', holdings.get('CASH', 0)):.0%} → {metrics.get('cash_weight_after', metrics.get('holdings_after', {}).get('CASH', 0)):.0%}")
            st.write(f"Descriptive total HHI including cash: {metrics['hhi_before']:.3f} → {metrics['hhi_after']:.3f}.")
            if "largest_equity_sector_weight_before" in metrics:
                st.write(f"Largest equity sector allocation: {metrics['largest_equity_sector_weight_before']:.0%} → {metrics['largest_equity_sector_weight_after']:.0%} of the full portfolio.")
            st.caption("Equity HHI uses equity weights normalized within equity; all-cash equity HHI is zero. Cash allocation is reported separately. Illustrations do not modify holdings.")
        watched = st.multiselect("Watchlist tickers", TICKERS, default=[t for t in profile["holdings"] if t in TICKERS])
        watch_key = (signature, tuple(watched))
        if st.button("Scan personalized watchlist", disabled=not watched):
            scan = request_or_error("POST", "/watchlist", "scan the watchlist", json={"user_id": user, "tickers": watched})
            if scan is not None:
                st.session_state.watchlist, st.session_state.watchlist_key = scan, watch_key
            else:
                st.session_state.pop("watchlist_key", None)
        if st.session_state.get("watchlist_key") == watch_key:
            scan = st.session_state.watchlist
            matrix = [{"Ticker": s["recommendation"]["ticker"], **({} if beginner else {a["dimension"]: a["label"] for a in s["recommendation"]["agent_outputs"]}), "Action": s["recommendation"]["action"]} for s in scan["sessions"]]
            st.dataframe(matrix, hide_index=True, use_container_width=True)
            for alert in scan["alerts"]:
                st.info(f"{alert['ticker']} · {alert['action']} · " + (readable[alert["action"]] if beginner else " ".join(alert["reason"])))
            if not scan["alerts"]:
                st.write("No actionable alerts pass this profile's policy and confidence threshold.")
    with tabs[3]:
        st.caption("Your profiles receive the identical market frame and corpus. Only the profile changes." if personal
                   else "All users receive the identical market frame and corpus. Only the profile changes.")
        compare_key = (ticker, sentiment_outage, missing_filing, live, tuple(sorted(profile_signature(p) for p in profiles)))
        if st.button("Compare my profiles" if personal else "Compare all three profiles"):
            results = request_or_error("POST", "/compare", "compare investor profiles", json=request)
            if results is not None:
                st.session_state.comparison, st.session_state.comparison_key = results, compare_key
            else:
                st.session_state.pop("comparison_key", None)
        if st.session_state.get("comparison_key") == compare_key:
            results = st.session_state.comparison
            if results:
                columns = st.columns(len(results))
                for column, item in zip(columns, results):
                    recommendation = item["recommendation"]
                    with column:
                        st.subheader(labels.get(recommendation["user_id"], recommendation["user_id"]))
                        if beginner:
                            st.subheader(recommendation["action"])
                            st.caption("Profile-specific demo action")
                        else:
                            st.metric(recommendation["action"], f"{recommendation['confidence']:.0%}")
                        if beginner:
                            st.write(readable[recommendation["action"]])
                        else:
                            for note in recommendation["personalization_notes"]:
                                st.write(note)
                if not beginner:
                    st.caption("Shared input: " + results[0]["market_fingerprint"])
    with tabs[4]:
        metrics = session["metrics"]
        if not beginner:
            a, b, c = st.columns(3)
            a.metric("Compute latency", f"{metrics['total_latency_ms']:.1f} ms")
            b.metric("Degraded / failed agents", f"{metrics['degraded_agent_count']} / {metrics['failed_agent_count']}")
            coverage = metrics.get("claim_support_coverage", metrics.get("citation_coverage"))
            coverage_label = "Supported evidence claims" if "claim_support_coverage" in metrics else "Evidence with source provenance"
            c.metric(coverage_label, f"{coverage:.0%}" if coverage is not None else "N/A")
            latency = pd.DataFrame({"Agent": list(metrics["agent_latency_ms"]), "ms": list(metrics["agent_latency_ms"].values())})
            st.plotly_chart(px.bar(latency, x="Agent", y="ms", title="Observed agent latency"), use_container_width=True)
            st.write(f"Parallel wall time {metrics['parallel_agents_ms']:.2f} ms; sum of wrapper times {metrics['sum_agent_latency_ms']:.2f} ms.")
            st.caption("Summed wrapper timings include scheduling and are not a sequential benchmark. Compute latency excludes persistence/HTTP. Claim support checks are limited deterministic rules, not independent verification of factual truth.")
        render_evaluation(beginner)
    with tabs[5]:
        history = request_or_error("GET", "/history/" + quote(user, safe=""), "load saved history", params={"ticker": ticker, "limit": 10})
        if history is not None:
            st.dataframe([{ "Session": s["session_id"][:8], "Action": s["recommendation"]["action"],
                          **({} if beginner else {"Confidence": s["recommendation"]["confidence"]}), "Warnings": len(s["warnings"])} for s in history], hide_index=True)
            prior = [s for s in history if s["session_id"] != session["session_id"]]
            if prior:
                old = prior[0]["recommendation"]
                old_agents = {a["dimension"]: a for a in old["agent_outputs"]}
                changes = [f"{a['dimension']}: {old_agents[a['dimension']]['label']} → {a['label']}" for a in rec["agent_outputs"] if a["dimension"] in old_agents and a["label"] != old_agents[a["dimension"]]["label"]]
                st.write(f"Previous action {old['action']} → {rec['action']}. " + ("Signals changed; review the current sources." if beginner and changes else "; ".join(changes) if changes else "Agent labels are unchanged; profile or evidence availability may still differ."))
        saved = session_saved(session)
        choice = st.selectbox("Record your demo decision", ["watch", "follow", "skip"], disabled=not saved)
        if st.button("Save decision", disabled=not saved):
            decision = request_or_error("POST", f"/sessions/{session['session_id']}/decision", "save the demo decision", json={"decision": choice})
            if decision is not None and decision.get("saved"):
                st.success("Decision saved. No trade is placed.")
        if saved:
            decisions = request_or_error("GET", f"/sessions/{session['session_id']}/decisions", "load saved decisions")
            if decisions:
                st.dataframe(decisions, hide_index=True)
    st.divider()
    st.caption("Commercial concept: free watchlist → paid personalization → B2B research API. Production needs licensed data, audited models, security controls and appropriate SEBI compliance.")


if __name__ == "__main__":
    main()
