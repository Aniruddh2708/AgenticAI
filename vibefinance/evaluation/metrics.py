from vibefinance.agents.risk_agent import what_if
from vibefinance.evaluation.backtest import backtest


def session_metrics(outputs, recommendation, profile, total_ms, parallel_ms):
    evidence_count = sum(len(out.evidence) for out in outputs)
    cited_evidence = sum(len(out.evidence) for out in outputs if out.citations)
    summed_ms = sum(out.latency_ms for out in outputs)
    evaluation = backtest()
    return {"total_latency_ms": total_ms, "parallel_agents_ms": parallel_ms,
            "agent_latency_ms": {out.dimension: out.latency_ms for out in outputs},
            "sum_agent_latency_ms": summed_ms,
            "estimated_parallel_speedup": summed_ms / parallel_ms if parallel_ms > 0 else 0,
            "citation_coverage": cited_evidence / evidence_count if evidence_count else None,
            "evidence_count": evidence_count,
            "degraded_agent_count": sum(out.status == "degraded" for out in outputs),
            "failed_agent_count": sum(out.status == "failed" for out in outputs),
            "technical_backtest_hit_rate": evaluation["hit_rate"],
            "technical_backtest_sample_size": evaluation["sample_size"],
            "technical_backtest_brier_score": evaluation["brier_score"],
            **what_if(profile, recommendation.ticker, recommendation.action)}
