"""Verify the optional Yahoo feed honestly; simulation is never counted as success."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vibefinance.config import TICKERS
from vibefinance.data.market_live import load_market
from vibefinance.data.market_sim import validate_market


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", choices=TICKERS, default="RELIANCE.NS")
    parser.add_argument("--require-live", action="store_true",
                        help="Exit 1 if the real feed is unavailable, even when simulation works.")
    args = parser.parse_args()
    frame, warning = load_market(args.ticker, live=True)
    validate_market(frame)
    live = frame.attrs.get("mode") == "live"
    print(json.dumps({"ticker": args.ticker, "live_download_succeeded": live,
                      "mode": frame.attrs.get("mode"), "rows": len(frame),
                      "start": str(frame.date.iloc[0]), "end": str(frame.date.iloc[-1]),
                      "fallback_warning": warning}, indent=2))
    if args.require_live and not live:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
