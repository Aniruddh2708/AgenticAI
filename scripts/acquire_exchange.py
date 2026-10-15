"""Import authorized NSE daily raw files, or explicitly fetch spent-date evidence."""
import argparse
import json
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vibefinance.data.exchange import ExchangeDataError, MAX_ARTIFACT_BYTES, automation_permission, fetch_spent_archive, write_bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", type=Path, help="Authorized local .csv/.zip file; default import path")
    mode.add_argument("--fetch", action="store_true", help="Explicitly authorized HTTPS acquisition; requires --permission-review and dates through 2025-12-31")
    parser.add_argument("--date", required=True, help="Exact daily session YYYY-MM-DD; no date ranges or inferred holidays")
    parser.add_argument("--format", choices=("legacy", "udiff"), help="Required for fetch; local schema is detected")
    parser.add_argument("--sha256", help="Optional previously recorded source SHA-256, not an authenticity certificate")
    parser.add_argument("--permission-review", type=Path, help="Existing operator-reviewed explicit NSE automation authorization with hashed evidence")
    parser.add_argument("--output-dir", required=True, type=Path, help="New evidence directory; existing directories are refused")
    args = parser.parse_args(argv)
    try:
        if args.output_dir.exists():
            raise ExchangeDataError("output_exists", "Existing acquisition directory is preserved; choose a new path")
        review = None
        if args.fetch:
            if args.format is None:
                raise ExchangeDataError("format_required", "Explicit fetch requires --format legacy or udiff")
            review = automation_permission(args.permission_review, args.date)
            content, _ = fetch_spent_archive(args.date, args.format, args.permission_review)
            kind = "zip"
        else:
            kind = args.input.suffix.lower().lstrip(".")
            if kind not in {"csv", "zip"}:
                raise ExchangeDataError("unsupported_format", "Import a local CSV or ZIP")
            if args.input.stat().st_size > MAX_ARTIFACT_BYTES:
                raise ExchangeDataError("artifact_too_large", "Local source artifact exceeds size bound")
            content = args.input.read_bytes()
        report = write_bundle(content, args.date, args.output_dir, kind, args.sha256,
                              official_fetch=args.fetch, requested_format=args.format, permission_review=review)
        print(json.dumps(report, indent=2, allow_nan=False))
        return 0
    except (ExchangeDataError, OSError, httpx.HTTPError, ValueError) as exc:
        print(json.dumps({"schema_version": 1, "kind": "nse_raw_acquisition", "status": "permission_required" if getattr(exc, "code", None) == "permission_required" else "failed",
                          "code": getattr(exc, "code", "acquisition_failed"), "message": str(exc),
                          "independently_reconciled": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
