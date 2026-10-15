"""Check an already-built local candidate image; never contacts Render/Supabase.

Creates only its own named container/volume, uses an ephemeral gate token passed
through process environment, and removes its resources in finally. No image pull,
remote Docker daemon, private account credential, or paid resource is used.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="vibefinance:development-v2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Existing container evidence is preserved")
    root = Path(__file__).resolve().parents[1]
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    env = os.environ.copy()
    for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        env.pop(key, None)
    env["VIBEFINANCE_API_TOKEN"] = secrets.token_urlsafe(32)
    cli = ["docker", "--host=unix:///var/run/docker.sock"]
    def docker(*arguments):
        return subprocess.check_output(cli+list(arguments), env=env, text=True, stderr=subprocess.PIPE).strip()
    name = "vf-development-check-"+secrets.token_hex(6)
    volume = name+"-state"
    checks = []
    report = {"kind": "local_candidate_container", "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "source_revision": revision, "scope": "local core-only demo; not hosted/provider acceptance"}
    try:
        # Refuse daemon image pulls: this checker uses a verified local build.
        report["image_id"] = docker("image", "inspect", "--format={{.Id}}", args.image)
        docker("volume", "create", volume)
        docker("run", "--detach", "--pull=never", "--name", name,
               "--publish", "127.0.0.1::10000", "--volume", volume+":/data",
               "--env", "VIBEFINANCE_API_TOKEN", "--env", "RENDER=true", "--env", "PORT=10000",
               "--env", "RENDER_GIT_COMMIT="+revision, "--env", "VIBEFINANCE_EMBEDDINGS=0", args.image)
        binding = docker("port", name, "10000/tcp")
        url = "http://"+binding.splitlines()[0]
        print("Checking owned candidate on assigned loopback port", binding.splitlines()[0].rsplit(":", 1)[-1], flush=True)
        with httpx.Client(base_url=url, timeout=60) as client:
            def ready():
                deadline = time.monotonic()+120
                last = None
                while time.monotonic() < deadline:
                    try:
                        h = client.get("/health", timeout=2)
                        observation = (h.status_code, h.json().get("status")) if h.status_code == 200 else (h.status_code, None)
                        if observation != last:
                            print("Candidate readiness", observation, flush=True)
                            last = observation
                        if h.status_code == 200 and h.json().get("status") == "ok":
                            return h.json()
                    except (httpx.HTTPError, ValueError):
                        pass
                    time.sleep(.2)
                raise RuntimeError("Owned candidate readiness timed out")
            health = ready()
            print("Checking packaged report and protected routes", flush=True)
            assert health["revision"] == revision and health["corpus_chunks"] == 21
            assert health["storage_available"] is True
            checks.append("assigned port, exact supplied revision, BM25 and storage health")
            assert "VibeFinance XAI" in client.get("/").text
            assert client.get("/profiles").status_code == 401
            headers = {"Authorization": "Bearer "+env["VIBEFINANCE_API_TOKEN"]}
            assert len(client.get("/profiles", headers=headers).json()) == 3
            checks.append("HTML shell and protected API")
            research = client.get("/evaluation/forecast/development", headers=headers).json()
            assert research["available"] and research["admission"]["passed"] is False
            assert research["new_holdout_evaluated"] is False and research["age_calendar_days"] > 0
            checks.append("packaged historical report, no fresh evaluation or model promotion")
            response = client.post("/analyze", json={"user_id": "meera", "ticker": "ITC.NS", "missing_filing": True}, headers=headers)
            response.raise_for_status()
            session = response.json()
            assert session["recommendation"]["action"] == "REDUCE"
            assert session["recommendation"]["decision_basis"] == "portfolio_policy"
            assert session["persistence"]["status"] == "saved"
            session_id = session["session_id"]
            checks.append("concentration priority despite missing evidence; saved session")
            assert docker("exec", name, "id", "-u") == "10001"
            # Hash packaged source independently of its environment revision
            # marker: an environment variable alone cannot prove image parity.
            expected = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (root/"vibefinance").rglob("*.py")}
            command = "import hashlib,json,pathlib; r=pathlib.Path('/app'); print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (r/'vibefinance').rglob('*.py')}))"
            assert json.loads(docker("exec", name, "python", "-c", command)) == expected
            checks.append("UID 10001 and exact packaged Python source hashes")
            report["python_files_verified"] = len(expected)
            print("Checking container restart persistence", flush=True)
            docker("restart", name)
            # This local Docker daemon can reassign ephemeral published ports
            # on restart. Rediscover transport before checking durable state.
            client.base_url = "http://"+docker("port", name, "10000/tcp").splitlines()[0]
            ready()
            saved = client.get("/sessions/"+session_id, headers=headers)
            saved.raise_for_status()
            assert saved.json()["session_id"] == session_id
            checks.append("exact-session SQLite persistence across container restart")
        report.update(ok=True, checks=checks, hosted_acceptance=False)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report, indent=2))
        return 0
    finally:
        # Cleanup is scoped to names generated by this invocation only.
        for command in (("rm", "--force", "--volumes", name), ("volume", "rm", volume)):
            subprocess.run(cli+list(command), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    try:
        result = main()
    except (OSError, RuntimeError, ValueError, AssertionError, subprocess.CalledProcessError, httpx.HTTPError):
        print(json.dumps({"ok": False, "scope": "owned_local_candidate", "error": "Candidate check failed; private diagnostics withheld. Check local image, packaged source parity and runtime readiness."}))
        result = 1
    raise SystemExit(result)
