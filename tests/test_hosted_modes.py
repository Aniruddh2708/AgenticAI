"""Protocol fixtures and browser doubles; never use hosted account credentials."""
import json
import ssl
import sys
from types import SimpleNamespace

import httpx
import pytest
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from streamlit.proto.TextInput_pb2 import TextInput

from scripts import check_hosted


REVISION = "a" * 40


def public_protocol(monkeypatch, fields, revision=REVISION[:12]):
    messages = []
    marker = ForwardMsg()
    marker.delta.new_element.markdown.body = "Deployed revision: " + revision
    messages.append(marker.SerializeToString())
    for label, kind in fields:
        message = ForwardMsg()
        message.delta.new_element.text_input.label = label
        message.delta.new_element.text_input.type = kind
        messages.append(message.SerializeToString())
    finished = ForwardMsg()
    finished.script_finished = ForwardMsg.FINISHED_SUCCESSFULLY
    messages.append(finished.SerializeToString())
    state = {"closed": False, "requests": [], "socket_options": None}

    class HealthClient:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            state["requests"].append(url)
            return httpx.Response(200, text="ok")

    class Socket:
        def send_binary(self, data):
            assert isinstance(data, bytes)

        def settimeout(self, value):
            pass

        def recv(self):
            return messages.pop(0)

        def close(self):
            state["closed"] = True

    def connect(url, **kwargs):
        state["socket_options"] = kwargs
        return Socket()

    monkeypatch.setattr(check_hosted.httpx, "Client", HealthClient)
    monkeypatch.setattr(check_hosted, "_proxy_options", lambda url: {})
    monkeypatch.setitem(sys.modules, "websocket", SimpleNamespace(create_connection=connect))
    return state


@pytest.mark.parametrize("kind,fields,expected", [
    ("demo", [("Demo access token", TextInput.PASSWORD)], True),
    ("demo", [("Demo access token", TextInput.DEFAULT)], False),
    ("demo", [("Email", TextInput.DEFAULT), ("Password", TextInput.PASSWORD)], False),
    ("supabase", [("Email", TextInput.DEFAULT), ("Password", TextInput.PASSWORD)], True),
    ("supabase", [("Demo access token", TextInput.PASSWORD)], False),
    ("supabase", [("Email", TextInput.DEFAULT)], False),
    ("supabase", [("Email", TextInput.DEFAULT), ("Password", TextInput.DEFAULT)], False),
    ("supabase", [("Account Email", TextInput.DEFAULT), ("Password", TextInput.PASSWORD)], False),
])
def test_public_gate_requires_expected_labels_and_password_type(monkeypatch, kind, fields, expected):
    state = public_protocol(monkeypatch, fields)
    result = check_hosted.check_public("https://finance.example.test", REVISION, 5, kind)
    assert result["ok"] is expected
    assert result["login_gate_visible"] is expected
    assert result["credentials_used"] is False
    assert result["tls_verified"] is True
    assert result["revision_matches"] is True
    assert state["closed"] is True
    assert state["socket_options"]["sslopt"]["cert_reqs"] == ssl.CERT_REQUIRED
    assert state["socket_options"]["sslopt"]["check_hostname"] is True
    assert "page" not in result


def test_correct_supabase_gate_does_not_hide_wrong_revision(monkeypatch):
    public_protocol(monkeypatch, [("Email", TextInput.DEFAULT), ("Password", TextInput.PASSWORD)], "b" * 12)
    result = check_hosted.check_public("https://finance.example.test", REVISION, 5, "supabase")
    assert result["login_gate_visible"] is True
    assert result["revision_matches"] is False
    assert result["ok"] is False


@pytest.mark.parametrize("flags", [
    ["--login-kind", "supabase", "--account-email-env", "FIXTURE_EMAIL"],
    ["--login-kind", "supabase", "--account-password-env", "FIXTURE_PASSWORD"],
    ["--login-kind", "supabase", "--protected-token-env", "FIXTURE_TOKEN"],
    ["--account-email-env", "FIXTURE_EMAIL", "--account-password-env", "FIXTURE_PASSWORD"],
    ["--login-kind", "supabase", "--account-email-env", "FIXTURE_EMAIL", "--account-password-env", "FIXTURE_PASSWORD"],
    ["--login-kind", "supabase", "--account-email-env", "email@example.test", "--account-password-env", "FIXTURE_PASSWORD", "--allow-protected-session-write"],
    ["--login-kind", "supabase", "--account-email-env", "FIXTURE_EMAIL", "--account-password-env", "FIXTURE_PASSWORD", "--allow-protected-session-write"],
    ["--allow-protected-session-write"],
    ["--protected-token-env", "FIXTURE_TOKEN", "--allow-protected-session-write"],
])
def test_invalid_or_missing_credentials_rejected_before_network(monkeypatch, capsys, flags):
    for name in ("FIXTURE_EMAIL", "FIXTURE_PASSWORD", "FIXTURE_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    attempts = []
    monkeypatch.setattr(check_hosted, "check_public", lambda *args: attempts.append(args))
    monkeypatch.setattr(sys, "argv", ["check_hosted.py", "--expected-revision", REVISION, *flags])
    with pytest.raises(SystemExit) as stopped:
        check_hosted.main()
    assert stopped.value.code == 2
    assert not attempts
    assert not capsys.readouterr().out


def test_cli_reads_supabase_environment_only_after_validation(monkeypatch, capsys):
    monkeypatch.setenv("FIXTURE_EMAIL", "fixture-private-email@example.test")
    monkeypatch.setenv("FIXTURE_PASSWORD", "fixture-private-password")
    observed = []
    monkeypatch.setattr(sys, "argv", ["check_hosted.py", "--expected-revision", REVISION,
        "--login-kind", "supabase", "--account-email-env", "FIXTURE_EMAIL",
        "--account-password-env", "FIXTURE_PASSWORD", "--allow-protected-session-write"])
    monkeypatch.setattr(check_hosted, "check_public", lambda *args: {"ok": True})
    def protected(url, token, timeout, executable, **kwargs):
        observed.append((token, kwargs))
        return {"ok": True}
    monkeypatch.setattr(check_hosted, "check_protected_browser", protected)
    assert check_hosted.main() == 0
    output = capsys.readouterr().out
    assert observed == [("fixture-private-password", {"login_kind": "supabase", "email": "fixture-private-email@example.test"})]
    assert "fixture-private" not in output
    assert json.loads(output)["ok"] is True


def test_browser_exception_is_sanitized(monkeypatch, capsys):
    monkeypatch.setenv("FIXTURE_TOKEN", "fixture-private-token")
    monkeypatch.setattr(sys, "argv", ["check_hosted.py", "--expected-revision", REVISION,
        "--protected-token-env", "FIXTURE_TOKEN", "--allow-protected-session-write"])
    monkeypatch.setattr(check_hosted, "check_public", lambda *args: {"ok": True})
    def fail(*args, **kwargs):
        raise RuntimeError("fixture-private-token at private-page-url")
    monkeypatch.setattr(check_hosted, "check_protected_browser", fail)
    assert check_hosted.main() == 1
    output = capsys.readouterr().out
    assert "fixture-private" not in output
    assert "private-page-url" not in output
    assert json.loads(output)["error_type"] == "RuntimeError"


def browser_fixture(monkeypatch, *, empty=False):
    actions = []
    class Locator:
        def __init__(self, label):
            self.label = label
        def fill(self, value):
            actions.append(("fill", self.label))
        def click(self):
            actions.append(("click", self.label))
        def wait_for(self, **kwargs):
            actions.append(("wait", self.label))
        def is_disabled(self):
            return empty
    class Page:
        def set_default_timeout(self, value):
            pass
        def goto(self, url, **kwargs):
            pass
        def get_by_label(self, label, **kwargs):
            return Locator(label)
        def get_by_role(self, role, name, **kwargs):
            return Locator(name)
        def get_by_text(self, text, **kwargs):
            return Locator(text)
    class Browser:
        def new_page(self, **kwargs):
            assert kwargs == {"ignore_https_errors": False}
            return Page()
        def close(self):
            actions.append(("close", "browser"))
    class Playwright:
        def __enter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch=lambda **kwargs: Browser()))
        def __exit__(self, *args):
            pass
    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "playwright.sync_api", SimpleNamespace(sync_playwright=Playwright))
    monkeypatch.setattr(check_hosted, "_proxy_options", lambda url: {})
    return actions


@pytest.mark.parametrize("empty", [False, True])
def test_supabase_browser_signs_in_and_never_creates_profiles(monkeypatch, empty):
    actions = browser_fixture(monkeypatch, empty=empty)
    result = check_hosted.check_protected_browser("https://finance.example.test", "fixture-password",
        5, login_kind="supabase", email="fixture-email@example.test")
    assert result["ok"] is not empty
    assert result["operator_profile_required"] is empty
    assert result["protected_login_verified"] is True
    assert ("fill", "Email") in actions and ("fill", "Password") in actions
    assert ("click", "Sign in") in actions and ("wait", "Sign out") in actions
    assert (("click", "Metrics") in actions) is not empty
    assert not any("Create" in label or "Save" in label for _, label in actions)
    assert actions[-1] == ("close", "browser")
    assert "fixture" not in json.dumps(result)


def test_existing_demo_browser_flow_stays_default(monkeypatch):
    actions = browser_fixture(monkeypatch)
    result = check_hosted.check_protected_browser("https://finance.example.test", "fixture-token", 5)
    assert result["ok"] is True
    assert ("fill", "Demo access token") in actions
    assert ("click", "Open protected demo") in actions
    assert ("fill", "Email") not in actions
