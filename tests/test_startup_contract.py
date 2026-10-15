"""Exercise the package entry points used by make demo and API startup."""
import asyncio
import signal
import time
from types import SimpleNamespace

import pytest

import vibefinance.demo as demo
import vibefinance.orchestrator as engine
from vibefinance.data.market_sim import generate_market


def test_retriever_default_initialization_budget_is_sixty_seconds(monkeypatch, retriever):
    budgets = []
    real_wait_for = asyncio.wait_for

    async def observe_wait_for(awaitable, timeout):
        budgets.append(timeout)
        return await real_wait_for(awaitable, timeout)

    monkeypatch.setattr(engine.asyncio, "wait_for", observe_wait_for)
    monkeypatch.setattr(engine, "Retriever", lambda: retriever)
    assert asyncio.run(engine.prepare_retriever()) is retriever
    assert budgets == [60.0]


def test_cold_analysis_does_not_apply_agent_deadline_to_initialization(monkeypatch, store, retriever):
    real_constructor = engine.Retriever
    initialization_calls = []

    def cold_constructor(*args, **kwargs):
        if args or kwargs:
            # A timeout fallback would reach this branch, exposing the regression.
            return real_constructor(*args, **kwargs)
        initialization_calls.append(True)
        time.sleep(.05)
        return retriever

    monkeypatch.setattr(engine, "Retriever", cold_constructor)
    session = asyncio.run(engine.analyze("RELIANCE.NS", store.profile("arjun"),
        frame=generate_market("RELIANCE.NS"), timeout=.01, persist=False))
    assert initialization_calls == [True]
    assert any(source["source_id"].endswith("_demo") for source in session["sources"])
    assert not any("initialization unavailable" in warning for warning in session["warnings"])


def _launcher_stubs(monkeypatch, ready_after):
    clock = {"now": 0.0, "ready_at": None}
    handlers = {}
    children = []

    class Child:
        terminated = False

        def poll(self):
            return 0 if self.terminated else None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            return 0

    def spawn(*args, **kwargs):
        child = Child()
        children.append(child)
        return child

    def sleep(seconds):
        clock["now"] += seconds
        if seconds == .5:
            # The running-service loop is reached only after successful readiness.
            clock["ready_at"] = clock["now"]
            handlers[signal.SIGTERM]()

    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def bind(self, address):
            return None

    def health(*args, **kwargs):
        status_code = 200 if clock["now"] >= ready_after else 503
        return SimpleNamespace(status_code=status_code, json=lambda: {"status": "ok"})

    monkeypatch.setattr(demo, "time", SimpleNamespace(monotonic=lambda: clock["now"], sleep=sleep))
    monkeypatch.setattr(demo, "signal", SimpleNamespace(SIGINT=signal.SIGINT, SIGTERM=signal.SIGTERM,
        signal=lambda name, handler: handlers.__setitem__(name, handler)))
    monkeypatch.setattr(demo.subprocess, "Popen", spawn)
    monkeypatch.setattr(demo.httpx, "get", health)
    import socket
    monkeypatch.setattr(socket, "socket", Socket)
    monkeypatch.setenv("VIBEFINANCE_API_HOST", "127.0.0.1")
    monkeypatch.setenv("VIBEFINANCE_DASHBOARD_HOST", "127.0.0.1")
    return clock, children


def test_package_launcher_allows_readiness_after_thirty_seconds(monkeypatch):
    clock, children = _launcher_stubs(monkeypatch, ready_after=45.0)
    demo.main()
    assert 45.0 <= clock["ready_at"] < 46.0
    assert len(children) == 2 and all(child.terminated for child in children)


def test_package_launcher_bounds_readiness_and_cleans_up_children(monkeypatch):
    clock, children = _launcher_stubs(monkeypatch, ready_after=float("inf"))
    with pytest.raises(RuntimeError, match="Service readiness timed out"):
        demo.main()
    assert 120.0 <= clock["now"] < 121.0
    assert clock["ready_at"] is None
    assert len(children) == 2 and all(child.terminated for child in children)
def test_root_compatibility_entrypoints_use_active_package():
    import demo as legacy_demo
    import orchestrator as legacy_orchestrator
    from vibefinance import demo, orchestrator

    assert legacy_demo.main is demo.main
    assert legacy_orchestrator.prepare_retriever is orchestrator.prepare_retriever
    assert legacy_orchestrator.analyze is orchestrator.analyze
