from vibefinance.agents.base import Citation


def validate_citations(citations: list[Citation], allowed: dict[str, Citation]):
    """Accept exact retrieved/registered passages only; reject invented or altered claims."""
    valid, rejected = [], []
    for citation in citations:
        source = allowed.get(citation.chunk_id)
        if source is None or any(getattr(citation, field) != getattr(source, field)
                                 for field in ("source_id", "doc_title", "excerpt", "date")):
            rejected.append(citation.chunk_id)
        else:
            valid.append(citation)
    return valid, rejected
