import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE_DIR = Path(os.getenv("VIBEFINANCE_STATE_DIR", ROOT.parent / ".runtime"))
TICKERS = ("RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ITC.NS")
SECTORS = {"RELIANCE.NS": "Energy", "TCS.NS": "IT", "INFY.NS": "IT",
           "HDFCBANK.NS": "Banking", "ITC.NS": "Consumer"}
SEED = 42
AGENT_TIMEOUT_SECONDS = 5.0
DISCLAIMER = "Educational/simulated, not investment advice (SEBI-registered advice required)."
WEIGHTS = {"momentum": .30, "volume": .15, "sentiment": .20, "filings": .35}
