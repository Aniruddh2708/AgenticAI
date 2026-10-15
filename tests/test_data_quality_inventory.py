import hashlib

import numpy as np
import pandas as pd
import pytest

from vibefinance.data.quality import audit


def test_read_only_quality_inventory_preserves_zero_rows_and_never_certifies_calendar(tmp_path):
    sources, before = [], {}
    dates = pd.bdate_range("2013-01-01", periods=280)
    for ticker in ("TCS.NS", "INFY.NS", "ITC.NS", "HDFCBANK.NS", "RELIANCE.NS"):
        frame = pd.DataFrame({"Date": dates, "Open": 100., "High": 101., "Low": 99.,
            "Close": 100., "Adj Close": 98., "Volume": np.full(280, 1000.),
            "Dividends": 0., "Stock Splits": 0.})
        frame.loc[100, "Volume"] = 0
        path = tmp_path/(ticker+".parquet")
        frame.to_parquet(path, index=False)
        before[ticker] = path.read_bytes()
        sources.append({"ticker": ticker, "filename": path.name, "sha256": hashlib.sha256(before[ticker]).hexdigest()})
    manifest = {"sources": sources, "archive_commit": "fixture_not_market_data", "license": "Generated fixture"}
    report = audit(manifest, tmp_path)
    assert report["repairs_applied"] is False and report["independent_approval"] is False
    assert report["calendar"]["complete_exchange_calendar_verified"] is False
    assert report["sources"][0]["source_rows_in_scope"] == 280
    assert report["sources"][0]["positive_volume_rows"] == 279
    assert len(report["sources"][0]["exclusions"]) == 1
    for s in sources:
        assert (tmp_path/s["filename"]).read_bytes() == before[s["ticker"]]
    with pytest.raises(ValueError):
        audit(manifest, tmp_path, end="2025-12-31")
