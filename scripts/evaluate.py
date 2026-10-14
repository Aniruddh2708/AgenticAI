import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vibefinance.evaluation.backtest import backtest

if __name__ == "__main__":
    print(json.dumps(backtest(), indent=2))
