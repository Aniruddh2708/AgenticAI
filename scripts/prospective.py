"""Register, issue and monitor prospective baseline forecasts without backdating."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vibefinance.evaluation import prospective


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("register", "forecast", "missed", "outcome", "score"))
    parser.add_argument("--run-dir", default=".runtime/prospective/baselines-v1")
    parser.add_argument("--protocol", default="data/prospective_protocol.json")
    parser.add_argument("--data", help="Local reconciled session batch JSON; never downloaded automatically")
    parser.add_argument("--review", help="Operator review attestation JSON for registration")
    parser.add_argument("--artifact-root", default=".", help="Root for reconciliation artifact paths")
    parser.add_argument("--reason", help="Required issuance-failure reason for a missed scheduled origin")
    parser.add_argument("--origin", help="Previously issued origin date for matured outcomes")
    parser.add_argument("--output", help="Exclusive-create report file (score only)")
    args = parser.parse_args()
    def read(path):
        if not path:
            parser.error("This stage requires --data/--review as documented")
        return json.loads(Path(path).read_text())
    try:
        if args.stage == "register":
            result = prospective.register(args.run_dir, read(args.protocol), read(args.data), read(args.review), args.artifact_root)
        elif args.stage == "forecast":
            result = prospective.record_forecast(args.run_dir, read(args.data), args.artifact_root)
        elif args.stage == "missed":
            result = prospective.record_missed(args.run_dir, read(args.data), args.reason, args.artifact_root)
        elif args.stage == "outcome":
            if not args.origin:
                parser.error("outcome requires --origin")
            result = prospective.record_outcome(args.run_dir, args.origin, read(args.data), args.artifact_root)
        else:
            result = prospective.score(args.run_dir)
            if args.output:
                prospective._write_new(args.output, result)
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        parser.exit(2, f"Prospective workflow unavailable: {error}\n")
    print(json.dumps(result if args.stage == "score" else {"kind": result["kind"], "sha256": result["sha256"]}, indent=2))


if __name__ == "__main__":
    main()
