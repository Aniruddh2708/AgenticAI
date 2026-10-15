"""Import explicitly permitted authentic text; never modifies the default corpus."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vibefinance.rag.authentic import import_corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = import_corpus(args.manifest, args.output_dir)
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"status": "invalid", "reason": "Check source hashes, permissions, identity, timestamps and new output directory; no successful import claimed."}))
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
