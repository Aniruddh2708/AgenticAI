"""Production launch/configuration checks; no real accounts or secrets."""
import json
import os
from pathlib import Path
import stat
import tomllib

import pytest

from vibefinance import production_startup as startup


def environment():
    return {
        "VIBEFINANCE_AUTH_MODE": "oidc",
        "VIBEFINANCE_OIDC_ISSUER": "https://identity.example.test/tenant",
        "VIBEFINANCE_OIDC_AUDIENCE": "https://api.example.test",
        "VIBEFINANCE_OIDC_UI_CLIENT_ID": "test-ui-client",
        "VIBEFINANCE_INTERNAL_AUTH_KEY": "i" * 32,
        "VIBEFINANCE_OIDC_UI_CLIENT_SECRET": 'test-secret-"quoted"-\\escaped',
        "VIBEFINANCE_OIDC_COOKIE_SECRET": "c" * 32,
        "VIBEFINANCE_PUBLIC_URL": "https://finance.example.test",
        "VIBEFINANCE_DATABASE_URL": "postgresql://test:fixture@db.example.test/finance?sslmode=verify-full",
    }


def supabase_environment():
    return {
        "VIBEFINANCE_AUTH_MODE": "supabase",
        "VIBEFINANCE_SUPABASE_URL": "https://abcdefghijklmnopqrst.supabase.co",
        "VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY": "sb_publishable_fixtureonlytestkey",
        "VIBEFINANCE_PUBLIC_URL": "https://finance.example.test",
        "VIBEFINANCE_DATABASE_URL": environment()["VIBEFINANCE_DATABASE_URL"],
    }


def test_free_supabase_configuration_does_not_require_oidc_secrets():
    values = supabase_environment()
    assert startup.validate_production_configuration(values).mode == "supabase"
    assert startup.production_preflight(values, check_dependencies=False)["ready"]
    with pytest.raises(startup.ProductionConfigurationError, match="only required in oidc"):
        startup.prepare_oidc_secrets(values)


def test_supabase_missing_configuration_and_sqlite_fail_closed():
    values = supabase_environment()
    del values["VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY"]
    report = startup.production_preflight(values, check_dependencies=False)
    assert report["missing_environment"] == ["VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY"]
    assert not report["ready"]
    with pytest.raises(startup.ProductionConfigurationError):
        startup.validate_production_configuration(supabase_environment() | {"VIBEFINANCE_DATABASE_URL": "sqlite:///shared.db"})


def test_preflight_reports_local_scope_only():
    report = startup.production_preflight(environment(), check_dependencies=False)
    assert report["ready"] is True
    assert report["scope"] == "local_configuration_only"
    assert report["remote_identity_verified"] is False
    assert report["database_connection_verified"] is False
    text = json.dumps(report)
    assert environment()["VIBEFINANCE_OIDC_UI_CLIENT_SECRET"] not in text
    assert "fixture" not in text


def test_empty_configuration_lists_missing_names_without_values():
    report = startup.production_preflight({}, check_dependencies=False)
    assert not report["ready"]
    assert set(report["missing_environment"]) == set(startup.SUPABASE_REQUIRED_ENVIRONMENT)


@pytest.mark.parametrize("name,value", [
    ("VIBEFINANCE_AUTH_MODE", "demo"),
    ("VIBEFINANCE_OIDC_ISSUER", "http://identity.example.test"),
    ("VIBEFINANCE_INTERNAL_AUTH_KEY", "short"),
    ("VIBEFINANCE_OIDC_AUDIENCE", "test-ui-client"),
    ("VIBEFINANCE_OIDC_UI_CLIENT_SECRET", ""),
    ("VIBEFINANCE_OIDC_COOKIE_SECRET", "short"),
    ("VIBEFINANCE_DATABASE_URL", "sqlite:///private/state.db"),
    ("VIBEFINANCE_DATABASE_URL", "postgresql://test:fixture@db.example.test/finance?sslmode=require"),
    ("VIBEFINANCE_ALLOW_INSECURE_LOCAL_DATABASE", "1"),
])
def test_invalid_production_requirements_fail_closed(name, value):
    values = environment() | {name: value}
    with pytest.raises(startup.ProductionConfigurationError):
        startup.validate_production_configuration(values)


@pytest.mark.parametrize("origin", [
    "http://finance.example.test", "https://user:password@finance.example.test",
    "https://finance.example.test/elsewhere", "https://finance.example.test?next=attacker",
    "https://finance.example.test#fragment", "https://localhost", "https://127.0.0.1",
    "https://[::1]", "https://finance.local", "https://finance.example.test:8443",
    "https://finance.example.test\n", "https://finance.example.test/\\attacker",
    "https://bad_host.example.test", "https://finance", "https://-bad.example.test",
])
def test_callback_origin_is_pinned_to_configured_public_https(origin):
    with pytest.raises(startup.ProductionConfigurationError):
        startup.validate_production_configuration(environment() | {"VIBEFINANCE_PUBLIC_URL": origin})


def test_optional_exact_host_allowlist():
    values = environment() | {"VIBEFINANCE_PUBLIC_HOSTS": "other.example.test"}
    with pytest.raises(startup.ProductionConfigurationError):
        startup.validate_production_configuration(values)
    values["VIBEFINANCE_PUBLIC_HOSTS"] = "other.example.test,FINANCE.example.test"
    assert startup.validate_production_configuration(values).mode == "oidc"


@pytest.mark.skipif(os.name != "posix", reason="Production image is Linux; mode/owner guarantees require POSIX")
def test_private_native_streamlit_secrets_are_valid_and_cleaned(tmp_path, capsys):
    directory = tmp_path / "runtime"
    values = environment()
    values["VIBEFINANCE_OIDC_UI_CLIENT_SECRET"] += "-🔐"
    path = startup.prepare_oidc_secrets(values, directory)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert path.stat().st_uid == os.getuid()
    data = tomllib.loads(path.read_text())
    assert data["auth"]["redirect_uri"] == "https://finance.example.test/oauth2callback"
    assert data["auth"]["cookie_secret"] == values["VIBEFINANCE_OIDC_COOKIE_SECRET"]
    assert data["auth"]["oidc"]["client_id"] == "test-ui-client"
    assert data["auth"]["oidc"]["client_secret"] == values["VIBEFINANCE_OIDC_UI_CLIENT_SECRET"]
    assert data["auth"]["oidc"]["server_metadata_url"] == "https://identity.example.test/tenant/.well-known/openid-configuration"
    assert capsys.readouterr() == ("", "")
    startup.cleanup_oidc_secrets(path)
    assert not path.exists()
    assert not directory.exists()


@pytest.mark.skipif(os.name != "posix", reason="Private OIDC runtime requires Linux production runtime")
def test_existing_operator_files_are_preserved_and_generated_names_unique(tmp_path):
    directory = tmp_path / "runtime"
    directory.mkdir(mode=0o700)
    operator = directory / "secrets.toml"
    operator.write_text("operator-owned-content")
    first = startup.prepare_oidc_secrets(environment(), directory)
    second = startup.prepare_oidc_secrets(environment(), directory)
    assert first != second
    startup.cleanup_oidc_secrets(operator)
    assert operator.read_text() == "operator-owned-content"
    startup.cleanup_oidc_secrets(first)
    startup.cleanup_oidc_secrets(second)
    assert directory.exists()
    assert operator.read_text() == "operator-owned-content"


@pytest.mark.skipif(os.name != "posix", reason="Private OIDC runtime requires Linux production runtime")
def test_runtime_directory_permissions_and_symlinks_rejected(tmp_path):
    directory = tmp_path / "insecure"
    directory.mkdir(mode=0o755)
    directory.chmod(0o755)
    with pytest.raises(startup.ProductionConfigurationError):
        startup.prepare_oidc_secrets(environment(), directory)
    secure = tmp_path / "secure"
    secure.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(secure, target_is_directory=True)
    with pytest.raises(startup.ProductionConfigurationError):
        startup.prepare_oidc_secrets(environment(), link)
    assert not list(secure.iterdir())


@pytest.mark.skipif(os.name != "posix", reason="Private OIDC runtime requires Linux production runtime")
def test_checkout_and_relative_runtime_directories_are_rejected():
    for directory in (startup._REPOSITORY / ".runtime" / "oidc", Path("relative")):
        with pytest.raises(startup.ProductionConfigurationError):
            startup.prepare_oidc_secrets(environment(), directory)


@pytest.mark.skipif(os.name != "posix", reason="Private OIDC runtime requires Linux production runtime")
def test_default_temporary_directory_cannot_put_secrets_in_checkout(monkeypatch):
    monkeypatch.setattr(startup.tempfile, "gettempdir", lambda: str(startup._REPOSITORY / ".runtime"))
    with pytest.raises(startup.ProductionConfigurationError, match="outside the repository"):
        startup.prepare_oidc_secrets(environment())


def test_configuration_errors_do_not_echo_bad_secrets():
    values = environment() | {"VIBEFINANCE_DATABASE_URL": "password-secret!invalid"}
    report = startup.production_preflight(values, check_dependencies=False)
    assert "password-secret" not in json.dumps(report)


def test_missing_dependencies_are_reported_without_loading_them(monkeypatch):
    monkeypatch.setattr(startup.importlib.util, "find_spec", lambda name: None)
    report = startup.production_preflight(environment())
    assert report["missing_packages"] == ["authlib", "jwt", "cryptography", "psycopg"]
    assert not report["ready"]
