"""Verify a hosted release without disclosing or requesting its credentials.

Default checks are public health, public revision and the demo login gate.
Supabase mode checks its personal-account gate instead. An explicitly enabled
protected browser check reads caller-supplied credentials from named environment
variables. Login with an existing profile creates one analysis session.
Optional tooling is described in docs/OPERATIONS.md; app locks are unchanged.
"""
import argparse
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
from urllib.parse import unquote, urlsplit
from urllib.request import getproxies, proxy_bypass

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _base_url(value):
    parsed = urlsplit(value)
    local = parsed.hostname == "localhost"
    try:
        local = local or ipaddress.ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        pass
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/") or (parsed.scheme != "https" and not (parsed.scheme == "http" and local))):
        raise argparse.ArgumentTypeError("Use an HTTPS root URL without credentials, or loopback HTTP for an isolated local test.")
    return value.rstrip("/")


def _revision(value):
    if not re.fullmatch(r"[0-9a-fA-F]{12,40}", value):
        raise argparse.ArgumentTypeError("Expected revision must be 12–40 hexadecimal characters.")
    return value.lower()


def _ssl_context():
    # Inherited trust is retained; never disable certificate/hostname checking.
    return ssl.create_default_context(cafile=os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE"))


def _proxy_options(url):
    parsed = urlsplit(url)
    if proxy_bypass(parsed.hostname or ""):
        return {}
    configured = getproxies().get(parsed.scheme)
    if not configured:
        return {}
    proxy = urlsplit(configured)
    if proxy.scheme != "http" or not proxy.hostname:
        raise ValueError("This checker requires an HTTP CONNECT proxy when a proxy is configured.")
    options = {"http_proxy_host": proxy.hostname, "http_proxy_port": proxy.port or 80, "proxy_type": "http"}
    if proxy.username is not None:
        options["http_proxy_auth"] = (unquote(proxy.username), unquote(proxy.password or ""))
    return options


def check_public(url, expected_revision, timeout=120, login_kind="demo"):
    """Read only the unauthenticated Streamlit protocol; retain no page contents."""
    if login_kind not in {"demo", "supabase"}:
        raise ValueError("Unsupported login kind")
    import websocket  # Optional operator tooling, not an application dependency.
    from streamlit.proto.BackMsg_pb2 import BackMsg
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    from streamlit.proto.TextInput_pb2 import TextInput

    result = {"url": url, "expected_revision": expected_revision, "login_kind": login_kind, "credentials_used": False,
              "tls_verified": url.startswith("https://"), "login_gate_visible": False}
    account_fields = set()
    deadline = time.monotonic() + timeout
    with httpx.Client(verify=_ssl_context(), trust_env=True, timeout=min(timeout, 15)) as client:
        while True:
            retry = True
            try:
                response = client.get(url + "/_stcore/health", timeout=max(1, min(15, deadline - time.monotonic())))
                result["health_status"] = response.status_code
                result["health_ok"] = response.status_code == 200 and response.text.strip() == "ok"
                retry = response.status_code in {502, 503, 504}
                result.pop("health_error_type", None)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                result.update(health_ok=False, health_error_type=type(exc).__name__)
            if result["health_ok"] or not retry or time.monotonic() >= deadline:
                break
            time.sleep(min(2, max(0, deadline - time.monotonic())))
    if not result["health_ok"]:
        result["ok"] = False
        return result
    remaining = max(1, deadline - time.monotonic())
    ws_url = ("wss://" if url.startswith("https://") else "ws://") + urlsplit(url).netloc + "/_stcore/stream"
    connection = websocket.create_connection(
        ws_url, timeout=min(remaining, 30), origin=url, subprotocols=["streamlit"],
        sslopt={"context": _ssl_context(), "cert_reqs": ssl.CERT_REQUIRED, "check_hostname": True},
        **_proxy_options(url),
    )
    try:
        message = BackMsg()
        message.rerun_script.query_string = ""
        connection.send_binary(message.SerializeToString())
        while time.monotonic() < deadline:
            connection.settimeout(max(1, min(30, deadline - time.monotonic())))
            raw = connection.recv()
            if not raw:
                break
            if not isinstance(raw, bytes):
                continue
            forward = ForwardMsg()
            forward.ParseFromString(raw)
            if forward.HasField("delta") and forward.delta.HasField("new_element"):
                element = forward.delta.new_element
                if element.HasField("markdown"):
                    match = re.fullmatch(r"Deployed revision: ([0-9a-f]{7,40})", element.markdown.body.strip())
                    if match:
                        result["visible_revision"] = match.group(1)
                if element.HasField("text_input"):
                    field = element.text_input
                    if login_kind == "demo" and field.label == "Demo access token" and field.type == TextInput.PASSWORD:
                        result["login_gate_visible"] = True
                    elif login_kind == "supabase":
                        if field.label == "Email" and field.type == TextInput.DEFAULT:
                            account_fields.add("email")
                        elif field.label == "Password" and field.type == TextInput.PASSWORD:
                            account_fields.add("password")
                        result["login_gate_visible"] = account_fields == {"email", "password"}
                if element.HasField("exception"):
                    result["application_exception"] = True
            if forward.HasField("script_finished"):
                break
    finally:
        connection.close()
    visible = result.get("visible_revision", "")
    result["revision_matches"] = len(visible) >= 12 and expected_revision.startswith(visible)
    result["ok"] = bool(result["health_ok"] and result["revision_matches"] and result["login_gate_visible"]
                        and not result.get("application_exception"))
    return result


def check_protected_browser(url, token, timeout, executable=None, *, login_kind="demo", email=None):
    """Opt-in browser acceptance. Never retain screenshots, traces or page text.

    The dashboard automatically POSTs /analyze after login, saving a session.
    This function must only be called after the explicit write acknowledgement.
    It does not edit profiles, record decisions, or scan watchlists.
    """
    if login_kind not in {"demo", "supabase"} or not token or (login_kind == "supabase" and not email):
        raise ValueError("Protected credentials are unavailable")
    from playwright.sync_api import sync_playwright

    options = {"headless": True}
    if executable:
        options["executable_path"] = executable
    proxy = _proxy_options(url)
    if proxy:
        options["proxy"] = {"server": f"http://{proxy['http_proxy_host']}:{proxy['http_proxy_port']}"}
        if "http_proxy_auth" in proxy:
            options["proxy"]["username"], options["proxy"]["password"] = proxy["http_proxy_auth"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**options)
        try:
            # Browser must trust the operator CA. No ignore_https_errors escape.
            page = browser.new_page(ignore_https_errors=False)
            page.set_default_timeout(timeout * 1000)
            page.goto(url, wait_until="domcontentloaded")
            if login_kind == "supabase":
                page.get_by_label("Email", exact=True).fill(email)
                page.get_by_label("Password", exact=True).fill(token)
                page.get_by_role("button", name="Sign in", exact=True).click()
                page.get_by_role("button", name="Sign out", exact=True).wait_for(state="visible")
            else:
                page.get_by_label("Demo access token", exact=True).fill(token)
                page.get_by_role("button", name="Open protected demo", exact=True).click()
            analysis = page.get_by_role("button", name="Run analysis", exact=True)
            analysis.wait_for(state="visible")
            if login_kind == "supabase" and analysis.is_disabled():
                return {"ok": False, "login_kind": login_kind, "protected_login_verified": True,
                        "operator_profile_required": True, "saved_report_loaded": False,
                        "initial_analysis_session_write_acknowledged": True, "credentials_used": True}
            page.get_by_role("tab", name="Metrics", exact=True).click()
            page.get_by_role("button", name="Load real-history forecast audit", exact=True).click()
            page.get_by_text("Model readiness: research only.", exact=False).wait_for(state="visible")
            return {"ok": True, "login_kind": login_kind, "protected_login_verified": True,
                    "operator_profile_required": False, "saved_report_loaded": True, "research_only_visible": True,
                    "initial_analysis_session_write_acknowledged": True, "credentials_used": True}
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", type=_base_url, default="https://vibefinance.onrender.com")
    parser.add_argument("--expected-revision", required=True, type=_revision)
    parser.add_argument("--timeout", type=int, default=120, help="Cold-start/check budget in seconds (1–300).")
    parser.add_argument("--login-kind", choices=("demo", "supabase"), default="demo",
                        help="Expected public login gate and optional protected sign-in type.")
    parser.add_argument("--protected-token-env", metavar="VARIABLE_NAME",
                        help="Opt in to a protected check using only a caller-supplied environment variable.")
    parser.add_argument("--account-email-env", metavar="VARIABLE_NAME",
                        help="Supabase protected check: caller-supplied account email environment variable name.")
    parser.add_argument("--account-password-env", metavar="VARIABLE_NAME",
                        help="Supabase protected check: caller-supplied account password environment variable name.")
    parser.add_argument("--allow-protected-session-write", action="store_true",
                        help="Acknowledge that dashboard login automatically analyzes and saves one session.")
    parser.add_argument("--browser-executable", help="Optional Chromium executable for protected checks.")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 300:
        parser.error("--timeout must be between 1 and 300 seconds")
    account_requested = bool(args.account_email_env or args.account_password_env)
    protected_requested = bool(args.protected_token_env or account_requested)
    if args.login_kind == "demo" and account_requested:
        parser.error("Account environment flags require --login-kind supabase and cannot be combined with demo credentials.")
    if args.login_kind == "supabase" and args.protected_token_env:
        parser.error("--protected-token-env is only for demo login; use the two account environment flags for Supabase.")
    if account_requested and not (args.account_email_env and args.account_password_env):
        parser.error("Protected Supabase login requires both --account-email-env and --account-password-env.")
    if protected_requested:
        if not args.allow_protected_session_write:
            parser.error("Protected login writes an analysis session: require --allow-protected-session-write on an authorized test target.")
        names = (args.account_email_env, args.account_password_env) if account_requested else (args.protected_token_env,)
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in names):
            parser.error("Credential flags must name environment variables, not contain credential values.")
        if len(set(names)) != len(names):
            parser.error("Account email and password must use separate environment variables.")
        if any(not os.getenv(name) for name in names):
            parser.error("A caller-supplied credential environment variable is empty or unavailable.")
    elif args.allow_protected_session_write:
        parser.error("--allow-protected-session-write requires the protected login environment flags")
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "url": args.url,
              "expected_revision": args.expected_revision, "login_kind": args.login_kind,
              "protected_check": "not requested"}
    try:
        result["public"] = check_public(args.url, args.expected_revision, args.timeout, args.login_kind)
        if protected_requested and result["public"]["ok"]:
            credential_name = args.account_password_env if account_requested else args.protected_token_env
            result["protected_check"] = check_protected_browser(
                args.url, os.environ[credential_name], args.timeout, args.browser_executable,
                login_kind=args.login_kind, email=os.environ[args.account_email_env] if account_requested else None)
        result["ok"] = result["public"]["ok"] and (
            not protected_requested or isinstance(result["protected_check"], dict) and result["protected_check"]["ok"])
    except Exception as exc:
        # Exceptions and browser diagnostics may contain URLs/credentials; emit
        # only the type, never raw errors, proxy configuration or page contents.
        result.update(ok=False, error_type=type(exc).__name__)
        if isinstance(exc, ImportError):
            result["tooling_help"] = "Install optional checker tooling as documented in docs/OPERATIONS.md."
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
