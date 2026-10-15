"""Cryptographic and filesystem invariants plus real optional PostgreSQL recovery."""
import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import struct
import subprocess
import sys

import pytest

from scripts import backup_production as recovery


pytest.importorskip("cryptography")


def snapshot():
    from tests.test_production_store import snapshot as account_snapshot
    account = account_snapshot()
    return {"format": recovery._FORMAT, "tables": {
        "schema": [{"singleton": 1, "version": 1}],
        "accounts": [{"account_id": account["account_id"], "created_at": "2026-10-15T09:00:00+00:00"}],
        **{name: [{"account_id": account["account_id"], **row} for row in account[name]] for name in ("profiles", "sessions", "decisions")},
    }, "decision_sequence": {"last_value": 12, "is_called": True}}


def test_authenticated_roundtrip_hides_account_profile_and_connection_metadata():
    data = snapshot()
    key = secrets.token_bytes(32)
    artifact, header = recovery.seal_snapshot(data, key)
    restored, actual = recovery.open_snapshot(artifact, key)
    assert restored == data and actual == header
    assert header["cipher"] == "AES-256-GCM"
    assert "accounts" not in header and "profiles" not in header
    assert b"Owned profile" not in artifact and b"a" * 64 not in artifact
    assert b"postgresql://" not in artifact
    second, _ = recovery.seal_snapshot(data, key)
    assert artifact != second  # Fresh 96-bit nonce, never deterministic encryption.


def test_wrong_key_fails_independently_of_filesystem_or_database():
    artifact, _ = recovery.seal_snapshot(snapshot(), secrets.token_bytes(32))
    with pytest.raises(recovery.RecoveryError, match="authentication"):
        recovery.open_snapshot(artifact, secrets.token_bytes(32))


@pytest.mark.skipif(os.name != "posix", reason="Production recovery file operations require a POSIX owner-private runner")
@pytest.mark.parametrize("operation", ["verify", "restore_missing_configuration"])
def test_standalone_isolated_cli_validates_backup_from_external_directory(tmp_path, operation):
    # -I omits PYTHONPATH, the current directory and the script directory. A valid
    # envelope reaches the lazy application-schema import, unlike --help or an
    # invalid-key check, so this catches a broken standalone operator command.
    os.chmod(tmp_path, 0o700)
    key = secrets.token_bytes(32)
    encrypted, _ = recovery.seal_snapshot(snapshot(), key)
    source = recovery.write_artifact(encrypted, tmp_path / "backup.vfenc")
    external = tmp_path / "external-working-directory"
    external.mkdir(mode=0o700)
    environment = os.environ.copy()
    environment["VIBEFINANCE_TEST_BACKUP_KEY"] = base64.b64encode(key).decode()
    environment.pop("VIBEFINANCE_TEST_MISSING_RECOVERY_DSN", None)
    command = [sys.executable, "-I", str(Path(recovery.__file__).resolve())]
    if operation == "verify":
        command += ["verify"]
    else:
        command += ["restore", "--database-url-env", "VIBEFINANCE_TEST_MISSING_RECOVERY_DSN",
                    "--owner-role", "test_app_owner", "--confirm-empty-target"]
    command += ["--source", str(source), "--key-env", "VIBEFINANCE_TEST_BACKUP_KEY"]
    result = subprocess.run(command, cwd=external, env=environment, capture_output=True, text=True, timeout=20)
    assert not result.stderr
    response = json.loads(result.stdout)
    assert response["operation"] == ("verify" if operation == "verify" else "restore")
    assert response["ok"] == (operation == "verify")
    assert result.returncode == (0 if operation == "verify" else 1)
    assert environment["VIBEFINANCE_TEST_BACKUP_KEY"] not in result.stdout
    assert not (external / "vibefinance").exists()


@pytest.mark.parametrize("location", ["header", "nonce", "ciphertext", "tag", "truncated", "magic", "length"])
def test_every_envelope_component_is_authenticated(location):
    key = secrets.token_bytes(32)
    encoded, _ = recovery.seal_snapshot(snapshot(), key)
    artifact = bytearray(encoded)
    offset = len(recovery._MAGIC) + 4
    header_length = struct.unpack(">I", artifact[len(recovery._MAGIC):offset])[0]
    positions = {"header": offset + header_length - 3, "nonce": offset + header_length,
                 "ciphertext": offset + header_length + 12, "tag": len(artifact) - 1,
                 "magic": 0, "length": len(recovery._MAGIC)}
    if location == "truncated":
        artifact = artifact[:-10]
    else:
        artifact[positions[location]] ^= 1
    with pytest.raises(recovery.RecoveryError):
        recovery.open_snapshot(bytes(artifact), key)


def test_wrong_key_authentication_fails_before_restore_connection(monkeypatch, tmp_path, capsys):
    encoded, _ = recovery.seal_snapshot(snapshot(), secrets.token_bytes(32))
    source = tmp_path / "backup.vfenc"
    source.write_bytes(encoded)
    monkeypatch.setenv("WRONG_BACKUP_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setenv("TEST_RESTORE_URL", "postgresql://secret-user:secret-password@example.com/tenant-private-database")
    monkeypatch.setattr(recovery, "restore_database", lambda *a, **k: pytest.fail("Must authenticate before any restore call"))
    assert recovery.main(["restore", "--source", str(source), "--key-env", "WRONG_BACKUP_KEY",
                          "--database-url-env", "TEST_RESTORE_URL", "--owner-role", "vfapp", "--confirm-empty-target"]) == 1
    text = capsys.readouterr().out
    assert "secret-password" not in text and "secret-user" not in text and "tenant-private-database" not in text


@pytest.mark.parametrize("value", ["passphrase", "!" * 43, "A" * 42, "A" * 44, " " + "A" * 43])
def test_only_base64_256_bit_random_key_shape_accepted(monkeypatch, value):
    monkeypatch.setenv("BACKUP_KEY_TEST", value)
    with pytest.raises(recovery.RecoveryError):
        recovery.encryption_key("BACKUP_KEY_TEST")


def test_key_variable_name_and_urlsafe_base64(monkeypatch):
    key = secrets.token_bytes(32)
    monkeypatch.setenv("BACKUP_KEY_TEST", base64.urlsafe_b64encode(key).decode().rstrip("="))
    assert recovery.encryption_key("BACKUP_KEY_TEST") == key
    with pytest.raises(recovery.RecoveryError):
        recovery.environment_value("$(expose_environment)")
    with pytest.raises(recovery.RecoveryError):
        recovery.environment_value("NEVER_CONFIGURED_BACKUP_TEST_VALUE")


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(format="unsupported"),
    lambda s: s["tables"].update(other=[]),
    lambda s: s["tables"]["schema"][0].update(version=2),
    lambda s: s["tables"]["schema"][0].update(version=True),
    lambda s: s["tables"]["accounts"][0].update(created_at="2026-10-15T09:00:00"),
    lambda s: s["tables"]["accounts"].append(deepcopy(s["tables"]["accounts"][0])),
    lambda s: s["tables"]["profiles"][0].update(account_id="b" * 64),
    lambda s: s["tables"]["profiles"][0].update(extra="unsupported"),
    lambda s: s["tables"]["sessions"][0].update(user_id="missing"),
    lambda s: s["tables"]["decisions"][0].update(id=True),
    lambda s: s["tables"]["decisions"][0].update(id=2 ** 63),
    lambda s: s["tables"]["decisions"].append(deepcopy(s["tables"]["decisions"][0])),
    lambda s: s["decision_sequence"].update(last_value=1),
    lambda s: s["decision_sequence"].update(is_called=False),
    lambda s: s["decision_sequence"].update(last_value=True),
])
def test_unsupported_or_invalid_snapshot_rejected_before_encryption(mutate):
    data = snapshot()
    mutate(data)
    with pytest.raises(recovery.RecoveryError):
        recovery.seal_snapshot(data, secrets.token_bytes(32))


def test_restore_needs_explicit_new_empty_target_confirmation(monkeypatch):
    monkeypatch.setattr(recovery, "_connection", lambda *a, **k: pytest.fail("No connection without confirmation"))
    with pytest.raises(recovery.RecoveryError, match="Explicit confirmation"):
        recovery.restore_database(snapshot(), "postgresql://example.com/production", owner_role="vfapp")


@pytest.mark.parametrize("owner", [None, "", "postgres; DROP TABLE accounts", "one.two", "a" * 64])
def test_restore_owner_is_explicit_identifier_before_database_connection(monkeypatch, owner):
    monkeypatch.setattr(recovery, "_connection", lambda *a, **k: pytest.fail("No connection for an invalid role"))
    with pytest.raises(recovery.RecoveryError, match="owner role"):
        recovery.restore_database(snapshot(), "postgresql://example.com/target", owner_role=owner, confirm_empty_target=True)


@pytest.mark.skipif(os.name != "posix", reason="Production recovery requires a POSIX owner-private runner")
def test_private_atomic_write_verify_and_no_plaintext_temporary_files(tmp_path, monkeypatch, capsys):
    os.chmod(tmp_path, 0o700)
    key = secrets.token_bytes(32)
    artifact, _ = recovery.seal_snapshot(snapshot(), key)
    destination = tmp_path / "backup.vfenc"
    recovery.write_artifact(artifact, destination)
    assert destination.stat().st_mode & 0o777 == 0o600
    assert recovery.read_artifact(destination) == artifact
    assert set(tmp_path.iterdir()) == {destination}
    monkeypatch.setenv("VERIFY_KEY_TEST", base64.b64encode(key).decode())
    assert recovery.main(["verify", "--key-env", "VERIFY_KEY_TEST", "--source", str(destination)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] and result["existing_data_replaced"] is False


@pytest.mark.skipif(os.name != "posix", reason="POSIX file protections")
@pytest.mark.parametrize("kind", ["file", "symlink", "race", "parent_symlink", "traversal", "public_directory"])
def test_existing_paths_symlinks_races_and_insecure_destinations_never_replace(tmp_path, monkeypatch, kind):
    os.chmod(tmp_path, 0o700)
    destination = tmp_path / "backup.vfenc"
    precious = tmp_path / "precious"
    precious.write_bytes(b"existing private data")
    if kind == "file":
        destination.write_bytes(b"existing artifact")
    elif kind == "symlink":
        destination.symlink_to(precious)
    elif kind == "race":
        original_link = os.link

        def competing_link(source, target, **kwargs):
            destination.write_bytes(b"concurrent winner")
            return original_link(source, target, **kwargs)

        monkeypatch.setattr(os, "link", competing_link)
    elif kind == "parent_symlink":
        parent = tmp_path / "alias"
        parent.symlink_to(tmp_path, target_is_directory=True)
        destination = parent / "backup.vfenc"
    elif kind == "traversal":
        (tmp_path / "directory").mkdir()
        destination = tmp_path / "directory" / ".." / "backup.vfenc"
    else:
        os.chmod(tmp_path, 0o755)
    with pytest.raises((OSError, recovery.RecoveryError)):
        recovery.write_artifact(b"encrypted bytes", destination)
    assert precious.read_bytes() == b"existing private data"
    if kind == "file":
        assert destination.read_bytes() == b"existing artifact"
    elif kind == "symlink":
        assert destination.is_symlink()
    elif kind == "race":
        assert destination.read_bytes() == b"concurrent winner"
    assert not list(tmp_path.glob(".vf-encrypted-*"))


@pytest.mark.skipif(os.name != "posix", reason="POSIX file protections")
def test_symlink_and_nonregular_source_not_followed(tmp_path):
    (tmp_path / "real").write_bytes(b"encrypted")
    (tmp_path / "link").symlink_to(tmp_path / "real")
    os.mkfifo(tmp_path / "pipe")
    for source in (tmp_path / "link", tmp_path / "pipe"):
        with pytest.raises((OSError, recovery.RecoveryError)):
            recovery.read_artifact(source)


_ADMIN = os.environ.get("VIBEFINANCE_TEST_POSTGRES_ADMIN_URL")
_RESTORE = os.environ.get("VIBEFINANCE_TEST_POSTGRES_RESTORE_URL")
_APP = os.environ.get("VIBEFINANCE_TEST_POSTGRES_URL")
_RESTORE_APP = os.environ.get("VIBEFINANCE_TEST_POSTGRES_RESTORE_APP_URL")


@pytest.mark.skipif(not (_ADMIN and _RESTORE and _APP and _RESTORE_APP), reason="Owned disposable PostgreSQL admin, runtime and pristine restore targets are required")
def test_actual_postgres_encrypted_all_account_restore_preserves_state_and_is_non_destructive(tmp_path):
    psycopg = pytest.importorskip("psycopg")
    from tests.test_production_store import profile, session
    from vibefinance.profiles.production_store import ProductionStore
    # The runner provisions these separate disposable databases; never derive
    # or create a target from a real production connection automatically.
    account_a, account_b = "c" * 64, "d" * 64
    original = ProductionStore(account_a, _APP, allow_local_insecure=True)
    other = ProductionStore(account_b, _APP, allow_local_insecure=True)
    original.save_profile(profile("recovery-one", "Recovery owner one"))
    other.save_profile(profile("recovery-two", "Recovery owner two"))
    original.save_session(session("recovery-one", "recovery-session-one"))
    original.decision("recovery-session-one", "watch")
    other.save_session(session("recovery-two", "recovery-session-two"))
    other.decision("recovery-session-two", "skip")
    before = recovery.snapshot_database(_ADMIN, allow_local_insecure=True)
    key = secrets.token_bytes(32)
    encrypted, _ = recovery.seal_snapshot(before, key)
    os.chmod(tmp_path, 0o700)
    destination = recovery.write_artifact(encrypted, tmp_path / "actual-pg.vfenc")
    restored, _ = recovery.open_snapshot(recovery.read_artifact(destination), key)
    # Even an unrelated existing table blocks recovery, without changing it.
    with psycopg.connect(_RESTORE) as db:
        db.execute("CREATE EXTENSION hstore WITH SCHEMA public")
        db.execute("CREATE SCHEMA auth")
        db.execute("CREATE TABLE auth.recovery_sentinel (provider_state TEXT)")
        db.execute("INSERT INTO auth.recovery_sentinel VALUES ('provider auth unchanged')")
        db.execute("CREATE TABLE recovery_guard (valuable TEXT)")
        db.execute("INSERT INTO recovery_guard VALUES ('preserve existing state')")
    with pytest.raises(recovery.RecoveryError, match="not pristine"):
        recovery.restore_database(restored, _RESTORE, owner_role="vfapp", confirm_empty_target=True, allow_local_insecure=True)
    with psycopg.connect(_RESTORE) as db:
        assert db.execute("SELECT valuable FROM recovery_guard").fetchone() == ("preserve existing state",)
        assert db.execute("SELECT to_regclass('public.vf_production_accounts')").fetchone() == (None,)
        db.execute("DROP TABLE recovery_guard")  # Only test-owned disposable setup.
    recovery.restore_database(restored, _RESTORE, owner_role="vfapp", confirm_empty_target=True, allow_local_insecure=True)
    assert recovery.snapshot_database(_RESTORE, allow_local_insecure=True) == before
    target = ProductionStore(account_a, _RESTORE_APP, allow_local_insecure=True)
    assert target.profile("recovery-one").name == "Recovery owner one"
    assert target.history("recovery-one")[0]["session_id"] == "recovery-session-one"
    assert target.decisions("recovery-session-one")[0]["decision"] == "watch"
    assert target.export_account() == original.export_account()
    # New writes consume the restored high-water mark, without primary-key reuse.
    target.decision("recovery-session-one", "follow")
    with psycopg.connect(_RESTORE) as db:
        flags = db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='vf_production_profiles'").fetchone()
        assert flags == (True, True)
        assert db.execute("SELECT provider_state FROM auth.recovery_sentinel").fetchone() == ("provider auth unchanged",)
        assert db.execute("SELECT 'a=>b'::hstore -> 'a'").fetchone() == ("b",)
        assert db.execute("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE relname='vf_production_profiles'").fetchone() == ("vfapp",)
        maximum = db.execute("SELECT MAX(id) FROM vf_production_decisions").fetchone()[0]
    assert maximum > before["decision_sequence"]["last_value"]
    current = recovery.snapshot_database(_RESTORE, allow_local_insecure=True)
    with pytest.raises(recovery.RecoveryError, match="not pristine"):
        recovery.restore_database(restored, _RESTORE, owner_role="vfapp", confirm_empty_target=True, allow_local_insecure=True)
    assert recovery.snapshot_database(_RESTORE, allow_local_insecure=True) == current
    assert recovery.snapshot_database(_ADMIN, allow_local_insecure=True) == before


@pytest.mark.skipif(not _APP, reason="Owned disposable non-administrative PostgreSQL source is required")
def test_actual_postgres_account_role_cannot_create_silently_partial_backup():
    pytest.importorskip("psycopg")
    from vibefinance.profiles.production_store import ProductionStore
    ProductionStore("e" * 64, _APP, allow_local_insecure=True)
    with pytest.raises(recovery.RecoveryError, match="BYPASSRLS"):
        recovery.snapshot_database(_APP, allow_local_insecure=True)
