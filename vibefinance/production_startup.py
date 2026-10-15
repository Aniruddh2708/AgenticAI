"""Fail-closed production configuration and private native-Streamlit OIDC setup.

This module performs no network discovery or remote resource creation. Its CLI
reports configuration readiness only, never authentication or database readiness.
"""
from __future__ import annotations

import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import stat
import tempfile
from urllib.parse import urlsplit

from vibefinance.auth import AuthSettings, AuthConfigurationError
from vibefinance.profiles.production_store import validate_database_url


class ProductionConfigurationError(ValueError):
    """Safe operator-facing error, deliberately excludes environment values."""


OIDC_REQUIRED_ENVIRONMENT = (
    "VIBEFINANCE_AUTH_MODE", "VIBEFINANCE_OIDC_ISSUER",
    "VIBEFINANCE_OIDC_AUDIENCE", "VIBEFINANCE_OIDC_UI_CLIENT_ID",
    "VIBEFINANCE_INTERNAL_AUTH_KEY", "VIBEFINANCE_OIDC_UI_CLIENT_SECRET",
    "VIBEFINANCE_OIDC_COOKIE_SECRET", "VIBEFINANCE_PUBLIC_URL",
    "VIBEFINANCE_DATABASE_URL",
)
SUPABASE_REQUIRED_ENVIRONMENT = (
    "VIBEFINANCE_AUTH_MODE", "VIBEFINANCE_SUPABASE_URL",
    "VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY", "VIBEFINANCE_PUBLIC_URL",
    "VIBEFINANCE_DATABASE_URL",
)
# Retained for callers explicitly checking the optional OIDC configuration.
REQUIRED_ENVIRONMENT = OIDC_REQUIRED_ENVIRONMENT
_OWNED_FILES: set[Path] = set()
_OWNED_DIRECTORIES: set[Path] = set()
_REPOSITORY = Path(__file__).resolve().parents[1]


def _public_origin(values):
    """Use the configured origin only, never request Host/forwarded headers."""
    value = values.get("VIBEFINANCE_PUBLIC_URL", "")
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname
                or parts.username is not None or parts.password is not None
                or parts.query or parts.fragment or parts.path not in {"", "/"}
                or parts.port not in {None, 443}
                or any(character.isspace() for character in value)):
            raise ValueError
        host = parts.hostname.lower()
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".localhost")):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or not all(part and all(c.isascii() and (c.isalnum() or c == "-") for c in part)
                                          and not part.startswith("-") and not part.endswith("-")
                                          for part in host.split(".")):
                raise ValueError
        else:
            if not address.is_global:
                raise ValueError
        configured_hosts = values.get("VIBEFINANCE_PUBLIC_HOSTS", "")
        if configured_hosts and host not in {part.strip().lower() for part in configured_hosts.split(",")}:
            raise ValueError
        # Retain the operator's exact HTTPS origin (including an explicit :443).
        return value.rstrip("/")
    except (ValueError, TypeError, AttributeError):
        raise ProductionConfigurationError(
            "VIBEFINANCE_PUBLIC_URL must be a public HTTPS origin; an optional VIBEFINANCE_PUBLIC_HOSTS must allow its exact host."
        ) from None


def validate_production_configuration(environ=None):
    """Validate production identity and verified database transport without I/O."""
    values = os.environ if environ is None else environ
    mode = values.get("VIBEFINANCE_AUTH_MODE")
    if mode not in {"supabase", "oidc"}:
        raise ProductionConfigurationError("Production requires VIBEFINANCE_AUTH_MODE=supabase or oidc.")
    try:
        settings = AuthSettings.from_env(values)
    except (AuthConfigurationError, TypeError, ValueError):
        raise ProductionConfigurationError("Managed authentication configuration is incomplete or invalid for the selected mode.") from None
    if mode == "oidc":
        if not values.get("VIBEFINANCE_OIDC_UI_CLIENT_SECRET", "").strip():
            raise ProductionConfigurationError("VIBEFINANCE_OIDC_UI_CLIENT_SECRET is required.")
        if len(values.get("VIBEFINANCE_OIDC_COOKIE_SECRET", "").encode("utf-8")) < 32:
            raise ProductionConfigurationError("VIBEFINANCE_OIDC_COOKIE_SECRET must contain at least 32 bytes.")
    if values.get("VIBEFINANCE_ALLOW_INSECURE_LOCAL_DATABASE") == "1":
        raise ProductionConfigurationError("The production launcher does not permit insecure local database mode.")
    try:
        validate_database_url(values.get("VIBEFINANCE_DATABASE_URL", ""))
    except (ValueError, TypeError):
        raise ProductionConfigurationError("VIBEFINANCE_DATABASE_URL must select PostgreSQL with sslmode=verify-full.") from None
    _public_origin(values)
    return settings


def production_preflight(environ=None, *, check_dependencies=True):
    """Return safe local checks. Passing does not establish remote acceptance."""
    values = os.environ if environ is None else environ
    required = OIDC_REQUIRED_ENVIRONMENT if values.get("VIBEFINANCE_AUTH_MODE") == "oidc" else SUPABASE_REQUIRED_ENVIRONMENT
    missing = [name for name in required if not values.get(name)]
    errors = []
    try:
        validate_production_configuration(values)
    except ProductionConfigurationError as exc:
        errors.append(str(exc))
    packages = ("authlib", "jwt", "cryptography", "psycopg") if values.get("VIBEFINANCE_AUTH_MODE") == "oidc" else ("jwt", "cryptography", "psycopg")
    missing_packages = [name for name in packages if importlib.util.find_spec(name) is None] if check_dependencies else []
    return {
        "ready": not missing and not errors and not missing_packages,
        "scope": "local_configuration_only", "missing_environment": missing,
        "configuration_errors": errors, "missing_packages": missing_packages,
        "remote_identity_verified": False, "database_connection_verified": False,
    }


def _private_directory(requested):
    if os.name != "posix":
        raise ProductionConfigurationError("Private production OIDC runtime files require the Linux production runtime.")
    if requested is None:
        base = Path(tempfile.gettempdir()).resolve()
        if base == _REPOSITORY or _REPOSITORY in base.parents:
            raise ProductionConfigurationError("The OIDC runtime directory must be outside the repository.")
        directory = Path(tempfile.mkdtemp(prefix="vibefinance-oidc-", dir=base))
        _OWNED_DIRECTORIES.add(directory)
        return directory
    directory = Path(requested)
    if not directory.is_absolute() or directory.resolve() != directory:
        raise ProductionConfigurationError("The OIDC runtime directory must be absolute and contain no symlinks.")
    if directory == _REPOSITORY or _REPOSITORY in directory.parents:
        raise ProductionConfigurationError("The OIDC runtime directory must be outside the repository.")
    try:
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            pass
        else:
            _OWNED_DIRECTORIES.add(directory)
        details = directory.lstat()
    except OSError:
        raise ProductionConfigurationError("Unable to create the private OIDC runtime directory.") from None
    if (not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid()
            or stat.S_IMODE(details.st_mode) != 0o700):
        raise ProductionConfigurationError("The OIDC runtime directory must be owned by the server account with mode 0700.")
    return directory


def prepare_oidc_secrets(environ=None, runtime_dir=None):
    """Atomically write a unique 0600 TOML file; use ``--secrets.files PATH``.

    Values come only from secure server environment variables. They are never
    returned as text, logged, written to the checkout or read from operator files.
    """
    values = os.environ if environ is None else environ
    settings = validate_production_configuration(values)
    if settings.mode != "oidc":
        raise ProductionConfigurationError("Native Streamlit OIDC secrets are only required in oidc mode.")
    directory = _private_directory(runtime_dir if runtime_dir is not None else values.get("VIBEFINANCE_RUNTIME_SECRETS_DIR"))
    payload = "\n".join((
        "[auth]", "redirect_uri = " + json.dumps(_public_origin(values) + "/oauth2callback", ensure_ascii=False),
        "cookie_secret = " + json.dumps(values["VIBEFINANCE_OIDC_COOKIE_SECRET"], ensure_ascii=False),
        "", "[auth.oidc]", "client_id = " + json.dumps(settings.ui_client_id, ensure_ascii=False),
        "client_secret = " + json.dumps(values["VIBEFINANCE_OIDC_UI_CLIENT_SECRET"], ensure_ascii=False),
        "server_metadata_url = " + json.dumps(settings.issuer.rstrip("/") + "/.well-known/openid-configuration", ensure_ascii=False), "",
    ))
    temporary = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".oidc-", dir=directory)
        temporary = Path(temporary_name)
        target = directory / (temporary.name.removeprefix(".") + ".toml")
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        _OWNED_FILES.add(target)
        return target
    except OSError:
        raise ProductionConfigurationError("Unable to create the private OIDC runtime configuration.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def cleanup_oidc_secrets(path):
    """Remove only files generated by this process; never operator secrets."""
    path = Path(path)
    if path not in _OWNED_FILES:
        return
    path.unlink(missing_ok=True)
    _OWNED_FILES.discard(path)
    if path.parent in _OWNED_DIRECTORIES:
        try:
            path.parent.rmdir()
        except OSError:
            return
        _OWNED_DIRECTORIES.discard(path.parent)


def main():
    report = production_preflight()
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
