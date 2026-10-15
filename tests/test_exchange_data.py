"""Explicit synthetic format fixtures; no market-data or forecasting evidence."""
import csv
import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

import httpx
import pytest

from vibefinance.data import exchange


@pytest.fixture
def legacy_rows():
    return [{"SYMBOL": ticker.removesuffix(".NS"), "SERIES": "EQ", "OPEN": "100", "HIGH": "103",
             "LOW": "99", "CLOSE": "102", "TOTTRDQTY": "1000", "TIMESTAMP": "31-DEC-2020",
             "ISIN": f"INE000A01{index:03}"} for index, ticker in enumerate(exchange.TICKERS)]


def csv_bytes(rows, trailing=False):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    text = stream.getvalue()
    if trailing:
        text = "\r\n".join(line + "," for line in text.splitlines()) + "\r\n"
    return text.encode()


def zipped(payload, member="cm31DEC2020bhav.csv"):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, payload)
    return stream.getvalue()


def udiff_rows():
    return [{"TckrSymb": ticker.removesuffix(".NS"), "SctySrs": "EQ", "OpnPric": "100", "HghPric": "103",
             "LwPric": "99", "ClsPric": "102", "TtlTradgVol": "1000", "TradDt": "2025-01-02",
             "BizDt": "2025-01-02", "ISIN": f"INE000A01{index:03}", "Sgmt": "CM", "Src": "NSE", "FinInstrmTp": "STK"}
            for index, ticker in enumerate(exchange.TICKERS)]


@pytest.fixture
def permission_review(tmp_path):
    # Explicit fake review/evidence for mocked HTTP tests only. This never
    # authorizes a real request or becomes a runtime/operator approval file.
    evidence = tmp_path / "fixture-permission.txt"
    evidence.write_text("Synthetic unit-test declaration; NOT actual NSE permission.")
    review = {"schema_version": 1, "kind": "nse_automation_permission_review",
              "status": "reviewed_approved", "automation_authorized": True,
              "reviewed_by": "Unit fixture only", "reviewed_at": "2020-01-01T00:00:00+00:00",
              "authorization_reference": "Synthetic fixture; no real authorization",
              "source_host": "nsearchives.nseindia.com", "authorized_dates": ["2020-12-31"],
              "evidence": {"path": evidence.name, "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}}
    path = tmp_path / "fixture-review.json"
    path.write_text(json.dumps(review))
    return path


def test_legacy_csv_and_standard_trailing_comma_keep_exact_raw_rows(legacy_rows):
    for trailing in (False, True):
        payload = csv_bytes(legacy_rows, trailing)
        report = exchange.parse_bhavcopy(payload, "2020-12-31")
        assert report["provider_format"] == "legacy"
        assert report["artifact_sha256"] == hashlib.sha256(payload).hexdigest()
        assert len(report["rows"]) == 5
        assert report["rows"][0]["ticker"] == "RELIANCE.NS"
        assert report["rows"][0]["close"] == 102.


def test_udiff_uses_actual_provider_close_field_and_market_identity():
    report = exchange.parse_bhavcopy(csv_bytes(udiff_rows()), "2025-01-02")
    assert report["provider_format"] == "udiff"
    assert report["rows"][1]["close"] == 102.


def test_wrong_series_is_not_substituted_for_missing_eq(legacy_rows):
    legacy_rows[0]["SERIES"] = "BE"
    with pytest.raises(exchange.ExchangeDataError, match="five requested") as error:
        exchange.parse_bhavcopy(csv_bytes(legacy_rows), "2020-12-31")
    assert error.value.code == "missing_security"


def test_other_series_does_not_override_exact_eq(legacy_rows):
    other = {**legacy_rows[0], "SERIES": "BE", "CLOSE": "500"}
    result = exchange.parse_bhavcopy(csv_bytes([other, *legacy_rows]), "2020-12-31")
    assert result["source_rows"] == 6
    assert result["rows"][0]["close"] == 102.


@pytest.mark.parametrize("defect,code", [("duplicate", "duplicate_security"), ("date", "date_mismatch"),
    ("nan", "invalid_number"), ("inf", "invalid_number"), ("negative", "invalid_number"),
    ("fractional_volume", "invalid_volume"), ("huge_volume", "invalid_volume"),
    ("bounds", "invalid_ohlc"), ("isin", "invalid_isin"), ("duplicate_isin", "duplicate_isin"), ("missing", "missing_security")])
def test_bad_daily_data_is_rejected_without_fills(legacy_rows, defect, code):
    if defect == "duplicate": legacy_rows.append(dict(legacy_rows[0]))
    elif defect == "date": legacy_rows[0]["TIMESTAMP"] = "30-DEC-2020"
    elif defect == "nan": legacy_rows[0]["CLOSE"] = "NaN"
    elif defect == "inf": legacy_rows[0]["HIGH"] = "Infinity"
    elif defect == "negative": legacy_rows[0]["TOTTRDQTY"] = "-1"
    elif defect == "fractional_volume": legacy_rows[0]["TOTTRDQTY"] = "1.5"
    elif defect == "huge_volume": legacy_rows[0]["TOTTRDQTY"] = "1e99999"
    elif defect == "bounds": legacy_rows[0]["HIGH"] = "98"
    elif defect == "isin": legacy_rows[0]["ISIN"] = "UNKNOWN"
    elif defect == "duplicate_isin": legacy_rows[0]["ISIN"] = legacy_rows[1]["ISIN"]
    else: legacy_rows.pop()
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.parse_bhavcopy(csv_bytes(legacy_rows), "2020-12-31")
    assert error.value.code == code


@pytest.mark.parametrize("field,value", [("Src", "BSE"), ("Sgmt", "FO"),
    ("BizDt", "2025-01-01"), ("FinInstrmTp", "FUT")])
def test_udiff_cash_equity_identity_is_checked(field, value):
    rows = udiff_rows()
    rows[0][field] = value
    with pytest.raises(exchange.ExchangeDataError):
        exchange.parse_bhavcopy(csv_bytes(rows), "2025-01-02")


def test_unrequested_source_rows_must_still_match_requested_daily_date(legacy_rows):
    legacy_rows.append({**legacy_rows[0], "SYMBOL": "UNREQUESTED", "TIMESTAMP": "01-JAN-2021"})
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.parse_bhavcopy(csv_bytes(legacy_rows), "2020-12-31")
    assert error.value.code == "date_mismatch"


def test_zero_volume_is_retained_and_flagged_not_removed(tmp_path, legacy_rows):
    legacy_rows[0]["TOTTRDQTY"] = "0"
    report = exchange.write_bundle(csv_bytes(legacy_rows), "2020-12-31", tmp_path / "bundle")
    assert report["findings"] == [{"code": "zero_volume", "ticker": "RELIANCE.NS", "date": "2020-12-31"}]
    assert len(report["files"]) == 5
    assert "0" in (tmp_path / "bundle/RELIANCE_NS.csv").read_text()
    assert report["price_basis"] == "raw"
    assert report["rights_status"] == "unreviewed"
    assert report["status"] == "raw_only_not_reconciled"
    assert "authorized_use" not in report


def test_zip_crc_identity_and_expected_source_hash(legacy_rows):
    payload = csv_bytes(legacy_rows)
    source = zipped(payload)
    report = exchange.parse_bhavcopy(source, "2020-12-31", "zip", hashlib.sha256(source).hexdigest())
    assert report["csv_member"] == "cm31DEC2020bhav.csv"
    assert report["csv_sha256"] == hashlib.sha256(payload).hexdigest()
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.parse_bhavcopy(source, "2020-12-31", "zip", "0" * 64)
    assert error.value.code == "checksum_mismatch"


@pytest.mark.parametrize("member", ["../prices.csv", "/prices.csv", "nested/prices.csv", "C:prices.csv", "nested\\prices.csv"])
def test_zip_traversal_and_platform_path_names_rejected(legacy_rows, member):
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.parse_bhavcopy(zipped(csv_bytes(legacy_rows), member), "2020-12-31", "zip")
    assert error.value.code == "unsafe_zip_path"


def test_zip_symlinks_and_multiple_members_rejected(legacy_rows):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        member = zipfile.ZipInfo("prices.csv")
        member.create_system = 3
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(member, csv_bytes(legacy_rows))
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.parse_bhavcopy(stream.getvalue(), "2020-12-31", "zip")
    assert error.value.code == "unsafe_zip_member"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("one.csv", csv_bytes(legacy_rows))
        archive.writestr("two.csv", csv_bytes(legacy_rows))
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.parse_bhavcopy(stream.getvalue(), "2020-12-31", "zip")
    assert error.value.code == "zip_members"


def test_zip_bomb_bound_rejected_before_read():
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.parse_bhavcopy(zipped(b"A" * 100000), "2020-12-31", "zip")
    assert error.value.code == "zip_expansion"


def test_existing_output_and_invalid_input_do_not_overwrite(tmp_path, legacy_rows):
    directory = tmp_path / "bundle"
    payload = csv_bytes(legacy_rows)
    report = exchange.write_bundle(payload, "2020-12-31", directory)
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.write_bundle(payload, "2020-12-31", directory)
    assert error.value.code == "output_exists"
    assert all(p.read_bytes() == before[p.name] for p in directory.iterdir())
    for artifact in report["files"] + [report["raw_artifact"]]:
        assert hashlib.sha256((directory / artifact["path"]).read_bytes()).hexdigest() == artifact["sha256"]
    with pytest.raises(exchange.ExchangeDataError):
        exchange.write_bundle(b"not valid data", "2020-12-31", tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_source_schema_must_match_explicit_fetch_format(tmp_path, legacy_rows):
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.write_bundle(csv_bytes(legacy_rows), "2020-12-31", tmp_path / "wrong", requested_format="udiff")
    assert error.value.code == "format_mismatch"
    assert not (tmp_path / "wrong").exists()


def test_duplicate_headers_and_guessed_udiff_aliases_are_rejected(legacy_rows):
    payload = csv_bytes(legacy_rows).replace(b"SYMBOL,SERIES", b"SYMBOL,SYMBOL", 1)
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.parse_bhavcopy(payload, "2020-12-31")
    assert error.value.code == "invalid_header"
    rows = udiff_rows()
    for row in rows:
        row["ClsgPric"] = row.pop("ClsPric")
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.parse_bhavcopy(csv_bytes(rows), "2025-01-02")
    assert error.value.code == "unknown_schema"


def test_zip_expanded_byte_bound_is_enforced_before_parsing(legacy_rows, monkeypatch):
    monkeypatch.setattr(exchange, "MAX_CSV_BYTES", 10)
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.parse_bhavcopy(zipped(csv_bytes(legacy_rows)), "2020-12-31", "zip")
    assert error.value.code == "zip_expansion"


def test_fetch_only_canonical_spent_date_and_no_redirects(monkeypatch, legacy_rows, permission_review):
    payload = zipped(csv_bytes(legacy_rows))
    calls = []
    actual_client = httpx.Client
    def factory(**kwargs):
        assert kwargs == {"timeout": 30, "follow_redirects": False}
        def handler(request):
            calls.append(str(request.url))
            return httpx.Response(200, content=payload)
        return actual_client(**kwargs, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(exchange.httpx, "Client", factory)
    content, url = exchange.fetch_spent_archive("2020-12-31", "legacy", permission_review)
    assert content == payload
    assert calls == ["https://nsearchives.nseindia.com/content/historical/EQUITIES/2020/DEC/cm31DEC2020bhav.csv.zip"]
    assert url == calls[0]
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.fetch_spent_archive("2026-01-02", "udiff")
    assert error.value.code == "unregistered_outcome"
    assert len(calls) == 1
    assert exchange.archive_url("2025-01-02", "udiff") == "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20250102_F_0000.csv.zip"


@pytest.mark.parametrize("status", [302, 403])
def test_fetch_stops_at_redirect_or_denial_without_retry_or_mirror(monkeypatch, status, permission_review):
    actual_client = httpx.Client
    calls = []
    def factory(**kwargs):
        def handler(request):
            calls.append(str(request.url))
            return httpx.Response(status, headers={"Location": "https://another.example.org/prices.zip"})
        return actual_client(**kwargs, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(exchange.httpx, "Client", factory)
    with pytest.raises(httpx.HTTPStatusError):
        exchange.fetch_spent_archive("2020-12-31", "legacy", permission_review)
    assert len(calls) == 1
    assert calls[0].startswith("https://nsearchives.nseindia.com/")


def test_absent_automation_permission_stops_before_any_http_client(monkeypatch):
    def forbidden_client(**kwargs):
        pytest.fail("Missing permission must fail before even creating an HTTP client")
    monkeypatch.setattr(exchange.httpx, "Client", forbidden_client)
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.fetch_spent_archive("2020-12-31", "legacy")
    assert error.value.code == "permission_required"


@pytest.mark.parametrize("defect", ["approval", "automation", "host", "date", "reviewer", "timestamp", "artifact", "hash", "traversal"])
def test_incomplete_or_out_of_scope_permission_never_reaches_http(permission_review, monkeypatch, defect):
    review = json.loads(permission_review.read_text())
    if defect == "approval": review["status"] = "pending"
    elif defect == "automation": review["automation_authorized"] = False
    elif defect == "host": review["source_host"] = "another.example.org"
    elif defect == "date": review["authorized_dates"] = ["2020-12-30"]
    elif defect == "reviewer": review["reviewed_by"] = ""
    elif defect == "timestamp": review["reviewed_at"] = "9999-01-01T00:00:00+00:00"
    elif defect == "artifact": review["evidence"]["path"] = "missing.pdf"
    elif defect == "hash": review["evidence"]["sha256"] = "0" * 64
    else: review["evidence"]["path"] = "../outside.pdf"
    permission_review.write_text(json.dumps(review))
    def forbidden_client(**kwargs):
        pytest.fail("Invalid permission must fail before HTTP")
    monkeypatch.setattr(exchange.httpx, "Client", forbidden_client)
    with pytest.raises(exchange.ExchangeDataError) as error:
        exchange.fetch_spent_archive("2020-12-31", "legacy", permission_review)
    assert error.value.code == "permission_required"


def test_cli_missing_permission_has_explicit_status_and_creates_no_bundle(tmp_path):
    script = Path(__file__).resolve().parent.parent / "scripts/acquire_exchange.py"
    target = tmp_path / "no-permission"
    result = subprocess.run([sys.executable, str(script), "--fetch", "--format", "legacy",
        "--date", "2020-12-31", "--output-dir", str(target)], capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "permission_required"
    assert not target.exists()


def test_cli_imports_local_file_without_network_and_reports_invalid_json(tmp_path, legacy_rows):
    path = tmp_path / "authorized.csv"
    path.write_bytes(csv_bytes(legacy_rows))
    script = Path(__file__).resolve().parent.parent / "scripts/acquire_exchange.py"
    cmd = [sys.executable, str(script), "--input", str(path), "--date", "2020-12-31", "--output-dir", str(tmp_path / "bundle")]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["origin_evidence"] == "local_file_origin_unverified"
    again = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert again.returncode == 2
    assert json.loads(again.stdout)["code"] == "output_exists"
