"""Explicit operator account export/import; shared demo state is never auto-migrated.

The operator must supply issuer/subject from a verified identity. This local
administrative CLI does not authenticate claims supplied on its command line.
Use encrypted whole-database recovery for production disaster-recovery backups.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vibefinance.profiles.production_store import (
    StorageUnavailableError, _validate_snapshot, account_identifier,
    create_production_store, initialize_production_storage,
)


def write_private_snapshot(path: Path, snapshot: dict):
    """Publish an own-account plaintext export without replacing existing files."""
    if not path.parent.is_dir() or os.path.lexists(path):
        raise ValueError("An existing private directory and new destination name are required")
    descriptor, name = tempfile.mkstemp(prefix=".vf-account-", dir=path.parent)
    temporary = Path(name)
    try:
        if os.name == "posix":
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def owned_sqlite_snapshot(path: Path, profile_ids: list[str], account_id: str):
    """Read explicitly selected, operator-owned profiles from an existing backup."""
    if not profile_ids or len(profile_ids) > 25 or len(set(profile_ids)) != len(profile_ids):
        raise ValueError("Select 1–25 distinct profiles that belong to the target account")
    source = path.resolve(strict=True)
    if not source.is_file():
        raise ValueError("An existing owned SQLite backup is required")
    placeholders = ",".join("?" for _ in profile_ids)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Source integrity check failed")
        db.execute("BEGIN")
        rows = db.execute(f"SELECT user_id,payload FROM profiles WHERE user_id IN ({placeholders}) ORDER BY user_id", profile_ids).fetchall()
        if {row[0] for row in rows} != set(profile_ids):
            raise ValueError("Every explicitly selected profile must exist")
        # SQLite has no profile timestamp. Use the actual export instant and
        # preserve original session/decision timestamps without inventing dates.
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        profiles = [{"user_id": row[0], "payload": json.loads(row[1]), "updated_at": now} for row in rows]
        rows = db.execute(f"SELECT id,user_id,ticker,created_at,payload,metrics FROM sessions WHERE user_id IN ({placeholders}) ORDER BY created_at,id", profile_ids).fetchall()
        sessions = [{"id": row[0], "user_id": row[1], "ticker": row[2], "created_at": row[3], "payload": json.loads(row[4]), "metrics": json.loads(row[5])} for row in rows]
        rows = db.execute(f"SELECT d.id,d.session_id,d.decision,d.created_at FROM decisions d JOIN sessions s ON d.session_id=s.id WHERE s.user_id IN ({placeholders}) ORDER BY d.id", profile_ids).fetchall()
        decisions = [{"id": row[0], "session_id": row[1], "decision": row[2], "created_at": row[3]} for row in rows]
    snapshot = {"format": "vibefinance-account-v1", "account_id": account_id,
                "profiles": profiles, "sessions": sessions, "decisions": decisions}
    return _validate_snapshot(snapshot, account_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("initialize", "export-account", "import-account", "import-owned-sqlite"))
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--issuer", help="Exact issuer from an already verified identity")
    parser.add_argument("--subject", help="Exact subject from that verified identity; never an email substitute")
    parser.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--confirm-owned-backup", action="store_true", help="Attest selected source profiles belong to this verified account")
    args = parser.parse_args()
    try:
        if args.operation == "initialize":
            initialize_production_storage()
            counts = {}
        else:
            if args.path is None:
                raise ValueError("A source or new destination path is required")
            owner = account_identifier(args.issuer, args.subject)
            if args.operation == "import-owned-sqlite":
                if not args.confirm_owned_backup:
                    raise ValueError("Explicit owned-backup attestation is required")
                snapshot = owned_sqlite_snapshot(args.path, args.profile_id, owner)
            elif args.operation == "import-account":
                snapshot = _validate_snapshot(json.loads(args.path.read_text(encoding="utf-8")), owner)
            else:
                snapshot = None
            store = create_production_store(owner)
            if args.operation == "export-account":
                snapshot = store.export_account()
                write_private_snapshot(args.path, snapshot)
            else:
                store.import_account(snapshot)
            counts = {name: len(snapshot[name]) for name in ("profiles", "sessions", "decisions")}
    except (StorageUnavailableError, ValueError, OSError, sqlite3.Error, KeyError):
        print(json.dumps({"ok": False, "operation": args.operation,
                          "error": "Operation failed. Check verified identity, private file permissions, valid owned input, empty target account, and configured production storage. No existing target data was replaced."}))
        return 1
    print(json.dumps({"ok": True, "operation": args.operation, "counts": counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
