import asyncio

from vibefinance.agents import momentum_agent, volume_agent
from vibefinance.agents.base import Citation
from vibefinance.data.market_sim import generate_market
from vibefinance import orchestrator


def test_market_computed_once_while_canonical_claims_and_outputs_are_preserved(store, retriever, monkeypatch):
    from vibefinance.evaluation.backtest import backtest
    backtest()  # One-time synthetic benchmark is outside this session's inputs.
    original = orchestrator.indicators
    calls = []
    def counted(frame):
        calls.append(len(frame))
        return original(frame)
    monkeypatch.setattr(orchestrator, "indicators", counted)
    monkeypatch.setattr(momentum_agent, "indicators", counted)
    monkeypatch.setattr(volume_agent, "indicators", counted)
    frame = generate_market("RELIANCE.NS")
    session = asyncio.run(orchestrator.analyze("RELIANCE.NS", store.profile("arjun"), frame=frame,
                                               retriever=retriever, persist=False))
    assert calls == [len(frame)]
    assert session["metrics"]["claim_support_coverage"] == 1
    for module, dimension in ((momentum_agent, "momentum"), (volume_agent, "volume")):
        actual = next(o for o in session["recommendation"]["agent_outputs"] if o["dimension"] == dimension)
        citation = Citation.model_validate(actual["citations"][0])
        expected = module.analyze("RELIANCE.NS", frame, citation)
        assert (actual["label"], actual["confidence"], actual["evidence"]) == (expected.label, expected.confidence, expected.evidence)


def test_precomputed_indicator_snapshot_cannot_be_changed_by_agent(store, retriever, monkeypatch):
    original = momentum_agent.analyze
    def checked(*args, computed_indicators=None):
        try:
            computed_indicators["return_1m"] = 99
        except TypeError:
            pass
        else:
            raise AssertionError("Shared indicator snapshot was mutable")
        return original(*args, computed_indicators=computed_indicators)
    monkeypatch.setattr(momentum_agent, "analyze", checked)
    session = asyncio.run(orchestrator.analyze("RELIANCE.NS", store.profile("meera"), retriever=retriever, persist=False))
    assert session["recommendation"]["action"] == "REDUCE"
    assert session["metrics"]["claim_support_coverage"] == 1
