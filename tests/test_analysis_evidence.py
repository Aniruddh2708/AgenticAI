"""Regression tests for negation, financial facts and bounded claim support."""

import pytest

from vibefinance.agents import filings_agent, sentiment_agent
from vibefinance.agents.base import Citation, EvidenceClaim
from vibefinance.analysis.financial_facts import extract_financial_facts
from vibefinance.analysis.text import tone
from vibefinance.rag.ingest import Chunk
from vibefinance.rag.validator import validate_claims


def chunk(text, doc_type="results"):
    return Chunk(source_id="test", ticker="RELIANCE.NS", doc_type=doc_type,
                 date="2026-09-25", title="Test source [SYNTHETIC]", chunk_id="test:0", text=text)


@pytest.mark.parametrize("text", [
    "No growth is expected.", "There is no revenue growth.",
    "Revenue growth of 12.5% was not achieved.", "Revenue growth -5%.",
    "Demand is not strong.", "Weak demand and guidance cut.",
    "Debt growth is a concern.", "Regulatory investigation caused a delay.",
])
def test_negative_phrases_and_negated_positive(text):
    assert tone(text)[2] < 0


@pytest.mark.parametrize("text", [
    "There is no litigation.", "We did not cut guidance.",
    "No weak demand was observed.", "No revenue decline was reported.",
])
def test_absence_of_negative_is_neutral_not_bullish(text):
    assert tone(text) == (0, 0, 0)


def test_negation_scope_stops_at_contrast_and_not_only_is_positive():
    assert tone("No growth, but strong demand.")[:2] == (1, 1)
    assert tone("Not only strong growth but improved margins.")[2] > 0


def test_numbers_attach_to_the_correct_metric():
    facts = extract_financial_facts("Revenue growth of 12%, profit growth of 9%. Operating profit improved 4%.")
    values = {fact.key: fact.value for fact in facts}
    assert values == {"revenue_change_pct": 12, "profit_change_pct": 9,
                      "operating_profit_change_pct": 4}


def test_decline_debt_and_percentage_points_have_correct_direction_and_units():
    facts = extract_financial_facts(
        "Profit decline of 6%. Debt reduced by 5%. Operating margin rose from 12% to 15%. "
        "Net debt stood at INR 100 crore. Margin was 15%."
    )
    lookup = {fact.key: fact for fact in facts}
    assert lookup["profit_change_pct"].value == -6
    assert lookup["profit_change_pct"].polarity == -1
    assert lookup["debt_change_pct"].value == -5
    assert lookup["debt_change_pct"].polarity == 1
    assert lookup["operating_margin_change_pp"].value == 3
    assert lookup["operating_margin_change_pp"].unit == "percentage_points"
    assert lookup["net_debt_amount"].value == 100
    assert lookup["net_debt_amount"].unit == "INR_crore"
    assert lookup["margin_level_pct"].polarity == 0


def test_negated_unsupported_and_invalid_numeric_facts_are_omitted():
    assert extract_financial_facts("No revenue growth of 12%. No guidance cut. No litigation.") == []
    assert extract_financial_facts("Revenue might be 42 someday. Operating margin was 120%.") == []
    assert extract_financial_facts("Revenue growth of 12% was not achieved.") == []
    assert extract_financial_facts("Profit decline of -6%.") == []


def test_negative_growth_and_resolved_litigation_are_not_positive_or_active_risk():
    fact = extract_financial_facts("Revenue growth -5%.")[0]
    assert fact.value == -5 and fact.polarity == -1
    facts = extract_financial_facts("Litigation resolved.")
    assert [fact.key for fact in facts] == ["legal_resolution"]
    assert tone("Litigation resolved.") == (0, 0, 0)


def test_future_statement_is_not_presented_as_an_observed_result():
    fact = extract_financial_facts("Management expects revenue growth of 12%.")[0]
    assert fact.text.startswith("Source outlook statement")


def test_guidance_legal_and_demand_facts_keep_source_qualification():
    facts = extract_financial_facts("Guidance cut after weak bookings. Litigation remains unresolved.")
    assert {fact.key for fact in facts} == {"guidance_cut", "demand_weakness", "legal_regulatory_risk"}
    assert all(fact.polarity == -1 for fact in facts)
    assert next(f for f in facts if f.key == "guidance_cut").text.startswith("Source outlook statement")
    assert next(f for f in facts if f.key == "legal_regulatory_risk").text.startswith("Source statement")


def test_sentiment_evidence_is_exact_source_text_and_negation_changes_label():
    source = chunk("No growth is expected. Weak demand persists.", "news")
    output = sentiment_agent.analyze("RELIANCE.NS", [(source, .8)])
    assert output.label == "NEGATIVE"
    assert output.evidence == [claim.text for claim in output.claims]
    assert all(claim.text in source.text for claim in output.claims)
    valid, rejected = validate_claims(output.claims, {source.chunk_id: source.citation(.8)})
    assert valid == output.claims and rejected == []


def test_filings_return_financial_facts_and_supported_quotes():
    source = chunk("Synthetic scenario: revenue growth of 12%, profit improved 9%. Guidance raised.")
    output = filings_agent.analyze("RELIANCE.NS", [(source, .8)])
    assert output.label == "SUPPORTIVE"
    assert output.evidence == [claim.text for claim in output.claims]
    assert {claim.fact_key for claim in output.claims if claim.method == "financial_fact"} == {
        "revenue_change_pct", "profit_change_pct", "guidance_raised"
    }
    valid, rejected = validate_claims(output.claims, {source.chunk_id: source.citation(.8)})
    assert valid == output.claims and rejected == []


def test_no_recognized_phrase_is_degraded_without_invented_financial_claims():
    source = chunk("This document lists the office address.")
    for agent in (sentiment_agent, filings_agent):
        output = agent.analyze("RELIANCE.NS", [(source, .8)])
        assert output.status == "degraded"
        assert not output.evidence and not output.claims and not output.citations


def test_quote_validation_rejects_paraphrase_unknown_source_and_extra_metadata():
    source = chunk("Revenue growth of 12%.")
    allowed = {source.chunk_id: source.citation(.8)}
    correct = EvidenceClaim(claim_id="quote", text=source.text,
                            citation_ids=[source.chunk_id], method="quotation")
    altered = correct.model_copy(update={"claim_id": "altered", "text": "Revenue grew by 12%."})
    absent = correct.model_copy(update={"claim_id": "missing", "citation_ids": ["missing:0"]})
    fake_fact = correct.model_copy(update={"claim_id": "extra", "value": 100})
    valid, rejected = validate_claims([correct, altered, absent, fake_fact], allowed)
    assert valid == [correct]
    assert rejected == ["altered", "missing", "extra"]


def test_financial_fact_validation_rejects_swapped_amount_and_unsupported_text():
    source = chunk("Revenue growth of 12%, profit growth of 9%.")
    output = filings_agent.analyze("RELIANCE.NS", [(source, .8)])
    fact = next(claim for claim in output.claims if claim.fact_key == "profit_change_pct")
    wrong_value = fact.model_copy(update={"claim_id": "wrong-value", "value": 12})
    wrong_text = fact.model_copy(update={"claim_id": "wrong-text", "text": "The company guarantees future profits."})
    wrong_unit = fact.model_copy(update={"claim_id": "wrong-unit", "unit": "INR_crore"})
    valid, rejected = validate_claims([fact, wrong_value, wrong_text, wrong_unit],
                                    {source.chunk_id: source.citation(.8)})
    assert valid == [fact] and len(rejected) == 3


def test_duplicate_claim_ids_and_misattributed_second_source_rejected():
    source = chunk("Revenue growth of 12%.")
    allowed = {source.chunk_id: source.citation()}
    allowed["other:0"] = Citation(source_id="other", doc_title="Other", chunk_id="other:0",
                                   excerpt="Profit decline of 4%.", score=1)
    claim = EvidenceClaim(claim_id="q", text=source.text, citation_ids=[source.chunk_id], method="quotation")
    unrelated = claim.model_copy(update={"claim_id": "unrelated", "citation_ids": [source.chunk_id, "other:0"]})
    valid, rejected = validate_claims([claim, claim, unrelated], allowed)
    assert valid == [claim] and rejected == ["q", "unrelated"]


def test_computed_claim_requires_exact_independently_approved_template():
    source = chunk("Price snapshot")
    allowed = {source.chunk_id: source.citation()}
    claim = EvidenceClaim(claim_id="computed", text="RSI is 70.", citation_ids=[source.chunk_id],
                          method="computed", fact_key="rsi", value=70, unit="index")
    assert validate_claims([claim], allowed) == ([], [claim.claim_id])
    assert validate_claims([claim], allowed, {claim.claim_id: claim}) == ([claim], [])
    altered = claim.model_copy(update={"value": 99})
    assert validate_claims([altered], allowed, [claim]) == ([], [claim.claim_id])
