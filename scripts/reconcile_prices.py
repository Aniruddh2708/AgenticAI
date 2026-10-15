"""Reconcile authorized local history without downloading or modifying inputs."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vibefinance.data.reconciliation import reconcile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path,
                        help="Local schema-1 evidence manifest; paths relative to this file")
    parser.add_argument("--output", type=Path, help="Create a new JSON report, refusing overwrite")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"),
                              parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Nonfinite JSON: {value}")))
        report = reconcile(manifest, args.manifest.resolve().parent)
    except (OSError, ValueError, TypeError) as exc:
        report = {"schema_version": 1, "kind": "price_reconciliation", "status": "invalid",
                  "findings": [{"severity": "error", "code": "invalid_manifest", "message": str(exc)}]}
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        try:
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(rendered)
        except OSError as exc:
            print(json.dumps({"status": "invalid", "code": "output_not_created", "message": str(exc)}))
            return 2
    print(rendered, end="")
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
