import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from vibefinance.agents.base import UserProfile
from vibefinance.config import ROOT, STATE_DIR


class Store:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else STATE_DIR / "vibefinance.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS profiles(user_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                ticker TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL, metrics TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY, session_id TEXT NOT NULL,
                decision TEXT NOT NULL, created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            if db.execute("SELECT 1 FROM metadata WHERE key='seeded'").fetchone() is None:
                for data in json.loads((ROOT / "data/users.json").read_text()):
                    profile = UserProfile.model_validate(data)
                    db.execute("INSERT OR IGNORE INTO profiles VALUES (?,?)", (profile.user_id, profile.model_dump_json()))
                db.execute("INSERT OR IGNORE INTO metadata VALUES ('seeded','1')")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def profiles(self):
        with self.connect() as db:
            return [UserProfile.model_validate_json(r[0]) for r in db.execute("SELECT payload FROM profiles ORDER BY user_id")]

    def profile(self, user_id: str):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM profiles WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            raise KeyError(user_id)
        return UserProfile.model_validate_json(row[0])

    def save_profile(self, profile: UserProfile):
        with self.connect() as db:
            db.execute("INSERT INTO profiles VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET payload=excluded.payload",
                       (profile.user_id, profile.model_dump_json()))

    def delete_profile(self, user_id: str):
        with self.connect() as db:
            if db.execute("DELETE FROM profiles WHERE user_id=?", (user_id,)).rowcount == 0:
                raise KeyError(user_id)

    def session(self, session_id: str):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(session_id)
        return json.loads(row[0])

    def save_session(self, session: dict):
        rec = session["recommendation"]
        with self.connect() as db:
            db.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?)", (session["session_id"], rec["user_id"], rec["ticker"],
                       datetime.now(timezone.utc).isoformat(), json.dumps(session), json.dumps(session["metrics"])))

    def history(self, user_id: str, ticker: str | None = None, limit: int = 20):
        query = "SELECT payload FROM sessions WHERE user_id=?"
        params = [user_id]
        if ticker:
            query += " AND ticker=?"
            params.append(ticker)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute(query, params)]

    def decision(self, session_id: str, decision: str):
        if decision not in {"follow", "watch", "skip"}:
            raise ValueError("Decision must be follow, watch, or skip")
        with self.connect() as db:
            if db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone() is None:
                raise KeyError(session_id)
            db.execute("INSERT INTO decisions(session_id,decision,created_at) VALUES (?,?,?)",
                       (session_id, decision, datetime.now(timezone.utc).isoformat()))

    def decisions(self, session_id: str):
        with self.connect() as db:
            return [{"decision": row[0], "created_at": row[1]} for row in
                    db.execute("SELECT decision,created_at FROM decisions WHERE session_id=? ORDER BY id", (session_id,))]
