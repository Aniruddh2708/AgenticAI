import json
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vibefinance.evaluation.backtest import backtest, policy_evaluation

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--policies", action="store_true", help="Evaluate dated synthetic full-agent policy constraints")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(policy_evaluation()) if args.policies else backtest(), indent=2))
