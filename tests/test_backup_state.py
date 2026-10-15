import os
from pathlib import Path
import sqlite3
import threading

import pytest

from scripts.backup_state import StateCopyError, copy_state
from scripts import backup_state
from vibefinance.profiles.store import Store


def test_backup_and_restore_actual_profiles_sessions_and_decisions(tmp_path):
    original = Store(tmp_path / "source.sqlite3")
    profile = original.profile("arjun")
    profile.name = "Restored investor"
    original.save_profile(profile)
    session = {"session_id": "saved-session", "recommendation": {
        "user_id": "arjun", "ticker": "RELIANCE.NS", "action": "WATCH"}, "metrics": {"elapsed_ms": 8}}
    original.save_session(session)
    original.decision("saved-session", "watch")
    backup = copy_state(original.path, tmp_path / "backup.sqlite3")
    # Subsequent live edits must not mutate the snapshot.
    profile.name = "Changed later"
    original.save_profile(profile)
    restored_path = copy_state(backup, tmp_path / "restored.sqlite3")
    restored = Store(restored_path)
    assert restored.profile("arjun").name == "Restored investor"
    assert restored.session("saved-session") == session
    assert restored.history("arjun")[0] == session
    assert restored.decisions("saved-session")[0]["decision"] == "watch"
    assert original.profile("arjun").name == "Changed later"
    if os.name == "posix":
        assert backup.stat().st_mode & 0o777 == 0o600
        assert restored_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("kind", ["missing", "garbage", "unrelated"])
def test_invalid_source_creates_no_destination_or_temporary_files(tmp_path, kind):
    source, destination = tmp_path / "source.db", tmp_path / "destination.db"
    if kind == "garbage":
        source.write_text("not a database")
    elif kind == "unrelated":
        with sqlite3.connect(source) as db:
            db.execute("CREATE TABLE unrelated(value)")
    with pytest.raises((OSError, StateCopyError)):
        copy_state(source, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".vibefinance-state-*"))
    if kind == "missing":
        assert not source.exists()


def test_existing_destination_and_symlink_are_never_replaced(tmp_path):
    original = Store(tmp_path / "source.db")
    destination = tmp_path / "precious.db"
    destination.write_bytes(b"preserve exactly")
    with pytest.raises(FileExistsError):
        copy_state(original.path, destination)
    assert destination.read_bytes() == b"preserve exactly"
    link = tmp_path / "link.db"
    link.symlink_to(destination)
    with pytest.raises(FileExistsError):
        copy_state(original.path, link)
    assert link.is_symlink()
    assert destination.read_bytes() == b"preserve exactly"
    with pytest.raises(FileExistsError):
        copy_state(original.path, original.path)
    assert Store(original.path).profile("arjun")


def test_destination_race_does_not_overwrite_winner(tmp_path, monkeypatch):
    original = Store(tmp_path / "source.db")
    destination = tmp_path / "raced.db"
    real_link = os.link

    def concurrent_creator(source, target):
        Path(target).write_bytes(b"concurrent winner")
        return real_link(source, target)

    monkeypatch.setattr(os, "link", concurrent_creator)
    with pytest.raises(FileExistsError):
        copy_state(original.path, destination)
    assert destination.read_bytes() == b"concurrent winner"
    assert not list(tmp_path.glob(".vibefinance-state-*"))


def test_online_backup_includes_wal_and_consistent_concurrent_transaction(tmp_path):
    original = Store(tmp_path / "source.db")
    # Keep the WAL open while snapshotting: a plain file copy can miss this data.
    writer = sqlite3.connect(original.path, check_same_thread=False)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE snapshot_pairs(first INTEGER, second INTEGER)")
    writer.execute("INSERT INTO snapshot_pairs VALUES (0,0)")
    writer.commit()
    started, finish = threading.Event(), threading.Event()
    errors = []

    def update():
        try:
            for value in range(1, 101):
                with writer:
                    writer.execute("UPDATE snapshot_pairs SET first=?", (value,))
                    writer.execute("UPDATE snapshot_pairs SET second=?", (value,))
                started.set()
                if finish.wait(0.001):
                    break
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=update)
    thread.start()
    try:
        assert started.wait(5)
        backup = copy_state(original.path, tmp_path / "online.db")
        with sqlite3.connect(backup) as db:
            first, second = db.execute("SELECT first,second FROM snapshot_pairs").fetchone()
            assert 1 <= first == second <= 100
            assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    finally:
        finish.set()
        thread.join(5)
        writer.close()
    assert not thread.is_alive()
    assert not errors


def test_non_posix_copy_does_not_require_fchmod_or_directory_fsync(tmp_path, monkeypatch):
    original = Store(tmp_path / "source.db")
    monkeypatch.setattr(backup_state, "_POSIX", False)

    def unsupported(*args):
        pytest.fail("POSIX-only operation was used")

    monkeypatch.setattr(os, "fchmod", unsupported, raising=False)
    real_fsync = os.fsync

    def regular_file_fsync(fd):
        import stat
        assert stat.S_ISREG(os.fstat(fd).st_mode)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", regular_file_fsync)
    assert Store(copy_state(original.path, tmp_path / "portable.db")).profile("arjun")


@pytest.mark.skipif(os.name != "posix", reason="Directory fsync is a POSIX durability check")
def test_final_durability_failure_is_reported_without_destroying_published_copy(tmp_path, monkeypatch):
    original = Store(tmp_path / "source.db")
    destination = tmp_path / "published.db"

    def failed_sync(_):
        raise OSError("simulated directory fsync failure")

    monkeypatch.setattr(backup_state, "_sync_directory", failed_sync)
    with pytest.raises(OSError):
        copy_state(original.path, destination)
    assert Store(destination).profile("arjun")
    with pytest.raises(FileExistsError):
        copy_state(original.path, destination)
