import asyncio
import sqlite3
import time

import pandas as pd
import pytest

import vibefinance.orchestrator as engine


def run(store, retriever, **kwargs):
    return asyncio.run(engine.analyze("RELIANCE.NS", store.profile("arjun"), store=store,
        retriever=retriever, **kwargs))


def test_retrieval_failure_finishes_with_disclosed_unknown_filings(store):
    class FailedRetriever:
        mode = "unavailable"
        warning = None
        def retrieve(self, *args, **kwargs):
            raise RuntimeError("Synthetic index outage")
    session = run(store, FailedRetriever())
    assert session["recommendation"]["action"] == "WATCH"
    assert session["persistence"]["status"] == "saved"
    assert any("retrieval unavailable" in message for message in session["warnings"])
    for out in session["recommendation"]["agent_outputs"]:
        if out["dimension"] in {"sentiment", "filings"}:
            assert not out["evidence"] and out["confidence"] == 0


def test_retriever_initialization_failure_uses_empty_fallback(store, monkeypatch):
    real = engine.Retriever
    def constructor(*args, **kwargs):
        if not kwargs:
            raise OSError("Synthetic unavailable corpus directory")
        return real(*args, **kwargs)
    monkeypatch.setattr(engine, "Retriever", constructor)
    session = asyncio.run(engine.analyze("RELIANCE.NS", store.profile("arjun"), store=store))
    assert session["recommendation"]["action"] == "WATCH"
    assert any("initialization unavailable" in message for message in session["warnings"])


def test_ingestion_failure_preserves_portfolio_policy_and_no_chart_rows(store, retriever, monkeypatch):
    def unavailable(*args, **kwargs):
        raise ConnectionError("Synthetic market ingestion failure")
    monkeypatch.setattr(engine, "load_market", unavailable)
    session = asyncio.run(engine.analyze("ITC.NS", store.profile("meera"), store=store, retriever=retriever))
    assert session["recommendation"]["action"] == "REDUCE"
    assert session["market_rows"] == []
    assert session["metrics"]["failed_agent_count"] == 2


def test_compare_ingestion_failure_shares_unavailable_input_and_persisted_warning(store, retriever, monkeypatch):
    def unavailable(*args, **kwargs):
        raise ConnectionError("Synthetic comparison ingestion failure")
    monkeypatch.setattr(engine, "load_market", unavailable)
    sessions = asyncio.run(engine.compare_users("RELIANCE.NS", store.profiles(), store=store, retriever=retriever))
    assert len({session["market_fingerprint"] for session in sessions}) == 1
    for session in sessions:
        assert session == store.session(session["session_id"])
        assert any("ingestion unavailable" in warning for warning in session["warnings"])


def test_retrieval_timeout_is_disclosed(store):
    class SlowRetriever:
        mode = "unavailable"
        warning = None
        def retrieve(self, *args, **kwargs):
            time.sleep(.05)
            return []
    session = run(store, SlowRetriever(), timeout=.01, persist=False)
    assert any("TimeoutError" in warning for warning in session["warnings"])
    assert session["recommendation"]["action"] == "WATCH"


def test_wrong_market_input_is_not_serialized_as_valid_data(store, retriever):
    session = run(store, retriever, frame={"close": "bad"}, persist=False)
    assert session["market_rows"] == []
    assert session["recommendation"]["action"] == "WATCH"


def test_unsaved_analysis_keeps_inline_passages(store, retriever, monkeypatch):
    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("Synthetic disk full")
    monkeypatch.setattr(store, "save_session", unavailable)
    session = run(store, retriever)
    assert session["persistence"]["status"] == "failed"
    assert session["sources"] and all(source["document_text"] for source in session["sources"])
    assert store.history("arjun") == []
    assert session["trace"][-1]["detail"].endswith("analysis was not saved.")


def test_database_transaction_rolls_back_failed_insert(store):
    with pytest.raises(RuntimeError):
        with store.connect() as db:
            db.execute("INSERT INTO metadata VALUES ('rollback-probe','test')")
            raise RuntimeError("Synthetic failed transaction")
    with store.connect() as db:
        assert db.execute("SELECT 1 FROM metadata WHERE key='rollback-probe'").fetchone() is None
