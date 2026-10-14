"""Adversarial regressions for statement accounting and agent signal integrity.

Overrides represent a faulty future producer, not a public API injection path.
The checks ensure valid provenance cannot silently authorize a forged signal.
"""

import asyncio

import pytest

from vibefinance.agents.base import AgentOutput, EvidenceClaim
from vibefinance.orchestrator import analyze


def run(store, retriever, **kwargs):
    return asyncio.run(analyze("RELIANCE.NS", store.profile("arjun"), store=store,
                               retriever=retriever, persist=False, **kwargs))


def agent(session, dimension):
    return AgentOutput.model_validate(next(output for output in session["recommendation"]["agent_outputs"]
                                          if output["dimension"] == dimension))


def test_altered_computed_value_is_removed_and_counted(store, retriever):
    baseline = run(store, retriever)
    original = agent(baseline, "momentum")
    forged = original.model_copy(deep=True)
    forged.claims[0] = forged.claims[0].model_copy(update={"value": 999.0})
    session = run(store, retriever, overrides={"momentum": lambda: forged})
    output = agent(session, "momentum")
    assert output.status == "degraded"
    assert output.evidence == original.evidence[1:]
    assert output.confidence <= original.confidence * 2 / 3 + 1e-12
    assert session["metrics"]["rejected_claim_count"] == 1
    assert session["metrics"]["submitted_claim_count"] == baseline["metrics"]["submitted_claim_count"]


@pytest.mark.parametrize("dimension,forged_label", [("momentum", "BEARISH"), ("sentiment", "NEGATIVE")])
def test_registered_evidence_does_not_authorize_forged_signal(store, retriever, dimension, forged_label):
    baseline = run(store, retriever)
    original = agent(baseline, dimension)
    assert original.label != forged_label
    forged = original.model_copy(update={"label": forged_label, "confidence": 1}, deep=True)
    session = run(store, retriever, overrides={dimension: lambda: forged})
    output = agent(session, dimension)
    assert output.confidence == 0 or output.label == original.label
    if output.confidence:
        assert output.confidence <= original.confidence


def test_raw_market_quotation_cannot_replace_recomputed_market_claims(store, retriever):
    baseline = run(store, retriever)
    original = agent(baseline, "momentum")
    source = original.citations[0]
    quote = EvidenceClaim(claim_id="momentum:computed:0", text=source.excerpt,
                          citation_ids=[source.chunk_id], method="quotation")
    forged = original.model_copy(update={"evidence": [quote.text], "claims": [quote]}, deep=True)
    session = run(store, retriever, overrides={"momentum": lambda: forged})
    output = agent(session, "momentum")
    assert output.confidence == 0 or all(claim.method == "computed" for claim in output.claims)
    assert quote.text not in output.evidence


def test_uninformative_news_prefix_cannot_justify_full_tone_strength(store, retriever):
    baseline = run(store, retriever)
    original = agent(baseline, "sentiment")
    source = original.citations[0]
    text = "Synthetic news:"
    assert text in source.excerpt
    quote = EvidenceClaim(claim_id="irrelevant-tone-quote", text=text,
                          citation_ids=[source.chunk_id], method="quotation")
    forged = original.model_copy(update={"evidence": [text], "claims": [quote]}, deep=True)
    session = run(store, retriever, overrides={"sentiment": lambda: forged})
    output = agent(session, "sentiment")
    assert output.confidence == 0
    assert not output.evidence


def test_duplicate_evidence_has_only_one_authorization_and_one_rejection(store, retriever):
    baseline = run(store, retriever)
    original = agent(baseline, "momentum")
    forged = original.model_copy(deep=True)
    forged.evidence.append(forged.evidence[0])
    session = run(store, retriever, overrides={"momentum": lambda: forged})
    output = agent(session, "momentum")
    assert output.evidence == original.evidence
    assert len(output.claims) == len(output.evidence)
    assert output.status == "degraded"
    assert session["metrics"]["submitted_claim_count"] == baseline["metrics"]["submitted_claim_count"] + 1
    assert session["metrics"]["supported_claim_count"] == baseline["metrics"]["supported_claim_count"]
    assert session["metrics"]["rejected_claim_count"] == 1


def test_extra_duplicate_claim_does_not_survive_without_evidence_slot(store, retriever):
    baseline = run(store, retriever)
    original = agent(baseline, "sentiment")
    forged = original.model_copy(deep=True)
    forged.claims.append(forged.claims[0].model_copy(update={"claim_id": "duplicate-quotation"}))
    session = run(store, retriever, overrides={"sentiment": lambda: forged})
    output = agent(session, "sentiment")
    assert len(output.claims) == len(output.evidence)
    assert output.status == "degraded"
    assert output.confidence < original.confidence
    assert session["metrics"]["rejected_claim_count"] == 1


@pytest.mark.parametrize("keep_claims", [True, False])
def test_no_displayed_evidence_cannot_contribute_positive_signal(store, retriever, keep_claims):
    baseline = run(store, retriever)
    original = agent(baseline, "sentiment")
    forged = original.model_copy(update={"evidence": [],
        "claims": original.claims if keep_claims else []}, deep=True)
    session = run(store, retriever, overrides={"sentiment": lambda: forged})
    output = agent(session, "sentiment")
    assert output.confidence == 0
    assert output.label in {"UNKNOWN", "MIXED"}
    assert not output.evidence and not output.claims


def test_missing_claim_attachment_rejects_evidence_even_with_registered_citation(store, retriever):
    baseline = run(store, retriever)
    original = agent(baseline, "sentiment")
    forged = original.model_copy(update={"claims": []}, deep=True)
    session = run(store, retriever, overrides={"sentiment": lambda: forged})
    output = agent(session, "sentiment")
    assert output.status == "degraded" and output.confidence == 0
    assert not output.evidence and not output.citations
    assert session["metrics"]["rejected_claim_count"] == len(original.evidence)


def test_failed_producer_cannot_display_high_confidence(store, retriever):
    original = agent(run(store, retriever), "sentiment")
    forged = original.model_copy(update={"status": "failed", "confidence": 1}, deep=True)
    output = agent(run(store, retriever, overrides={"sentiment": lambda: forged}), "sentiment")
    assert output.status == "failed" and output.confidence == 0
    assert output.label == "UNKNOWN" and not output.evidence and not output.citations
