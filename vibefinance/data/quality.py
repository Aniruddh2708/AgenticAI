"""Read-only inventory of pinned vendor data; never an independent approval.

The audit reports defects before model fitting and does not repair source rows,
infer exchange sessions, or certify adjustment/redistribution rights.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from vibefinance.data.historical import verify_file


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def audit(manifest, directory, *, end="2023-12-31"):
    """Inventory only the declared development/calibration scope, before fitting."""
    if end > "2023-12-31":
        raise ValueError("Development audit must not inspect the spent 2024-2025 outcomes")
    records, calendars = [], {}
    for source in manifest["sources"]:
        path = Path(directory) / source["filename"]
        verify_file(path, source["sha256"])
        raw = pd.read_parquet(path).reset_index()
        raw = raw[(raw.Date >= pd.Timestamp("2010-01-01")) &
                  (raw.Date <= pd.Timestamp(end))].copy()
        if raw.empty:
            raise ValueError("Empty declared audit scope")
        dates = pd.to_datetime(raw.Date)
        numeric = raw[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].to_numpy(float)
        zero = raw.Volume.eq(0)
        factor = raw["Adj Close"] / raw.Close
        changed = factor.pct_change(fill_method=None).abs() > 1e-5
        actions = {}
        for field in ("Dividends", "Stock Splits"):
            values = raw[field] if field in raw else pd.Series(np.nan, index=raw.index)
            events = values.notna() & values.ne(0)
            actions[field] = {"present": field in raw, "missing": int(values.isna().sum()),
                              "events": [{"date": str(d.date()), "value": float(v)}
                                         for d, v in zip(dates[events], values[events])],
                              "independently_verified": False}
        exclusions = [{"date": str(d.date()), "reason": "zero_volume_vendor_observation",
                       "policy": "existing uniform exclusion; no repair; changes vendor-row horizon"}
                      for d in dates[zero]]
        usable = dates[~zero]
        calendars[source["ticker"]] = set(usable.dt.strftime("%Y-%m-%d"))
        records.append({"ticker": source["ticker"], "source_sha256": source["sha256"],
            "start": str(dates.min().date()), "end": str(dates.max().date()),
            "source_rows_in_scope": len(raw), "positive_volume_rows": int((~zero).sum()),
            "duplicates": int(dates.duplicated().sum()), "chronological": bool(dates.is_monotonic_increasing),
            "intraday_labels": int((dates != dates.dt.normalize()).sum()),
            "nonfinite_cells": int((~np.isfinite(numeric)).sum()),
            "nonpositive_price_cells": int((numeric[:, :5] <= 0).sum()),
            "negative_or_fractional_volumes": int(((raw.Volume < 0) | (raw.Volume % 1 != 0)).sum()),
            "ohlc_bound_violations": int(((raw.High < raw[["Open", "Close"]].max(axis=1) - 1e-4) |
                                          (raw.Low > raw[["Open", "Close"]].min(axis=1) + 1e-4)).sum()),
            "positive_volume_weekend_dates": usable[usable.dt.weekday >= 5].dt.strftime("%Y-%m-%d").tolist(),
            "gaps_over_seven_days": [{"after": str(a.date()), "before": str(b.date())}
                                      for a, b in zip(usable.iloc[:-1], usable.iloc[1:]) if (b-a).days > 7],
            "exclusions": exclusions, "excluded_dates_sha256": digest(exclusions),
            "adjustment_factor_range": [float(factor.min()), float(factor.max())],
            "adjustment_change_dates": dates[changed].dt.strftime("%Y-%m-%d").tolist(),
            "corporate_actions": actions, "adjustment_vintage": "retrospective vendor snapshot; unverified",
            "security_identity": "symbol only; historical ISIN mapping and survivorship review unresolved"})
    union = set.union(*calendars.values())
    common = set.intersection(*calendars.values())
    return {"schema_version": 2, "kind": "vendor_data_quality_inventory", "status": "not_independently_validated",
        "scope": {"start": "2010-01-01", "end": end, "securities": sorted(calendars)},
        "source_manifest_sha256": digest(manifest), "archive_commit": manifest["archive_commit"],
        "source_license": manifest["license"], "commercial_use_permitted": False,
        "sources": records, "calendar": {"vendor_union_dates": len(union), "vendor_common_dates": len(common),
            "missing_from_vendor_union_by_ticker": {t: sorted(union-v) for t, v in calendars.items()},
            "complete_exchange_calendar_verified": False,
            "note": "Shared omissions cannot be detected from a vendor union; special sessions are not inferred."},
        "independent_evidence": {"reference": "docs/assets/independent-source-review.json",
            "scope": ["2020-12-31", "2025-03-18"],
            "finding": "Prior two-date NSE review only; not re-downloaded or recertified in this audit",
            "full_calendar_actions_adjusted_history_rights_approved": False},
        "unresolved": ["Complete authorized independent prices and comparable volume basis",
            "Exchange calendar including special sessions", "Equivalent corporate-action adjustment vintage and actions",
            "Point-in-time symbol/ISIN and survivor-universe review", "Permission for any hosted/commercial use"],
        "repairs_applied": False, "independent_approval": False}
