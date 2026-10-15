"""Reproduce development-v2, never score a purported fresh holdout.

Run `download` explicitly, then `run` in a new run directory. Hash-verified raw
files stay ignored. Reports are exclusively created and cannot replace old runs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vibefinance.data.historical import download, load, read_manifest
from vibefinance.data.quality import audit, digest
from vibefinance.evaluation.development import run, validate_protocol


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["download", "run"])
    parser.add_argument("--data-dir", type=Path, default=Path(".runtime/forecast-development/data"))
    parser.add_argument("--run-dir", type=Path, default=Path(".runtime/forecast-development/v2-run1"))
    parser.add_argument("--protocol", type=Path, default=Path("data/forecast_development_v2_protocol.json"))
    args = parser.parse_args()
    manifest = read_manifest("data/forecast_followup_manifest.json")
    if args.stage == "download":
        download(manifest, args.data_dir)
        print("Five pinned vendor artifacts and license verified; no evaluation performed.")
        return
    protocol = json.loads(args.protocol.read_text())
    validate_protocol(protocol)
    args.run_dir.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [root / "scripts/develop_forecast.py", root / "vibefinance/evaluation/development.py",
                        root / "vibefinance/data/quality.py", root / "vibefinance/evaluation/uncertainty.py",
                        root / "vibefinance/evaluation/forecast.py", root / "vibefinance/data/historical.py"]}
    write_new(args.run_dir/"registration.json", {"protocol": protocol, "sha256": digest(protocol),
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "implementation_sha256": hashes,
        "scope": "local development registration, not independent prospective timestamp evidence"})
    quality = audit(manifest, args.data_dir)
    write_new(args.run_dir/"quality.json", quality)
    hard = ("duplicates", "intraday_labels", "nonfinite_cells", "nonpositive_price_cells",
            "negative_or_fractional_volumes", "ohlc_bound_violations")
    if any(any(s[k] for k in hard) or not s["chronological"] for s in quality["sources"]):
        raise ValueError("Vendor data contains unresolved hard defects; inspect quality.json")
    # A local quality inventory cannot grant F1 approval. Exploratory fitting
    # retains known source limitations and the original uniform zero-volume rule.
    scoped = {**manifest, "study_end": "2023-12-31"}
    frames, metadata = load(scoped, args.data_dir)
    report = run(frames, protocol)
    import numpy as np
    import pandas as pd
    report.update(created_at_utc=datetime.now(timezone.utc).isoformat(),
        source_manifest=manifest, source_metadata=metadata, quality_sha256=digest(quality),
        implementation_sha256=hashes,
        runtime={"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__})
    write_new(args.run_dir/"report.json", report)
    # Compact reviewable output excludes full row predictions and coefficients.
    summary = {k: v for k, v in report.items() if k not in {"development_rows", "calibration_rows", "eligibility"}}
    summary["complete_report_sha256"] = hashlib.sha256((args.run_dir/"report.json").read_bytes()).hexdigest()
    write_new(args.run_dir/"summary.json", summary)
    print(json.dumps({"model_id": report["model_id"], "probability": report["selection"]["probability_selection"]["chosen"],
                      "return": report["selection"]["return_selection"]["chosen"],
                      "rows": report["development"]["sample_size"], "admission": report["admission"]}, indent=2))


if __name__ == "__main__":
    main()
