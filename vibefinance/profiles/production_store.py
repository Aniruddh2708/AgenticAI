"""Opt-in PostgreSQL storage bound to one authenticated OIDC account.

This module never reads or seeds the shared demo database. A verified identity
must be bound by the authentication layer, before constructing a store.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from urllib.parse import parse_qsl, urlsplit

from vibefinance.agents.base import UserProfile


class StorageUnavailableError(RuntimeError):
    """Sanitized database failure; deliberately excludes connection diagnostics."""


def account_identifier(issuer: str, subject: str) -> str:
    """Use only exact, already verified OIDC claims, never email or profile ID."""
    if not isinstance(issuer, str) or not issuer or not isinstance(subject, str) or not subject:
        raise ValueError("Verified issuer and subject are required")
    if len(issuer) > 2048 or len(subject) > 1024:
        raise ValueError("Identity claim is too long")
    encoded = json.dumps([issuer, subject], ensure_ascii=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_database_url(dsn: str, *, allow_local_insecure: bool = False) -> str:
    """Require a single URL host and verified TLS, with an explicit local test exception."""
    try:
        parts = urlsplit(dsn)
        host, port = parts.hostname, parts.port
        query = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
        keys = [key.lower() for key, _ in query]
        if (parts.scheme not in {"postgres", "postgresql"} or not host or not parts.path.strip("/")
                or parts.fragment or "," in host or len(keys) != len(set(keys))
                or any(key in keys for key in {"host", "hostaddr", "port", "service", "servicefile"})):
            raise ValueError
        if port is not None and not 1 <= port <= 65535:
            raise ValueError
        sslmode = dict(query).get("sslmode", "verify-full")
        local = host.lower() in {"localhost", "127.0.0.1", "::1"}
        if sslmode != "verify-full" and not (local and allow_local_insecure and sslmode == "disable"):
            raise ValueError
        if any(key != key.lower() for key, _ in query):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ValueError("A PostgreSQL URL with verified TLS is required; insecure loopback requires an explicit test flag") from None
    # Supplying the default explicitly prevents a weaker PGSSLMODE environment
    # setting from changing this connection's verified transport policy.
    return dsn if "sslmode" in keys else dsn + ("&" if parts.query else "?") + "sslmode=verify-full"


def _driver():
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
    except ImportError:
        raise StorageUnavailableError("Optional production database dependencies are not installed") from None
    return psycopg, dict_row, Jsonb


_SCHEMA = """
CREATE TABLE IF NOT EXISTS vf_production_schema (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1), version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS vf_production_accounts (
    account_id TEXT PRIMARY KEY CHECK (account_id ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS vf_production_profiles (
    account_id TEXT NOT NULL REFERENCES vf_production_accounts(account_id),
    user_id TEXT NOT NULL, payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(account_id, user_id));
CREATE TABLE IF NOT EXISTS vf_production_sessions (
    account_id TEXT NOT NULL, id TEXT NOT NULL, user_id TEXT NOT NULL,
    ticker TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL, metrics JSONB NOT NULL,
    PRIMARY KEY(account_id, id),
    FOREIGN KEY(account_id, user_id) REFERENCES vf_production_profiles(account_id, user_id) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS vf_production_sessions_history
    ON vf_production_sessions(account_id, user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS vf_production_decisions (
    id BIGSERIAL PRIMARY KEY, account_id TEXT NOT NULL, session_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('follow', 'watch', 'skip')),
    created_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY(account_id, session_id) REFERENCES vf_production_sessions(account_id, id) ON DELETE CASCADE);
"""
_TABLES = ("accounts", "profiles", "sessions", "decisions")


def initialize_schema(db):
    """Transactional v1 migration for app startup and explicit disaster recovery.

    The caller owns the transaction and must not commit until all restoration
    data and checks have succeeded. No identity or profile rows are inserted.
    """
    db.execute("SET LOCAL search_path = public")
    db.execute("SELECT pg_advisory_xact_lock(86423917002521)")
    db.execute(_SCHEMA)
    row = db.execute("SELECT version FROM vf_production_schema WHERE singleton=1").fetchone()
    if row is not None and row["version"] != 1:
        raise StorageUnavailableError("Unsupported production schema version")
    for name in _TABLES:
        table = f"vf_production_{name}"
        db.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        db.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        exists = db.execute("SELECT 1 FROM pg_policies WHERE schemaname=current_schema() AND tablename=%s AND policyname='account_isolation'", (table,)).fetchone()
        if not exists:
            db.execute(f"CREATE POLICY account_isolation ON {table} USING (account_id = current_setting('vibefinance.account_id', true)) WITH CHECK (account_id = current_setting('vibefinance.account_id', true))")
    db.execute("INSERT INTO vf_production_schema VALUES (1,1) ON CONFLICT DO NOTHING")
    # Managed projects can configure default grants for browser-facing roles.
    # This backend must never expose portfolio tables through their Data API.
    for role in ("PUBLIC", "anon", "authenticated", "service_role"):
        if role != "PUBLIC" and not db.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
            continue
        for name in ("schema", *_TABLES):
            db.execute(f"REVOKE ALL PRIVILEGES ON TABLE vf_production_{name} FROM {role}")
        db.execute(f"REVOKE ALL PRIVILEGES ON SEQUENCE vf_production_decisions_id_seq FROM {role}")


class _Database:
    def __init__(self, dsn: str, *, allow_local_insecure: bool = False, account_id: str = "", migrate_schema=True):
        self._account_id = account_id
        self._dsn = validate_database_url(dsn, allow_local_insecure=allow_local_insecure)
        self._psycopg, self._dict_row, self._jsonb = _driver()
        with self.connect() as db:
            role = db.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
            if role is None or role["rolsuper"] or role["rolbypassrls"]:
                raise StorageUnavailableError("The application database role must not bypass account row security")
            if not migrate_schema:
                row = db.execute("SELECT version FROM vf_production_schema WHERE singleton=1").fetchone()
                if row is None or row["version"] != 1:
                    raise StorageUnavailableError("Unsupported production schema version")
        if migrate_schema:
            self.migrate()

    @property
    def account_id(self):
        return self._account_id

    @contextmanager
    def connect(self, *, snapshot=False):
        try:
            with self._psycopg.connect(self._dsn, row_factory=self._dict_row, connect_timeout=10, prepare_threshold=None) as db:
                if snapshot:
                    db.isolation_level = self._psycopg.IsolationLevel.REPEATABLE_READ
                    db.read_only = True
                db.execute("SET LOCAL TIME ZONE 'UTC'")
                db.execute("SET LOCAL search_path = public")
                db.execute("SET LOCAL statement_timeout = '15s'")
                db.execute("SELECT set_config('vibefinance.account_id', %s, true)", (self.account_id,))
                yield db
        except self._psycopg.Error:
            raise StorageUnavailableError("Production storage is unavailable; the operation was not completed") from None

    def migrate(self):
        """Apply versioned schema and row isolation atomically, including concurrent startup."""
        with self.connect() as db:
            initialize_schema(db)


class ProductionStore(_Database):
    """Store-compatible methods; callers cannot supply another operation's tenant."""

    def __init__(self, account_id: str, dsn: str, *, allow_local_insecure: bool = False, migrate_schema=True):
        if not isinstance(account_id, str) or not re.fullmatch("[0-9a-f]{64}", account_id):
            raise ValueError("An authenticated account identifier is required")
        super().__init__(dsn, allow_local_insecure=allow_local_insecure, account_id=account_id, migrate_schema=migrate_schema)

    def profiles(self):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM vf_production_profiles WHERE account_id=%s ORDER BY user_id", (self.account_id,)).fetchall()
        return [UserProfile.model_validate(row["payload"]) for row in rows]

    def profile(self, user_id: str):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM vf_production_profiles WHERE account_id=%s AND user_id=%s", (self.account_id, user_id)).fetchone()
        if row is None:
            raise KeyError(user_id)
        return UserProfile.model_validate(row["payload"])

    def save_profile(self, profile: UserProfile):
        # Revalidate even when a caller mutates an existing pydantic instance.
        profile = UserProfile.model_validate(profile.model_dump())
        with self.connect() as db:
            db.execute("INSERT INTO vf_production_accounts(account_id) VALUES (%s) ON CONFLICT DO NOTHING", (self.account_id,))
            db.execute("INSERT INTO vf_production_profiles(account_id,user_id,payload) VALUES (%s,%s,%s) ON CONFLICT(account_id,user_id) DO UPDATE SET payload=excluded.payload,updated_at=CURRENT_TIMESTAMP", (self.account_id, profile.user_id, self._jsonb(profile.model_dump(mode="json"))))

    def delete_profile(self, user_id: str):
        with self.connect() as db:
            if db.execute("DELETE FROM vf_production_profiles WHERE account_id=%s AND user_id=%s", (self.account_id, user_id)).rowcount == 0:
                raise KeyError(user_id)

    def session(self, session_id: str):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM vf_production_sessions WHERE account_id=%s AND id=%s", (self.account_id, session_id)).fetchone()
        if row is None:
            raise KeyError(session_id)
        return row["payload"]

    def save_session(self, session: dict):
        rec = session["recommendation"]
        with self.connect() as db:
            if db.execute("SELECT 1 FROM vf_production_profiles WHERE account_id=%s AND user_id=%s", (self.account_id, rec["user_id"])).fetchone() is None:
                raise KeyError(rec["user_id"])
            db.execute("INSERT INTO vf_production_sessions(account_id,id,user_id,ticker,created_at,payload,metrics) VALUES (%s,%s,%s,%s,%s,%s,%s)", (self.account_id, session["session_id"], rec["user_id"], rec["ticker"], datetime.now(timezone.utc), self._jsonb(session), self._jsonb(session["metrics"])))

    def history(self, user_id: str, ticker: str | None = None, limit: int = 20):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("History limit must be between 1 and 100")
        query = "SELECT payload FROM vf_production_sessions WHERE account_id=%s AND user_id=%s"
        params = [self.account_id, user_id]
        if ticker:
            query += " AND ticker=%s"
            params.append(ticker)
        query += " ORDER BY created_at DESC,id DESC LIMIT %s"
        params.append(limit)
        with self.connect() as db:
            return [row["payload"] for row in db.execute(query, params).fetchall()]

    def decision(self, session_id: str, decision: str):
        if decision not in {"follow", "watch", "skip"}:
            raise ValueError("Decision must be follow, watch, or skip")
        with self.connect() as db:
            if db.execute("SELECT 1 FROM vf_production_sessions WHERE account_id=%s AND id=%s", (self.account_id, session_id)).fetchone() is None:
                raise KeyError(session_id)
            db.execute("INSERT INTO vf_production_decisions(account_id,session_id,decision,created_at) VALUES (%s,%s,%s,%s)", (self.account_id, session_id, decision, datetime.now(timezone.utc)))

    def decisions(self, session_id: str):
        with self.connect() as db:
            if db.execute("SELECT 1 FROM vf_production_sessions WHERE account_id=%s AND id=%s", (self.account_id, session_id)).fetchone() is None:
                raise KeyError(session_id)
            return [{"decision": row["decision"], "created_at": row["created_at"].isoformat()} for row in db.execute("SELECT decision,created_at FROM vf_production_decisions WHERE account_id=%s AND session_id=%s ORDER BY id", (self.account_id, session_id)).fetchall()]

    def export_account(self):
        """Consistent own-account logical snapshot, including database timestamps."""
        with self.connect(snapshot=True) as db:
            data = {"format": "vibefinance-account-v1", "account_id": self.account_id}
            for name in ("profiles", "sessions", "decisions"):
                order = {"profiles": "user_id", "sessions": "created_at,id", "decisions": "id"}[name]
                rows = db.execute(f"SELECT * FROM vf_production_{name} WHERE account_id=%s ORDER BY {order}", (self.account_id,)).fetchall()
                data[name] = [{key: value.isoformat() if isinstance(value, datetime) else value for key, value in row.items() if key != "account_id"} for row in rows]
        return data

    def import_account(self, snapshot: dict):
        """Restore only a validated own-account snapshot into an empty account."""
        data = _validate_snapshot(snapshot, self.account_id)
        with self.connect() as db:
            db.execute("INSERT INTO vf_production_accounts(account_id) VALUES (%s) ON CONFLICT DO NOTHING", (self.account_id,))
            # Serialize import with normal writes for this account. Locks on the
            # account row also prevent parallel imports passing the empty check.
            db.execute("SELECT account_id FROM vf_production_accounts WHERE account_id=%s FOR UPDATE", (self.account_id,))
            for name in ("profiles", "sessions", "decisions"):
                if db.execute(f"SELECT 1 FROM vf_production_{name} WHERE account_id=%s LIMIT 1", (self.account_id,)).fetchone():
                    raise ValueError("Restore requires an empty account; no existing data was replaced")
            for row in data["profiles"]:
                db.execute("INSERT INTO vf_production_profiles VALUES (%s,%s,%s,%s)", (self.account_id, row["user_id"], self._jsonb(row["payload"]), row["updated_at"]))
            for row in data["sessions"]:
                db.execute("INSERT INTO vf_production_sessions VALUES (%s,%s,%s,%s,%s,%s,%s)", (self.account_id, row["id"], row["user_id"], row["ticker"], row["created_at"], self._jsonb(row["payload"]), self._jsonb(row["metrics"])))
            for row in data["decisions"]:
                # IDs are database-local; preserve order, not another database's sequence.
                db.execute("INSERT INTO vf_production_decisions(account_id,session_id,decision,created_at) VALUES (%s,%s,%s,%s)", (self.account_id, row["session_id"], row["decision"], row["created_at"]))


def _validate_snapshot(snapshot, account_id):
    if not isinstance(snapshot, dict) or snapshot.get("format") != "vibefinance-account-v1" or snapshot.get("account_id") != account_id:
        raise ValueError("Snapshot must belong to the authenticated account")
    try:
        snapshot = json.loads(json.dumps(snapshot, allow_nan=False))
        profiles, sessions = set(), set()
        for name in ("profiles", "sessions", "decisions"):
            if not isinstance(snapshot[name], list):
                raise ValueError
            for row in snapshot[name]:
                if not isinstance(row, dict) or "account_id" in row:
                    raise ValueError
                timestamp = datetime.fromisoformat(row["updated_at" if name == "profiles" else "created_at"])
                if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                    raise ValueError
                if name == "profiles":
                    profile = UserProfile.model_validate(row["payload"])
                    if row["user_id"] != profile.user_id or row["user_id"] in profiles:
                        raise ValueError
                    profiles.add(row["user_id"])
                elif name == "sessions":
                    payload, rec = row["payload"], row["payload"]["recommendation"]
                    if (not isinstance(row["id"], str) or not row["id"] or row["id"] in sessions
                            or row["user_id"] not in profiles or rec["user_id"] != row["user_id"]
                            or rec["ticker"] != row["ticker"] or payload["session_id"] != row["id"]
                            or payload["metrics"] != row["metrics"]):
                        raise ValueError
                    sessions.add(row["id"])
                elif row["session_id"] not in sessions or row["decision"] not in {"follow", "watch", "skip"}:
                    raise ValueError
    except (TypeError, KeyError, ValueError, OverflowError):
        raise ValueError("Snapshot validation failed; no data was imported") from None
    return snapshot


def create_production_store(account_id: str) -> ProductionStore:
    dsn, allow_local = _configuration()
    return ProductionStore(account_id, dsn, allow_local_insecure=allow_local, migrate_schema=False)


def _configuration():
    dsn = os.getenv("VIBEFINANCE_DATABASE_URL", "")
    if not dsn:
        raise StorageUnavailableError("Production database configuration is unavailable")
    return dsn, os.getenv("VIBEFINANCE_ALLOW_INSECURE_LOCAL_DATABASE") == "1"


def initialize_production_storage():
    """Fail-closed startup check and schema migration; creates no account rows."""
    dsn, allow_local = _configuration()
    _Database(dsn, allow_local_insecure=allow_local)


def production_storage_health() -> bool:
    """Return only availability, never connection details, counts or identity."""
    try:
        dsn, allow_local = _configuration()
        _Database(dsn, allow_local_insecure=allow_local, migrate_schema=False)
        return True
    except (StorageUnavailableError, ValueError):
        return False
