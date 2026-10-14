import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vibefinance.evaluation.backtest import policy_evaluation
from vibefinance.evaluation.benchmark import benchmark


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Measured execution benchmark or point-in-time synthetic policy replay")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--ticker", default="RELIANCE.NS")
    parser.add_argument("--policy-evaluation", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(policy_evaluation()) if args.policy_evaluation else benchmark(args.repeats, ticker=args.ticker)
    print(json.dumps(result, indent=2))
