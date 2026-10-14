import asyncio

import numpy as np
import pytest

from vibefinance.agents.base import AgentOutput
from vibefinance.evaluation import backtest as evaluation
from vibefinance.evaluation.backtest import _dated_documents, _synthetic_market, backtest, policy_evaluation


def test_expanded_evaluation_has_cluster_intervals_and_comparable_baselines():
    result = backtest()
    assert result["sample_size"] > 500
    assert result["independent_seed_count"] == 12
    assert result["total_windows"] == result["sample_size"] + result["abstained_neutral_windows"]
    assert result["baselines"]["always_up_direction"]["hit_rate"] == result["buy_hold_hit_rate"]
    assert result["baselines"]["constant_half_probability"]["brier_score"] == pytest.approx(.25)
    for interval in result["uncertainty_intervals"].values():
        assert 0 <= interval["low"] <= interval["high"] <= 1
    rows = result["rows"]
    assert result["paired_hit_rate_differences"]["momentum_minus_always_up"]["difference"] == pytest.approx(
        np.mean([row["hit"] - row["buy_hold_hit"] for row in rows]))
    assert "not final recommendation confidence" in result["limitations"]


def test_prequential_probability_uses_only_completed_outcomes(monkeypatch):
    frames = []
    def bullish(ticker, frame, citation):
        frames.append(frame)
        return AgentOutput(agent="momentum_agent", ticker=ticker, dimension="momentum", label="BULLISH",
                           confidence=.9, evidence=[], citations=[citation])
    monkeypatch.setattr(evaluation, "analyze", bullish)
    backtest.cache_clear()
    try:
        result = backtest(seeds=(73,), days=180)
        for ticker in {row["ticker"] for row in result["rows"]}:
            rows = [row for row in result["rows"] if row["ticker"] == ticker]
            previous_up = 0
            for count, row in enumerate(rows):
                assert row["probability_training_samples"] == count
                assert row["probability_up"] == pytest.approx((previous_up + 1) / (count + 2))
                assert row["as_of"] < row["target_end"]
                previous_up += row["realized_up"]
        assert all(len(frame) <= 150 for frame in frames)
        assert result["uncertainty_intervals"]["hit_rate"] is None
    finally:
        backtest.cache_clear()


def test_synthetic_inputs_do_not_depend_on_future_path_length():
    shorter = _synthetic_market("RELIANCE.NS", 43, 180)
    longer = _synthetic_market("RELIANCE.NS", 43, 240)
    # Independent RNG streams make extending the path leave all past inputs unchanged.
    assert shorter.equals(longer.iloc[:180])
    short_docs = _dated_documents("RELIANCE.NS", 43, shorter.date)
    long_docs = _dated_documents("RELIANCE.NS", 43, longer.date)
    assert short_docs == long_docs[:len(short_docs)]


def test_full_policy_replay_checks_constraints_without_future_documents(monkeypatch):
    import vibefinance.orchestrator as orchestrator
    real_analyze = orchestrator.analyze
    observed_cutoffs = []

    async def inspect_inputs(ticker, profile, **kwargs):
        cutoff = kwargs["as_of"]
        assert str(kwargs["frame"].date.iloc[-1].date()) == cutoff
        assert all(chunk.date <= cutoff for chunk in kwargs["retriever"].chunks)
        observed_cutoffs.append(cutoff)
        return await real_analyze(ticker, profile, **kwargs)

    monkeypatch.setattr(orchestrator, "analyze", inspect_inputs)
    result = asyncio.run(policy_evaluation(seeds=(47,), days=120))
    assert result["sample_size"] == 15
    assert result["distinct_market_windows"] == 5
    assert any(row["missing_filing"] for row in result["rows"])
    assert len(observed_cutoffs) == result["sample_size"]
    assert all(check["violations"] == 0 for check in result["policy_checks"].values())
    assert all(date <= row["as_of"] for row in result["rows"] for date in row["document_dates"])
    assert "not a trading strategy" in result["limitations"]


def test_benchmark_measures_both_modes_and_preserves_outputs(store, retriever):
    from vibefinance.evaluation.benchmark import benchmark
    result = benchmark(repeats=2, profile=store.profile("arjun"), retriever=retriever)
    assert result["identical_outputs"] and result["unchanged_market_input"]
    assert len(result["wall_time_ms"]["parallel"]) == len(result["wall_time_ms"]["sequential"]) == 2
    assert result["measured_speedup"] > 0  # No requirement that concurrency helps.
    assert result["measured_speedup"] == pytest.approx(
        np.median(result["wall_time_ms"]["sequential"]) / np.median(result["wall_time_ms"]["parallel"]))
    assert store.history("arjun") == []


@pytest.mark.parametrize("repeats", [0, 1, -1, 101, True, 2.5])
def test_benchmark_rejects_invalid_repetition_count(repeats):
    from vibefinance.evaluation.benchmark import benchmark
    with pytest.raises(ValueError):
        benchmark(repeats)
