"""Held-out source-ranking evaluation with independently supplied judgments.

Source-span integrity is distinct from semantic claim support. This evaluator
does not generate relevance labels, tune queries, or certify source truth.
"""
import math

from vibefinance.data.quality import digest


def evaluate(retriever, questions, *, k=4):
    if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= 20:
        raise ValueError("Use a declared k from 1 to 20")
    if not questions or len({q["id"] for q in questions}) != len(questions):
        raise ValueError("Unique nonempty held-out questions required")
    records = []
    for q in questions:
        if q["split"] != "held_out" or not q["judged_by"] or not q["judgment_evidence"]:
            raise ValueError("Held-out designation and actual judgment evidence required")
        grades = q["relevance_by_source_id"]
        if (not isinstance(grades, dict) or not grades or
                any(type(v) is not int or v not in (0, 1, 2) for v in grades.values()) or not max(grades.values())):
            raise ValueError("Explicit graded relevance judgments required")
        found = retriever.retrieve(q["query"], q["ticker"], k, q.get("doc_types"),
                                   as_of=q["as_of"], source_kinds={"authentic"})
        ids = list(dict.fromkeys(c.source_id for c, _ in found))
        unjudged = [s for s in ids if s not in grades]
        # Do not silently treat unjudged results as irrelevant: keep the score
        # unavailable until the judgment pool covers returned documents.
        relevant = {s for s, grade in grades.items() if grade > 0}
        dcg = sum((2**grades.get(s, 0)-1)/math.log2(i+2) for i, s in enumerate(ids))
        ideal = sum((2**g-1)/math.log2(i+2) for i, g in enumerate(sorted(grades.values(), reverse=True)[:k]))
        integrity = all(c.span_start is not None and c.span_end is not None and
                        c.document_text[c.span_start:c.span_end] == c.text for c, _ in found)
        records.append({"id": q["id"], "source_ids": ids, "unjudged_source_ids": unjudged,
            "ndcg_at_k": dcg/ideal if not unjudged else None,
            "recall_at_k": len(set(ids)&relevant)/len(relevant) if not unjudged else None,
            "exact_span_integrity": integrity, "returned_chunks": len(found),
            "citation_semantic_support": "requires separate claim-level judgments; span checks establish provenance only"})
    complete = all(not r["unjudged_source_ids"] for r in records)
    return {"schema_version": 1, "kind": "held_out_retrieval_evaluation", "question_count": len(records),
        "questions_sha256": digest(questions), "k": k, "mode": retriever.mode,
        "judgment_pool_complete": complete, "rows": records,
        "mean_ndcg_at_k": sum(r["ndcg_at_k"] for r in records)/len(records) if complete else None,
        "mean_recall_at_k": sum(r["recall_at_k"] for r in records)/len(records) if complete else None,
        "all_spans_exact": all(r["exact_span_integrity"] for r in records),
        "semantic_model": "real local model required for neural acceptance" if retriever.mode == "bm25" else "local embedding backend active",
        "limitations": "Operator-supplied judgments and documents need independent review. No model/answer tuning by this evaluator; no claim of generic semantic entailment."}
