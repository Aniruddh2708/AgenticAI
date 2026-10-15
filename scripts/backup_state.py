"""Create a consistent SQLite backup or restore it to a new, private file.

Both operations use SQLite's online backup API, validate the copied database,
and publish it atomically without replacing any existing destination.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile


class StateCopyError(ValueError):
    """The requested state copy could not be safely completed."""


_POSIX = os.name == "posix"
_COLUMNS = {
    "profiles": {"user_id", "payload"},
    "sessions": {"id", "user_id", "ticker", "created_at", "payload", "metrics"},
    "decisions": {"id", "session_id", "decision", "created_at"},
    "metadata": {"key", "value"},
}


def _private_mode(fd, path):
    if _POSIX:
        os.fchmod(fd, 0o600)
    else:
        # Windows chmod is not an ACL editor. The caller must restrict access
        # through the destination directory's inherited ACL before copying.
        os.chmod(path, 0o600)


def _sync_directory(path):
    if _POSIX:
        directory_fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)


def _validate(db):
    if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise StateCopyError("SQLite integrity validation failed.")
    for table, columns in _COLUMNS.items():
        actual = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
        if not columns <= actual:
            raise StateCopyError("Source is not a compatible VibeFinance state database.")


def copy_state(source: Path | str, destination: Path | str) -> Path:
    """Copy committed state, including WAL data, without touching existing files.

    The destination's parent must already exist. The source is opened read-only;
    failed validation leaves no destination. A same-directory temporary file and
    exclusive hard link provide atomic publication with no overwrite race.
    """
    source = Path(source).resolve(strict=True)
    destination = Path(destination).absolute()
    if not source.is_file():
        raise StateCopyError("Source must be an existing database file.")
    if not destination.parent.is_dir():
        raise StateCopyError("Destination parent directory must already exist.")
    if os.path.lexists(destination):
        raise FileExistsError("Destination already exists; no files were replaced.")
    fd, temporary_name = tempfile.mkstemp(prefix=".vibefinance-state-", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb"):
            _private_mode(fd, temporary)
        # mode=ro avoids accidentally creating a database for a mistyped source.
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=10)) as original:
            with closing(sqlite3.connect(temporary)) as copied:
                original.backup(copied, pages=64, sleep=0.01)
                _validate(copied)
        # Windows _commit/FlushFileBuffers requires a writable handle. SQLite
        # connections are closed; reopening for update does not alter contents.
        with temporary.open("r+b") as completed:
            os.fsync(completed.fileno())
        os.link(temporary, destination)  # Atomic; fails if another writer wins.
        _sync_directory(destination.parent)
        return destination
    except sqlite3.Error as exc:
        raise StateCopyError("SQLite state copy or validation failed.") from exc
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("backup", "restore"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, help="New file in an existing private directory; never overwritten.")
    args = parser.parse_args()
    try:
        destination = copy_state(args.source, args.destination)
    except (OSError, StateCopyError):
        # Avoid echoing database contents or SQLite diagnostics into shared logs.
        print(json.dumps({"operation": args.operation, "ok": False,
                          "error": "Copy failed. Check source validity, private directory access, and a new destination name. A final durability failure may leave a complete destination; inspect it before retrying."}))
        return 1
    print(json.dumps({"operation": args.operation, "ok": True, "destination": str(destination),
                      "integrity": "ok", "existing_files_replaced": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
