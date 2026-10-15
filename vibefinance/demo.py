"""Start both local services; shut down only children started by this launcher."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from vibefinance.deployment import dashboard_binding, release_revision


SERVICE_READINESS_TIMEOUT_SECONDS = 120.0


def main():
    root = Path(__file__).resolve().parent.parent
    children = []
    stopping = False
    api_host = os.getenv("VIBEFINANCE_API_HOST", "127.0.0.1")
    api_port = int(os.getenv("VIBEFINANCE_API_PORT", "8000"))
    dashboard_host, dashboard_port = dashboard_binding()
    if any(host not in {"127.0.0.1", "localhost", "::1"} for host in (api_host, dashboard_host)) and not os.getenv("VIBEFINANCE_API_TOKEN"):
        raise RuntimeError("External service binding requires VIBEFINANCE_API_TOKEN for shared-demo access.")
    api_url = f"http://127.0.0.1:{api_port}"
    dashboard_url = f"http://127.0.0.1:{dashboard_port}"
    if revision := release_revision():
        print(f"Starting VibeFinance revision {revision}", flush=True)

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        # Fail on occupied ports rather than taking over pre-existing processes.
        import socket
        for host, port in ((api_host, api_port), (dashboard_host, dashboard_port)):
            with socket.socket() as sock:
                sock.bind((host, port))
        children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "vibefinance.api:app",
            "--host", api_host, "--port", str(api_port)], cwd=root))
        children.append(subprocess.Popen([sys.executable, "-m", "streamlit", "run", "vibefinance/dashboard.py",
            "--server.address", dashboard_host, "--server.port", str(dashboard_port), "--server.headless", "true",
            "--browser.gatherUsageStats", "false"], cwd=root,
            env={**os.environ, "PYTHONPATH": str(root), "VIBEFINANCE_API_URL": api_url}))
        deadline = time.monotonic() + SERVICE_READINESS_TIMEOUT_SECONDS
        while time.monotonic() < deadline and not stopping:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A service exited during startup")
            try:
                health = httpx.get(api_url + "/health", timeout=1)
                dashboard = httpx.get(dashboard_url + "/_stcore/health", timeout=1)
                if health.status_code == dashboard.status_code == 200 and health.json().get("status") in {"ok", "degraded"}:
                    print(f"API and dashboard ready on ports {api_port} and {dashboard_port}.", flush=True)
                    if health.json()["status"] == "degraded":
                        print("Running with degraded retrieval/storage; inspect API health and analysis warnings.", flush=True)
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.2)
        else:
            if not stopping:
                raise RuntimeError("Service readiness timed out")
        while not stopping:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A service exited")
            time.sleep(.5)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
