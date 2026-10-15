"""Create one new restricted backend login using an owned database's admin access.

Read ADMIN_DATABASE_URL and VIBEFINANCE_APP_ROLE_PASSWORD from private environment
bindings. Never put either value in arguments. This operation does not provision
a database or alter an existing role. The application connection must use the
new role, not the administrator connection used by this local operator tool.
"""
import argparse
import json
import os
from pathlib import Path
import sys

# Direct operator invocation must work outside the checkout, without relying on
# a Docker PYTHONPATH or the caller's current working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vibefinance.profiles.production_store import StorageUnavailableError, _driver, validate_database_url

APP_ROLE = "vibefinance_app"


def bootstrap_role(admin_url: str, password: str, *, allow_local_insecure=False):
    if not isinstance(password, str) or len(password) < 24 or len(password) > 1024 or "\x00" in password:
        raise ValueError("A new private password of at least 24 characters is required")
    url = validate_database_url(admin_url, allow_local_insecure=allow_local_insecure)
    psycopg, dict_row, _ = _driver()
    from psycopg import sql
    try:
        with psycopg.connect(url, row_factory=dict_row, connect_timeout=10, prepare_threshold=None) as db:
            db.execute("SET LOCAL statement_timeout = '15s'")
            db.execute("SELECT pg_advisory_xact_lock(86423917002522)")
            if db.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (APP_ROLE,)).fetchone():
                raise ValueError("The application role already exists; no role was changed")
            if not db.execute("SELECT 1 FROM pg_namespace WHERE nspname='public'").fetchone():
                raise ValueError("The expected application schema is unavailable")
            if db.execute("SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ('vf_production_schema','vf_production_accounts','vf_production_profiles','vf_production_sessions','vf_production_decisions','vf_production_decisions_id_seq')").fetchone():
                raise ValueError("Application tables already exist; review ownership before any migration")
            db.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT").format(sql.Identifier(APP_ROLE), sql.Literal(password)))
            db.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(db.info.dbname), sql.Identifier(APP_ROLE)))
            db.execute(sql.SQL("GRANT USAGE,CREATE ON SCHEMA public TO {}").format(sql.Identifier(APP_ROLE)))
            row = db.execute("SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication FROM pg_roles WHERE rolname=%s", (APP_ROLE,)).fetchone()
            if row is None or any(row.values()):
                raise StorageUnavailableError("Restricted application role verification failed")
    except psycopg.Error:
        raise StorageUnavailableError("Restricted application role creation failed; no existing role was changed") from None
    return APP_ROLE


def main(argv=None):
    # Help and invalid arguments must exit before credentials are read or any
    # administrative database operation is attempted.
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        role = bootstrap_role(os.getenv("ADMIN_DATABASE_URL", ""), os.getenv("VIBEFINANCE_APP_ROLE_PASSWORD", ""),
                              allow_local_insecure=os.getenv("VIBEFINANCE_ALLOW_INSECURE_LOCAL_DATABASE") == "1")
    except (StorageUnavailableError, ValueError):
        print(json.dumps({"ok": False, "error": "Bootstrap failed. Check private admin configuration, verified TLS, a new strong password, role-creation permission, and that the application role and tables do not already exist. No existing role was changed."}))
        return 1
    print(json.dumps({"ok": True, "role": role, "existing_roles_changed": False,
                      "next": "Configure the application DSN with the new role and verify it over TLS; never deploy the admin DSN."}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
