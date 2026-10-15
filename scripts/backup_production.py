"""Encrypted, versioned VibeFinance application backup and empty-database recovery.

This is an application logical snapshot, not a PostgreSQL cluster backup. It
does not copy roles, grants, extensions, arbitrary SQL objects, or other apps.
Connection URLs and encryption keys are read from named environment variables.
"""
import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import struct
import sys


# Direct operator invocation must work from any directory, including Python's
# isolated mode where PYTHONPATH and the checkout working directory are absent.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class RecoveryError(ValueError):
    """A sanitized application recovery error, excluding private data."""


_MAGIC = b"VFPROD1\x00"
_FORMAT = "vibefinance-production-backup-v1"
_MAX_BYTES = 128 * 1024 * 1024
_TABLES = {
    "schema": ("singleton", "version"),
    "accounts": ("account_id", "created_at"),
    "profiles": ("account_id", "user_id", "payload", "updated_at"),
    "sessions": ("account_id", "id", "user_id", "ticker", "created_at", "payload", "metrics"),
    "decisions": ("id", "account_id", "session_id", "decision", "created_at"),
}
_ORDER = {"schema": "singleton", "accounts": "account_id", "profiles": "account_id,user_id",
          "sessions": "account_id,id", "decisions": "id"}


def environment_value(name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise RecoveryError("A valid environment variable name is required")
    value = os.environ.get(name)
    if not value:
        raise RecoveryError("The named configuration variable is not available")
    return value


def encryption_key(name):
    """A fresh random 256-bit key, base64 encoded; no human passphrases."""
    try:
        encoded = environment_value(name)
        if len(encoded) not in (43, 44):
            raise ValueError
        key = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
        if len(key) != 32:
            raise ValueError
    except (ValueError, TypeError):
        raise RecoveryError("The key variable must contain a base64-encoded random 32-byte key") from None
    return key


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def _crypto():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        raise RecoveryError("Optional production encryption dependencies are not installed") from None
    return AESGCM


def seal_snapshot(snapshot, key):
    _validate_snapshot(snapshot)
    plaintext = _json_bytes(snapshot)
    if len(plaintext) > _MAX_BYTES:
        raise RecoveryError("Application snapshot exceeds the supported in-memory backup limit")
    header = {"format": _FORMAT, "schema_version": 1, "cipher": "AES-256-GCM",
              "created_at": datetime.now(timezone.utc).isoformat(),
              "snapshot_sha256": hashlib.sha256(plaintext).hexdigest(), "snapshot_bytes": len(plaintext)}
    encoded = _json_bytes(header)
    prefix = _MAGIC + struct.pack(">I", len(encoded)) + encoded
    nonce = secrets.token_bytes(12)
    return prefix + nonce + _crypto()(key).encrypt(nonce, plaintext, prefix), header


def open_snapshot(artifact, key):
    """Authenticate before parsing or connecting to any restore target."""
    try:
        if not isinstance(artifact, bytes) or not artifact.startswith(_MAGIC) or len(artifact) > _MAX_BYTES + 8192:
            raise ValueError
        offset = len(_MAGIC) + 4
        length = struct.unpack(">I", artifact[len(_MAGIC):offset])[0]
        if not 1 <= length <= 4096 or len(artifact) < offset + length + 28:
            raise ValueError
        prefix = artifact[:offset + length]
        header = json.loads(artifact[offset:offset + length])
        if (set(header) != {"format", "schema_version", "cipher", "created_at", "snapshot_sha256", "snapshot_bytes"}
                or header["format"] != _FORMAT or type(header["schema_version"]) is not int or header["schema_version"] != 1
                or header["cipher"] != "AES-256-GCM"
                or not isinstance(header["snapshot_bytes"], int) or isinstance(header["snapshot_bytes"], bool)
                or not 0 < header["snapshot_bytes"] <= _MAX_BYTES
                or not re.fullmatch(r"[0-9a-f]{64}", header["snapshot_sha256"])):
            raise ValueError
        when = datetime.fromisoformat(header["created_at"])
        if when.tzinfo is None or when.utcoffset() is None:
            raise ValueError
        nonce = artifact[len(prefix):len(prefix) + 12]
        plaintext = _crypto()(key).decrypt(nonce, artifact[len(prefix) + 12:], prefix)
        if len(plaintext) != header["snapshot_bytes"] or hashlib.sha256(plaintext).hexdigest() != header["snapshot_sha256"]:
            raise ValueError
        snapshot = json.loads(plaintext)
        _validate_snapshot(snapshot)
        return snapshot, header
    except RecoveryError:
        raise
    except Exception:
        # Includes InvalidTag, JSON diagnostics and unsupported envelope input.
        raise RecoveryError("Backup authentication or format validation failed; no database was changed") from None


def _validate_snapshot(snapshot):
    """Bound the schema and validate account snapshots before any restore SQL."""
    from vibefinance.profiles.production_store import _validate_snapshot as validate_account
    try:
        if (not isinstance(snapshot, dict) or set(snapshot) != {"format", "tables", "decision_sequence"}
                or snapshot["format"] != _FORMAT or not isinstance(snapshot["tables"], dict)
                or set(snapshot["tables"]) != set(_TABLES)):
            raise ValueError
        tables = snapshot["tables"]
        for name, columns in _TABLES.items():
            if not isinstance(tables[name], list) or any(not isinstance(row, dict) or set(row) != set(columns) for row in tables[name]):
                raise ValueError
        if (tables["schema"] != [{"singleton": 1, "version": 1}]
                or any(type(value) is not int for value in tables["schema"][0].values())):
            raise ValueError
        accounts = set()
        for row in tables["accounts"]:
            if not isinstance(row["account_id"], str) or not re.fullmatch("[0-9a-f]{64}", row["account_id"]) or row["account_id"] in accounts:
                raise ValueError
            timestamp = datetime.fromisoformat(row["created_at"])
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError
            accounts.add(row["account_id"])
        seen_ids = set()
        for row in tables["decisions"]:
            number = row["id"]
            if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number < 2 ** 63 or number in seen_ids:
                raise ValueError
            seen_ids.add(number)
        for name in ("profiles", "sessions", "decisions"):
            if any(row["account_id"] not in accounts for row in tables[name]):
                raise ValueError
        for account in accounts:
            data = {"format": "vibefinance-account-v1", "account_id": account}
            for name in ("profiles", "sessions", "decisions"):
                data[name] = [{k: v for k, v in row.items() if k != "account_id"} for row in tables[name] if row["account_id"] == account]
            validate_account(data, account)
        sequence = snapshot["decision_sequence"]
        if (not isinstance(sequence, dict) or set(sequence) != {"last_value", "is_called"}
                or isinstance(sequence["last_value"], bool) or not isinstance(sequence["last_value"], int)
                or not 1 <= sequence["last_value"] < 2 ** 63 or not isinstance(sequence["is_called"], bool)
                or sequence["last_value"] < max(seen_ids, default=1)
                or (seen_ids and not sequence["is_called"])):
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError):
        raise RecoveryError("Unsupported or invalid application snapshot") from None


@contextmanager
def _connection(database_url, allow_local_insecure):
    from vibefinance.profiles.production_store import validate_database_url
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        raise RecoveryError("Optional production database dependencies are not installed") from None
    try:
        dsn = validate_database_url(database_url, allow_local_insecure=allow_local_insecure)
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10,
                             application_name="vibefinance-private-recovery") as db:
            yield db
    except psycopg.Error:
        raise RecoveryError("Database recovery operation failed; private database diagnostics were withheld") from None


def snapshot_database(database_url, *, allow_local_insecure=False):
    """One MVCC snapshot across every account; requires an explicit DBA role."""
    with _connection(database_url, allow_local_insecure) as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        # Implicit pg_catalog is searched before public while current_schema()
        # remains public, so the shared initializer creates public app tables.
        db.execute("SET LOCAL search_path = public")
        db.execute("SET LOCAL TIME ZONE 'UTC'")
        db.execute("SET LOCAL statement_timeout = '60s'")
        db.execute("SET LOCAL row_security = off")
        role = db.execute("SELECT rolsuper OR rolbypassrls AS allowed FROM pg_roles WHERE rolname=current_user").fetchone()
        if not role or not role["allowed"]:
            raise RecoveryError("Full application backup requires a dedicated DBA role with BYPASSRLS")
        actual = {row["table_name"] for row in db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'").fetchall()}
        if actual != {"vf_production_" + name for name in _TABLES}:
            raise RecoveryError("Source is not exactly the supported versioned application schema")
        tables = {}
        for name, columns in _TABLES.items():
            table = "vf_production_" + name
            actual_columns = {r["column_name"] for r in db.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", (table,)).fetchall()}
            if actual_columns != set(columns):
                raise RecoveryError("Unsupported application table version")
            # All identifiers are fixed constants above, never caller input.
            rows = db.execute(f"SELECT {','.join(columns)} FROM public.{table} ORDER BY {_ORDER[name]}").fetchall()
            tables[name] = [{k: v.isoformat() if isinstance(v, datetime) else v for k, v in row.items()} for row in rows]
        sequence = dict(db.execute("SELECT last_value,is_called FROM public.vf_production_decisions_id_seq").fetchone())
    snapshot = {"format": _FORMAT, "tables": tables, "decision_sequence": sequence}
    _validate_snapshot(snapshot)
    return snapshot


def restore_database(snapshot, database_url, *, owner_role, confirm_empty_target=False, allow_local_insecure=False):
    """Transactionally restore into a separately provisioned empty app namespace.

    Never drops objects, overwrites rows, disables constraints, or changes the
    source database. An object collision rolls the entire import back.
    """
    if not confirm_empty_target:
        raise RecoveryError("Explicit confirmation of a new empty restore target is required")
    if not isinstance(owner_role, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", owner_role):
        raise RecoveryError("An explicit existing non-administrative application owner role is required")
    _validate_snapshot(snapshot)
    from vibefinance.profiles.production_store import initialize_schema
    from psycopg import sql
    from psycopg.types.json import Jsonb
    with _connection(database_url, allow_local_insecure) as db:
        db.execute("SET LOCAL search_path = public")
        db.execute("SET LOCAL TIME ZONE 'UTC'")
        db.execute("SET LOCAL statement_timeout = '60s'")
        db.execute("SELECT pg_advisory_xact_lock(86423917002521)")
        role = db.execute("SELECT rolsuper OR rolbypassrls AS allowed FROM pg_roles WHERE rolname=current_user").fetchone()
        if not role or not role["allowed"]:
            raise RecoveryError("Full application restore requires a dedicated DBA role with BYPASSRLS")
        owner = db.execute("SELECT rolcanlogin,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=%s", (owner_role,)).fetchone()
        if not owner or not owner["rolcanlogin"] or owner["rolsuper"] or owner["rolbypassrls"]:
            raise RecoveryError("The application owner must be an existing login role without row-security bypass")
        # Provider Auth/storage schemas are deliberately outside this application
        # snapshot. Existing extension-owned public functions/types are safe to
        # leave intact; all other public user objects block restoration.
        objects = db.execute("""WITH RECURSIVE extension_objects AS (
            SELECT classid,objid FROM pg_depend WHERE deptype='e' AND refclassid='pg_extension'::regclass
            UNION SELECT d.classid,d.objid FROM pg_depend d JOIN extension_objects e
              ON d.refclassid=e.classid AND d.refobjid=e.objid WHERE d.deptype IN ('i','a'))
            SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname = 'public' AND NOT EXISTS
              (SELECT 1 FROM extension_objects e WHERE e.classid='pg_class'::regclass AND e.objid=c.oid)
            UNION ALL SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname = 'public' AND NOT EXISTS
              (SELECT 1 FROM extension_objects e WHERE e.classid='pg_proc'::regclass AND e.objid=p.oid)
            UNION ALL SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
            WHERE n.nspname = 'public' AND NOT EXISTS
              (SELECT 1 FROM extension_objects e WHERE e.classid='pg_type'::regclass AND e.objid=t.oid)
            LIMIT 1""").fetchone()
        if objects:
            raise RecoveryError("Restore application's public namespace is not pristine; existing objects and data were preserved")
        db.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(owner_role)))
        initialize_schema(db)
        db.execute("RESET ROLE")
        for name, columns in _TABLES.items():
            if name == "schema":  # The schema initializer inserted its version marker.
                continue
            placeholders = ",".join("%s" for _ in columns)
            for row in snapshot["tables"][name]:
                values = [Jsonb(row[c]) if c in {"payload", "metrics"} else row[c] for c in columns]
                db.execute(f"INSERT INTO public.vf_production_{name} ({','.join(columns)}) VALUES ({placeholders})", values)
        sequence = snapshot["decision_sequence"]
        db.execute("SELECT setval('public.vf_production_decisions_id_seq'::regclass,%s,%s)", (sequence["last_value"], sequence["is_called"]))


@contextmanager
def _private_parent(path, *, require_private=False):
    if os.name != "posix":
        raise RecoveryError("Use a POSIX recovery runner with owner-only directory permissions")
    path = Path(path).absolute()
    if ".." in path.parts or path.name in {"", ".", ".."}:
        raise RecoveryError("A direct file path without parent traversal is required")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    # Walk directory handles rather than checking then reopening a pathname;
    # swapping any parent for a symlink cannot redirect the final operation.
    parent = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:-1]:
            following = os.open(part, flags, dir_fd=parent)
            os.close(parent)
            parent = following
        metadata = os.fstat(parent)
        if require_private and (metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077):
            raise RecoveryError("Destination directory must be owned by this operator with mode 0700")
        yield path.name, parent
    finally:
        os.close(parent)


def write_artifact(artifact, destination):
    """Private, fsynced, exclusive atomic publication; no plaintext temp files."""
    with _private_parent(destination, require_private=True) as (name, parent):
        temporary = ".vf-encrypted-" + secrets.token_hex(16)
        fd = None
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(fd, "wb") as stream:
                fd = None
                os.fchmod(stream.fileno(), 0o600)
                stream.write(artifact)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            os.fsync(parent)
        finally:
            if fd is not None:
                os.close(fd)
            try:
                os.unlink(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass
    return Path(destination).absolute()


def read_artifact(source):
    with _private_parent(source) as (name, parent):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > _MAX_BYTES + 8192:
                raise RecoveryError("Backup must be a regular file within the supported size limit")
            artifact = stream.read(_MAX_BYTES + 8193)
            if len(artifact) > _MAX_BYTES + 8192:
                raise RecoveryError("Backup exceeds the supported size limit")
            return artifact


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for operation in ("backup", "verify", "restore"):
        command = sub.add_parser(operation)
        command.add_argument("--key-env", default="VIBEFINANCE_BACKUP_KEY", help="Name of the base64 32-byte key variable; never its value")
        if operation == "backup":
            command.add_argument("--destination", type=Path, required=True)
        else:
            command.add_argument("--source", type=Path, required=True)
        if operation != "verify":
            command.add_argument("--database-url-env", default="VIBEFINANCE_DATABASE_URL", help="Name of the configured database URL variable; never its value")
            command.add_argument("--allow-local-insecure", action="store_true", help="Disposable loopback-only integration tests")
        if operation == "restore":
            command.add_argument("--confirm-empty-target", action="store_true", help="Target is a separately provisioned deployment with an empty public application namespace")
            command.add_argument("--owner-role", required=True, help="Existing non-administrative application login role that will own restored tables")
    args = parser.parse_args(argv)
    try:
        key = encryption_key(args.key_env)
        if args.operation == "backup":
            snapshot = snapshot_database(environment_value(args.database_url_env), allow_local_insecure=args.allow_local_insecure)
            artifact, header = seal_snapshot(snapshot, key)
            write_artifact(artifact, args.destination)
        else:
            snapshot, header = open_snapshot(read_artifact(args.source), key)
            if args.operation == "restore":
                restore_database(snapshot, environment_value(args.database_url_env), owner_role=args.owner_role, confirm_empty_target=args.confirm_empty_target,
                                 allow_local_insecure=args.allow_local_insecure)
        print(json.dumps({"operation": args.operation, "ok": True, "format": header["format"],
                          "created_at": header["created_at"], "snapshot_sha256": header["snapshot_sha256"],
                          "existing_data_replaced": False}))
        return 0
    except (RecoveryError, OSError, ValueError):
        print(json.dumps({"operation": args.operation, "ok": False,
                          "error": "Recovery failed. Check named configuration, authentication, private file permissions, compatible source schema and a new empty target. No existing objects were replaced. A final file durability failure may leave a complete encrypted artifact; verify it before retrying."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
