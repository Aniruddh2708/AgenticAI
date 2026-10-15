"""Storage unit checks and opt-in tests against a real disposable PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from urllib.parse import quote, urlsplit, urlunsplit

import pytest

from vibefinance.agents.base import UserProfile
from vibefinance.profiles.production_store import (
    ProductionStore, StorageUnavailableError, _validate_snapshot,
    account_identifier, create_production_store, initialize_production_storage,
    production_storage_health, validate_database_url,
)
from scripts.migrate_production import owned_sqlite_snapshot, write_private_snapshot
from scripts.bootstrap_production_role import APP_ROLE, bootstrap_role
from vibefinance.profiles.store import Store


def test_account_identifier_uses_verified_issuer_and_subject_not_display_name():
    expected = hashlib.sha256(json.dumps(["https://issuer.example", "subject"], separators=(",", ":")).encode()).hexdigest()
    assert account_identifier("https://issuer.example", "subject") == expected
    assert account_identifier("https://issuer.example", "subject") != account_identifier("https://other.example", "subject")
    assert account_identifier("ab", "c") != account_identifier("a", "bc")


@pytest.mark.parametrize("issuer,subject", [("", "x"), ("x", ""), (None, "x"), ("x", None), ("x" * 2049, "s"), ("i", "x" * 1025)])
def test_account_identifier_rejects_invalid_claims(issuer, subject):
    with pytest.raises(ValueError):
        account_identifier(issuer, subject)


@pytest.mark.parametrize("dsn", [
    "", "host=example.com dbname=app", "sqlite:///file", "postgresql:///app",
    "postgresql://example.com/app?sslmode=disable", "postgresql://example.com/app?sslmode=require",
    "postgresql://example.com/app?sslmode=verify-ca", "postgresql://localhost/app?sslmode=disable",
    "postgresql://example.com/app?host=localhost", "postgresql://example.com/app?hostaddr=127.0.0.1",
    "postgresql://example.com/app?service=other", "postgresql://example.com/app?port=5432",
    "postgresql://example.com/app?sslmode=verify-full&sslmode=disable", "postgresql://example.com/app#other",
    "postgresql://example.com:0/app", "postgresql://one,two/app", "postgresql://example.com/app?SSLMode=verify-full",
])
def test_database_transport_rejects_weak_or_ambiguous_configuration(dsn):
    with pytest.raises(ValueError):
        validate_database_url(dsn)


def test_database_transport_pins_verified_tls_and_local_exception_is_explicit():
    assert validate_database_url("postgresql://example.com/app").endswith("?sslmode=verify-full")
    assert validate_database_url("postgresql://example.com/app?application_name=vf").endswith("&sslmode=verify-full")
    local = "postgresql://127.0.0.1/app?sslmode=disable"
    assert validate_database_url(local, allow_local_insecure=True) == local
    with pytest.raises(ValueError):
        validate_database_url("postgresql://example.com/app?sslmode=disable", allow_local_insecure=True)


def test_unconfigured_storage_fails_closed(monkeypatch):
    monkeypatch.delenv("VIBEFINANCE_DATABASE_URL", raising=False)
    with pytest.raises(StorageUnavailableError):
        initialize_production_storage()
    with pytest.raises(StorageUnavailableError):
        create_production_store("a" * 64)
    assert production_storage_health() is False


@pytest.mark.parametrize("account", [None, "", "user", "a" * 63, "A" * 64, "' OR 1=1 --"])
def test_production_store_rejects_non_authenticated_account_before_connecting(account):
    with pytest.raises(ValueError):
        ProductionStore(account, "postgresql://example.com/app")


def profile(user_id="portfolio", name="Owned profile"):
    return UserProfile(user_id=user_id, name=name, risk_tolerance="moderate", horizon_months=12,
                       holdings={"ITC.NS": .1}, max_single_stock_pct=.2)


def session(user_id="portfolio", session_id="session"):
    return {"session_id": session_id, "recommendation": {"user_id": user_id, "ticker": "ITC.NS"}, "metrics": {"latency_ms": 1}, "sources": []}


def snapshot(account="a" * 64):
    return {"format": "vibefinance-account-v1", "account_id": account,
            "profiles": [{"user_id": "portfolio", "payload": profile().model_dump(), "updated_at": "2026-10-15T10:00:00+00:00"}],
            "sessions": [{"id": "session", "user_id": "portfolio", "ticker": "ITC.NS", "created_at": "2026-10-15T11:00:00+00:00", "payload": session(), "metrics": {"latency_ms": 1}}],
            "decisions": [{"id": 7, "session_id": "session", "decision": "watch", "created_at": "2026-10-15T12:00:00+00:00"}]}


@pytest.mark.parametrize("mutation", [
    lambda s: s.update(account_id="b" * 64),
    lambda s: s["profiles"][0].update(account_id="b" * 64),
    lambda s: s["profiles"][0].update(user_id="other"),
    lambda s: s["profiles"][0].update(updated_at="2026-10-15T10:00:00"),
    lambda s: s["sessions"][0].update(user_id="other"),
    lambda s: s["sessions"][0].update(metrics={}),
    lambda s: s["sessions"][0]["payload"].update(session_id="other"),
    lambda s: s["decisions"][0].update(session_id="other"),
    lambda s: s["decisions"][0].update(decision="trade"),
    lambda s: s["profiles"].append(deepcopy(s["profiles"][0])),
    lambda s: s["sessions"].append(deepcopy(s["sessions"][0])),
])
def test_snapshot_restore_validates_ownership_references_and_payloads(mutation):
    data = snapshot()
    mutation(data)
    with pytest.raises(ValueError):
        _validate_snapshot(data, "a" * 64)


def test_explicit_sqlite_migration_includes_only_selected_owned_profiles(tmp_path):
    original = Store(tmp_path / "owned.sqlite3")
    original.save_profile(profile("mine"))
    original.save_profile(profile("other"))
    original.save_session(session("mine", "mine-session"))
    original.save_session(session("other", "other-session"))
    original.decision("mine-session", "watch")
    original.decision("other-session", "skip")
    before = (tmp_path / "owned.sqlite3").read_bytes()
    migrated = owned_sqlite_snapshot(original.path, ["mine"], "a" * 64)
    assert [p["user_id"] for p in migrated["profiles"]] == ["mine"]
    assert [s["id"] for s in migrated["sessions"]] == ["mine-session"]
    assert [d["decision"] for d in migrated["decisions"]] == ["watch"]
    assert original.path.read_bytes() == before
    for selection in ([], ["mine", "mine"], ["absent"]):
        with pytest.raises(ValueError):
            owned_sqlite_snapshot(original.path, selection, "a" * 64)


def test_account_export_is_private_and_never_overwrites_or_follows_symlinks(tmp_path):
    target = tmp_path / "own-account.json"
    write_private_snapshot(target, snapshot())
    assert json.loads(target.read_text()) == snapshot()
    if os.name == "posix":
        assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError):
        write_private_snapshot(target, snapshot("b" * 64))
    assert json.loads(target.read_text())["account_id"] == "a" * 64
    if os.name == "posix":
        link = tmp_path / "alias.json"
        link.symlink_to(target)
        with pytest.raises(ValueError):
            write_private_snapshot(link, snapshot())


@pytest.mark.parametrize("password", [None, "", "short", "x" * 1025, "x" * 24 + "\x00"])
def test_role_bootstrap_rejects_weak_password_without_connecting(password):
    with pytest.raises(ValueError):
        bootstrap_role("postgresql://example.com/app", password)


@pytest.mark.parametrize("arguments,exit_code", [(["--help"], 0), (["--unsupported"], 2)])
def test_role_bootstrap_help_and_invalid_arguments_never_read_credentials_or_mutate(monkeypatch, capsys, arguments, exit_code):
    import scripts.bootstrap_production_role as module
    def forbidden(*args, **kwargs):
        raise AssertionError("Argument handling attempted an administrative operation")
    monkeypatch.setattr(module, "bootstrap_role", forbidden)
    # Patch only this module's environment accessor; argument processing must
    # complete before the first private setting is requested.
    monkeypatch.setattr(module.os, "getenv", forbidden)
    with pytest.raises(SystemExit) as exc:
        module.main(arguments)
    assert exc.value.code == exit_code
    captured = capsys.readouterr()
    assert "usage:" in (captured.out if exit_code == 0 else captured.err)


@pytest.mark.parametrize("script", ["bootstrap_production_role.py", "migrate_production.py"])
@pytest.mark.parametrize("operation", ["help", "missing-config", "invalid"])
def test_operator_cli_runs_with_isolated_python_from_external_directory(tmp_path, script, operation):
    command = [sys.executable, "-I", str(Path(__file__).resolve().parents[1] / "scripts" / script)]
    environment = os.environ.copy()
    # No repository PYTHONPATH or inherited administrator/application database
    # setting may make this subprocess test accidentally access real storage.
    for key in tuple(environment):
        if key.startswith("VIBEFINANCE_") or key in {"PYTHONPATH", "ADMIN_DATABASE_URL"}:
            environment.pop(key)
    if operation == "help":
        command.append("--help")
        expected = 0
    elif operation == "invalid":
        command.append("--unsupported-operation")
        expected = 2
    else:
        if script == "migrate_production.py":
            command.append("initialize")
        expected = 1
    result = subprocess.run(command, cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=15)
    assert result.returncode == expected, result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert "Traceback" not in result.stderr
    if operation == "help":
        assert "usage:" in result.stdout
    elif operation == "invalid":
        assert "usage:" in result.stderr
    else:
        assert json.loads(result.stdout)["ok"] is False


_DSN = os.getenv("VIBEFINANCE_TEST_POSTGRES_URL")
integration = pytest.mark.skipif(not _DSN, reason="Opt-in real PostgreSQL integration requires a disposable database URL")


@pytest.fixture
def accounts():
    return (account_identifier("https://test.invalid", str(uuid.uuid4())), account_identifier("https://test.invalid", str(uuid.uuid4())))


def pg_store(account):
    return ProductionStore(account, _DSN, allow_local_insecure=True)


@integration
def test_postgres_concurrent_schema_migration_and_no_demo_seeding(accounts):
    with ThreadPoolExecutor(max_workers=6) as pool:
        stores = list(pool.map(pg_store, [accounts[0]] * 6))
    assert all(s.profiles() == [] for s in stores)
    with stores[0].connect() as db:
        assert db.execute("SELECT 1 FROM vf_production_accounts WHERE account_id=%s", (accounts[0],)).fetchone() is None
        assert db.execute("SELECT version FROM vf_production_schema").fetchone()["version"] == 1


@integration
def test_postgres_factory_and_public_health_never_repeat_startup_migration(accounts, monkeypatch):
    import vibefinance.profiles.production_store as module
    monkeypatch.setenv("VIBEFINANCE_DATABASE_URL", _DSN)
    # Explicit migration is a startup/operator operation, never a public poll.
    initialize_production_storage()
    def forbidden_migration(db):
        raise AssertionError("Request or health check attempted DDL")
    monkeypatch.setattr(module, "initialize_schema", forbidden_migration)
    factory_store = create_production_store(accounts[0])
    assert factory_store.profiles() == []
    assert production_storage_health() is True


@integration
def test_postgres_tenant_isolation_including_shared_profile_and_session_ids(accounts):
    first, second = map(pg_store, accounts)
    first.save_profile(profile(name="First"))
    second.save_profile(profile(name="Second"))
    first.save_session(session())
    assert second.history("portfolio") == []
    for operation in (second.session, second.decisions):
        with pytest.raises(KeyError):
            operation("session")
    with pytest.raises(KeyError):
        second.decision("session", "follow")
    second.save_session(session())
    first.decision("session", "watch")
    second.decision("session", "skip")
    assert first.profile("portfolio").name == "First"
    assert second.profile("portfolio").name == "Second"
    assert first.decisions("session")[0]["decision"] == "watch"
    assert second.decisions("session")[0]["decision"] == "skip"
    first.delete_profile("portfolio")
    assert first.history("portfolio") == []
    with pytest.raises(KeyError):
        first.session("session")
    assert second.session("session") == session()


@integration
def test_postgres_database_row_security_blocks_unscoped_reads_and_cross_account_writes(accounts):
    first, second = map(pg_store, accounts)
    first.save_profile(profile(name="First"))
    second.save_profile(profile(name="Second"))
    with first.connect() as db:
        role = db.execute("SELECT rolsuper FROM pg_roles WHERE rolname=current_user").fetchone()
        assert not role["rolsuper"], "Integration must use a nonsuperuser role to exercise forced RLS"
        rows = db.execute("SELECT account_id FROM vf_production_profiles").fetchall()
        assert rows and {row["account_id"] for row in rows} == {accounts[0]}
    with pytest.raises(StorageUnavailableError):
        with first.connect() as db:
            db.execute("INSERT INTO vf_production_profiles(account_id,user_id,payload) VALUES (%s,%s,%s)", (accounts[1], "forbidden", first._jsonb(profile("forbidden").model_dump())))
    assert second.profiles()[0].name == "Second"


@integration
def test_postgres_privileged_application_connection_is_refused(accounts):
    admin_url = os.getenv("VIBEFINANCE_TEST_POSTGRES_ADMIN_URL")
    if not admin_url:
        pytest.skip("Privileged disposable test connection not supplied")
    with pytest.raises(StorageUnavailableError, match="must not bypass"):
        ProductionStore(accounts[0], admin_url, allow_local_insecure=True)


@integration
def test_postgres_public_browser_roles_cannot_read_production_tables(accounts):
    store = pg_store(accounts[0])
    with store.connect() as db:
        assert not db.execute("SELECT EXISTS(SELECT 1 FROM pg_class c, LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a WHERE c.oid='vf_production_profiles'::regclass AND a.grantee=0) AS allowed").fetchone()["allowed"]
        for role in ("anon", "authenticated", "service_role"):
            if db.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                assert not db.execute("SELECT has_table_privilege(%s, 'vf_production_profiles', 'SELECT') AS allowed", (role,)).fetchone()["allowed"]


@integration
def test_postgres_role_bootstrap_creates_restricted_new_role_and_never_changes_existing():
    # Use a separate pristine database: bootstrap refuses application tables.
    admin_url = os.getenv("VIBEFINANCE_TEST_POSTGRES_BOOTSTRAP_URL")
    if not admin_url:
        pytest.skip("Separate pristine bootstrap test database not supplied")
    import psycopg
    assert bootstrap_role(admin_url, "local-random-test-password-0123456789", allow_local_insecure=True) == APP_ROLE
    with psycopg.connect(admin_url) as db:
        row = db.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls,rolreplication,rolinherit FROM pg_roles WHERE rolname=%s", (APP_ROLE,)).fetchone()
        assert row == (False, False, False, False, False, False)
    with pytest.raises(ValueError, match="already exists"):
        bootstrap_role(admin_url, "different-test-password-0123456789", allow_local_insecure=True)
    parts = urlsplit(admin_url)
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    netloc = APP_ROLE + ":" + quote("local-random-test-password-0123456789") + "@" + host
    if parts.port:
        netloc += ":" + str(parts.port)
    restricted_url = urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))
    owned = ProductionStore(account_identifier("https://test.invalid", "bootstrapped-owner"), restricted_url, allow_local_insecure=True)
    owned.save_profile(profile())
    assert owned.profile("portfolio") == profile()


@integration
def test_postgres_sql_parameterization_ownership_and_limits(accounts):
    first = pg_store(accounts[0])
    identifier = "' ; DROP TABLE vf_production_profiles; --"
    first.save_profile(profile(identifier))
    first.save_session(session(identifier, identifier))
    assert first.session(identifier) == session(identifier, identifier)
    assert first.history(identifier)[0]["session_id"] == identifier
    with pytest.raises(KeyError):
        first.save_session(session("unowned"))
    for limit in (0, 101, True, "20"):
        with pytest.raises(ValueError):
            first.history(identifier, limit=limit)
    first.delete_profile(identifier)
    assert first.profiles() == []


@integration
def test_postgres_account_export_restore_atomic_and_no_merge(accounts):
    store = pg_store(accounts[0])
    store.import_account(snapshot(accounts[0]))
    exported = store.export_account()
    assert exported["profiles"] == snapshot(accounts[0])["profiles"]
    assert exported["sessions"] == snapshot(accounts[0])["sessions"]
    assert store.decisions("session")[0]["decision"] == "watch"
    with pytest.raises(ValueError):
        store.import_account(exported)
    assert store.export_account() == exported
    other = pg_store(accounts[1])
    with pytest.raises(ValueError):
        other.import_account(exported)
    assert other.profiles() == []
    broken = snapshot(accounts[1])
    broken["decisions"][0]["session_id"] = "other"
    with pytest.raises(ValueError):
        other.import_account(broken)
    assert other.profiles() == []


@integration
def test_postgres_late_restore_constraint_failure_rolls_back_every_insert(accounts):
    store = pg_store(accounts[0])
    data = snapshot(accounts[0])
    # This passes identity/reference validation but fails the database NOT NULL
    # constraint after the profile insertion; the whole transaction must abort.
    data["sessions"][0]["ticker"] = None
    data["sessions"][0]["payload"]["recommendation"]["ticker"] = None
    with pytest.raises(StorageUnavailableError):
        store.import_account(data)
    assert store.profiles() == []
    assert store.history("portfolio") == []


@integration
def test_postgres_reconnect_durability_and_schema_version_rejection(accounts):
    store = pg_store(accounts[0])
    store.save_profile(profile())
    store.save_session(session())
    store.decision("session", "follow")
    reopened = pg_store(accounts[0])
    assert reopened.profile("portfolio") == profile()
    assert reopened.session("session") == session()
    assert reopened.decisions("session")[0]["created_at"].endswith("+00:00")
    with store.connect() as db:
        db.execute("UPDATE vf_production_schema SET version=999 WHERE singleton=1")
    try:
        with pytest.raises(StorageUnavailableError, match="Unsupported"):
            pg_store(accounts[0])
    finally:
        with store.connect() as db:
            db.execute("UPDATE vf_production_schema SET version=1 WHERE singleton=1")
