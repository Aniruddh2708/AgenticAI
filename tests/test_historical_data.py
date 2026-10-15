"""Historical artifact and corporate-action tests, not forecasting evidence."""
import copy
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from vibefinance.config import TICKERS
from vibefinance.data.historical import load, normalize, read_manifest, verify_file


@pytest.fixture
def raw():
    close = np.arange(100, 400, dtype=float)
    return pd.DataFrame({"Date": pd.bdate_range("2010-01-01", periods=300),
        "Open": close, "High": close+1, "Low": close-1, "Close": close,
        "Adj Close": close * .5, "Volume": np.full(300, 1000)})


def test_adjusted_close_and_ohlc_use_same_basis(raw):
    out = normalize(raw)
    np.testing.assert_allclose(out.close, raw["Adj Close"])
    np.testing.assert_allclose(out.high, raw.High * .5)
    np.testing.assert_allclose(out.volume, raw.Volume)


def test_zero_volume_removed_but_traded_weekend_retained(raw):
    raw.loc[0, "Volume"] = 0
    raw.loc[2, "Date"] = pd.Timestamp("2010-01-09")
    raw.loc[3, "Date"] = pd.Timestamp("2010-01-10")
    raw.loc[4:, "Date"] += pd.Timedelta(days=10)
    out = normalize(raw)
    assert len(out) == 299
    assert out.attrs["removed_zero_volume_rows"] == 1
    assert pd.Timestamp("2010-01-09") in set(out.date)


@pytest.mark.parametrize("defect", ["nan", "negative", "duplicate", "order", "bounds"])
def test_invalid_history_is_rejected_not_repaired(raw, defect):
    if defect == "nan":
        raw.loc[10, "Adj Close"] = np.nan
    elif defect == "negative":
        raw.loc[10, "Volume"] = -1
    elif defect == "duplicate":
        raw.loc[10, "Date"] = raw.loc[9, "Date"]
    elif defect == "order":
        raw = raw.iloc[::-1]
    else:
        raw.loc[10, "High"] = 1
    with pytest.raises(ValueError):
        normalize(raw)


def test_predeclared_study_crop_excludes_bad_outside_rows(raw):
    raw.loc[0, "Close"] = np.nan
    out = normalize(raw, "2010-01-04", "2011-12-31")
    assert out.date.min() == pd.Timestamp("2010-01-04")
    assert np.isfinite(out.close).all()
    with pytest.raises(ValueError):
        normalize(raw)


def test_checksum_prevents_silent_snapshot_updates(tmp_path):
    file = tmp_path / "history.csv"
    file.write_bytes(b"real artifact bytes")
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    verify_file(file, digest)
    file.write_bytes(b"other artifact bytes")
    with pytest.raises(ValueError, match="checksum"):
        verify_file(file, digest)


@pytest.fixture
def manifest():
    return {"schema_version": 1, "sources": [{"ticker": ticker,
        "url": "https://example.org/archive.csv", "filename": ticker + ".csv",
        "provider": "Unit test fixture", "price_basis": "adjusted",
        "lineage_url": "https://example.org/lineage", "sha256": "0" * 64} for ticker in TICKERS]}


@pytest.mark.parametrize("defect", ["ticker", "basis", "missing_lineage", "hash", "url", "path"])
def test_manifest_requires_universe_adjustment_and_provenance(tmp_path, manifest, defect):
    source = manifest["sources"][0]
    if defect == "ticker": source["ticker"] = "FAKE"
    elif defect == "basis": source["price_basis"] = "simulated"
    elif defect == "missing_lineage": source.pop("lineage_url")
    elif defect == "hash": source["sha256"] = "unknown"
    elif defect == "url": source["url"] = "http://example.org/archive.csv"
    else: source["filename"] = "../history.csv"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        read_manifest(path)


def test_loader_records_exact_source_and_exclusions(tmp_path, raw, manifest):
    raw.loc[10, "Volume"] = 0
    for source in manifest["sources"]:
        path = tmp_path / source["filename"]
        raw.to_csv(path, index=False)
        source["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    frames, metadata = load(manifest, tmp_path)
    assert set(frames) == set(TICKERS)
    assert all(info["removed_zero_volume_rows"] == 1 and info["rows"] == 299 for info in metadata)
    assert all(frame.attrs["mode"] == "historical_adjusted" for frame in frames.values())
