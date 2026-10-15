"""Explicit download -> prepare -> test stages; preserves spent holdouts."""
import argparse
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vibefinance.data.historical import download, load, read_manifest
from vibefinance.evaluation.forecast import Protocol, evaluate, fingerprint, prepare


def implementation_hashes():
    root = Path(__file__).resolve().parent.parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in (
        "vibefinance/evaluation/forecast.py", "vibefinance/data/historical.py", "scripts/forecast.py")}


def write_new(path, data):
    with Path(path).open("x") as handle:
        json.dump(data, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["download", "prepare", "test"])
    parser.add_argument("--manifest", default="data/forecast_manifest.json")
    parser.add_argument("--protocol", default="data/forecast_protocol.json")
    parser.add_argument("--data-dir", default=".runtime/forecast/data")
    parser.add_argument("--run-dir", default=".runtime/forecast")
    args = parser.parse_args()
    directory = Path(args.run_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if args.stage == "download":
        manifest = read_manifest(args.manifest)
        download(manifest, args.data_dir)
        frames, metadata = load(manifest, args.data_dir)
        print(json.dumps({"downloaded_and_verified": [{"ticker": s["ticker"], "rows": s["rows"],
            "date_start": s["date_start"], "date_end": s["date_end"], "sha256": s["sha256"]} for s in metadata]}, indent=2))
        return
    if args.stage == "prepare":
        if (directory / "selection.json").exists() or (directory / "report.json").exists():
            raise ValueError("Run already frozen/spent; do not overwrite or retune a reported holdout")
        manifest = read_manifest(args.manifest)
        frames, metadata = load(manifest, args.data_dir)
        protocol = Protocol(**json.loads(Path(args.protocol).read_text()))
        frozen = prepare(frames, metadata, protocol)
        frozen["created_at_utc"] = datetime.now(timezone.utc).isoformat()
        frozen["source_manifest"] = manifest
        frozen["data_directory"] = str(Path(args.data_dir).resolve())
        import numpy as np
        import pandas as pd
        frozen["runtime"] = {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__}
        frozen["implementation_sha256"] = implementation_hashes()
        frozen["selection_id"] = fingerprint(frozen)
        write_new(directory / "selection.json", frozen)
        print(json.dumps({"selection_id": frozen["selection_id"], "selection": frozen["selection"],
                          "validation": frozen["validation"], "calibration": frozen["calibration"]}, indent=2))
        return
    if (directory / "report.json").exists():
        raise ValueError("Held-out test already reported; read report.json rather than repeat tuning")
    frozen = json.loads((directory / "selection.json").read_text())
    identity = frozen.pop("selection_id")
    if fingerprint(frozen) != identity:
        raise ValueError("Frozen selection was modified")
    if implementation_hashes() != frozen["implementation_sha256"]:
        raise ValueError("Research implementation changed after model selection was frozen")
    frames, _ = load(frozen["source_manifest"], frozen["data_directory"])
    report = evaluate(frames, frozen)
    report["selection_id"] = identity
    report["evaluated_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["runtime"] = frozen["runtime"]
    write_new(directory / "report.json", report)
    print(json.dumps({"selection": report["selection"], "test": report["test"]}, indent=2))


if __name__ == "__main__":
    main()
