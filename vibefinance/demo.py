"""Start both local services; shut down only children started by this launcher."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx


def main():
    root = Path(__file__).resolve().parent.parent
    children = []
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        # Fail on occupied ports rather than taking over pre-existing processes.
        import socket
        for port in (8000, 8501):
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", port))
        children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "vibefinance.api:app",
            "--host", "127.0.0.1", "--port", "8000"], cwd=root))
        children.append(subprocess.Popen([sys.executable, "-m", "streamlit", "run", "vibefinance/dashboard.py",
            "--server.address", "127.0.0.1", "--server.port", "8501", "--server.headless", "true",
            "--browser.gatherUsageStats", "false"], cwd=root,
            env={**os.environ, "PYTHONPATH": str(root), "VIBEFINANCE_API_URL": "http://127.0.0.1:8000"}))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not stopping:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A service exited during startup")
            try:
                health = httpx.get("http://127.0.0.1:8000/health", timeout=1)
                dashboard = httpx.get("http://127.0.0.1:8501/_stcore/health", timeout=1)
                if health.status_code == dashboard.status_code == 200 and health.json()["corpus_chunks"] > 0:
                    print("API and dashboard ready on local ports 8000 and 8501.", flush=True)
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
