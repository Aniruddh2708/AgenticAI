"""Replay existing policy constraints on the frozen historical price test dates."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.forecast import implementation_hashes
from vibefinance.data.historical import load
from vibefinance.evaluation.forecast import fingerprint
from vibefinance.evaluation.historical_policy import historical_policy_evaluation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", default=".runtime/forecast")
    args = parser.parse_args()
    directory = Path(args.run_dir)
    output = directory / "policies.json"
    if output.exists():
        raise ValueError("Historical policy replay already recorded; read policies.json without overwriting")
    frozen = json.loads((directory / "selection.json").read_text(encoding="utf-8"))
    identity = frozen.pop("selection_id")
    if fingerprint(frozen) != identity:
        raise ValueError("Frozen selection was modified")
    if implementation_hashes() != frozen["implementation_sha256"]:
        raise ValueError("Research implementation changed after selection was frozen")
    frames, _ = load(frozen["source_manifest"], frozen["data_directory"])
    report = asyncio.run(historical_policy_evaluation(frames, frozen))
    report["selection_id"] = identity
    report["evaluated_at_utc"] = datetime.now(timezone.utc).isoformat()
    root = Path(__file__).resolve().parent.parent
    report["implementation_sha256"] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in ("scripts/historical_policies.py", "vibefinance/evaluation/historical_policy.py",
                     "vibefinance/orchestrator.py", "vibefinance/synthesis/synthesizer.py",
                     "vibefinance/agents/base.py", "vibefinance/agents/momentum_agent.py",
                     "vibefinance/agents/volume_agent.py", "vibefinance/agents/risk_agent.py")}
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({key: report[key] for key in ("selection_id", "price_window_count",
        "profile_decision_count", "action_counts", "policy_checks", "limitations")}, indent=2))


if __name__ == "__main__":
    main()
