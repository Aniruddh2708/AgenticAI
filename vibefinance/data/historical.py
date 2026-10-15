"""Checksum-pinned historical inputs with explicit provenance; no fallback."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse

import httpx
import numpy as np
import pandas as pd

from vibefinance.config import TICKERS


def read_manifest(path):
    manifest = json.loads(Path(path).read_text())
    sources = manifest.get("sources", [])
    if manifest.get("schema_version") != 1 or len(sources) != len(TICKERS):
        raise ValueError("Need a versioned manifest for the five declared tickers")
    if {s.get("ticker") for s in sources} != set(TICKERS):
        raise ValueError("Manifest must contain exactly the existing five-ticker universe")
    for source in sources:
        if (not re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")) or
                source.get("price_basis") != "adjusted" or
                not source.get("provider") or not source.get("lineage_url")):
            raise ValueError("Each input needs a hash, provider lineage and documented adjusted prices")
        name = source.get("filename", "")
        if Path(name).name != name or Path(name).suffix not in {".csv", ".parquet"}:
            raise ValueError("Historical filenames must be local CSV/Parquet basenames")
        url = urlparse(source.get("url", ""))
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("Historical sources must use HTTPS without credentials")
    return manifest


def verify_file(path, expected):
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
        raise ValueError(f"Historical artifact checksum mismatch: {Path(path).name}")


def download(manifest, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        artifacts = list(manifest["sources"])
        if manifest.get("license_artifact"):
            artifacts.append(manifest["license_artifact"])
        for source in artifacts:
            path = directory / source["filename"]
            if path.exists():
                verify_file(path, source["sha256"])
                continue
            response = client.get(source["url"])
            response.raise_for_status()
            if hashlib.sha256(response.content).hexdigest() != source["sha256"]:
                raise ValueError(f"Downloaded artifact checksum mismatch: {source['filename']}")
            # Exclusive creation never overwrites user input or partial data.
            with path.open("xb") as handle:
                handle.write(response.content)


def normalize(raw, study_start=None, study_end=None):
    """Use adjusted close explicitly; adjust OHLC consistently where necessary."""
    frame = raw.copy()
    if "date" not in {str(c).lower() for c in frame.columns}:
        frame = frame.reset_index()
    frame.columns = [str(c).strip().lower().replace(" ", "_") for c in frame.columns]
    if "date" not in frame or any(c not in frame for c in ("open", "high", "low", "close", "volume")):
        raise ValueError("Historical input needs dated OHLCV columns")
    frame["date"] = pd.to_datetime(frame.date, errors="raise")
    # Daily session dates retain local calendar date, never shift via UTC.
    if getattr(frame.date.dt, "tz", None) is not None:
        frame["date"] = frame.date.dt.tz_localize(None)
    frame["date"] = frame.date.dt.normalize()
    if study_start is not None:
        frame = frame[frame.date >= pd.Timestamp(study_start)].copy()
    if study_end is not None:
        frame = frame[frame.date <= pd.Timestamp(study_end)].copy()
    if frame.date.duplicated().any() or not frame.date.is_monotonic_increasing:
        raise ValueError("Historical dates must be unique and strictly chronological")
    if (frame.date > pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()).any():
        raise ValueError("Historical input contains future dates")
    for column in ("open", "high", "low", "close", "volume", "adj_close"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
    if "adj_close" in frame:
        factor = frame.adj_close / frame.close
        frame[["open", "high", "low", "close"]] = frame[["open", "high", "low", "close"]].mul(factor, axis=0)
    frame = frame[["date", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
    values = frame.drop(columns="date").to_numpy(float)
    if len(frame) < 240 or not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError("Historical data must contain 240 valid positive-price sessions")
    tolerance = frame.close.abs() * 1e-6
    if ((frame.high + tolerance < frame[["open", "close"]].max(axis=1)).any() or
            (frame.low - tolerance > frame[["open", "close"]].min(axis=1)).any()):
        raise ValueError("Historical OHLC bounds are inconsistent")
    # Nontraded holiday placeholders are not trading sessions. This rule is
    # declared before scoring; retain positive-volume Muhurat/weekend sessions.
    dropped = int((frame.volume == 0).sum())
    excluded_dates = [str(date.date()) for date in frame.loc[frame.volume == 0, "date"]]
    frame = frame[frame.volume > 0].reset_index(drop=True)
    if len(frame) < 240:
        raise ValueError("Need 240 actual traded sessions")
    frame.attrs["removed_zero_volume_rows"] = dropped
    frame.attrs["excluded_zero_volume_dates"] = excluded_dates
    return frame


def load(manifest, directory):
    frames, metadata = {}, []
    for source in manifest["sources"]:
        path = Path(directory) / source["filename"]
        verify_file(path, source["sha256"])
        raw = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        frame = normalize(raw, manifest.get("study_start"), manifest.get("study_end"))
        frame.attrs.update(mode="historical_adjusted", source_id=source["url"])
        frames[source["ticker"]] = frame
        gaps = int((frame.date.diff().dt.days > 7).sum())
        metadata.append({**source, "rows": len(frame), "date_start": str(frame.date.min().date()),
                         "date_end": str(frame.date.max().date()), "gaps_over_seven_calendar_days": gaps,
                         "source_file_rows": len(raw),
                         "study_start": manifest.get("study_start"), "study_end": manifest.get("study_end"),
                         "removed_zero_volume_rows": frame.attrs["removed_zero_volume_rows"],
                         "excluded_zero_volume_dates": frame.attrs["excluded_zero_volume_dates"],
                         "source_license": manifest.get("license"), "source_license_url": manifest.get("license_url"),
                         "commercial_use_permitted": manifest.get("commercial_use_permitted", False)})
    return frames, metadata
