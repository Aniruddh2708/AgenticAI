"""Verify an existing demo image locally; create and clean up only this test's resources."""
import argparse
import json
import os
import secrets
import subprocess
import time

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="vibefinance:local")
    parser.add_argument("--port", type=int, default=18601)
    parser.add_argument("--docker-config", default=".runtime/docker-config")
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    suffix = secrets.token_hex(5)
    name = f"vibefinance-verification-{suffix}"
    volume = f"vibefinance-verification-state-{suffix}"
    # This ephemeral test credential stays in process memory. Never print it.
    token = secrets.token_urlsafe(32)
    docker = ["docker", "--config", args.docker_config]

    def run(*arguments, **kwargs):
        result = subprocess.run([*docker, *arguments], text=True, capture_output=True, **kwargs)
        if result.returncode:
            # Check snippets never print credentials; surface the meaningful failure.
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Docker command failed")
        return result

    created_container = False
    created_volume = False
    try:
        run("volume", "create", volume)
        created_volume = True
        run("run", "--detach", "--name", name, "--publish", f"127.0.0.1:{args.port}:8501",
            "--env", "VIBEFINANCE_API_TOKEN", "--volume", f"{volume}:/data", args.image,
            env={**os.environ, "VIBEFINANCE_API_TOKEN": token})
        created_container = True
        url = f"http://127.0.0.1:{args.port}"

        def wait_for_dashboard():
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    if httpx.get(url + "/_stcore/health", timeout=2).status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(.25)
            raise RuntimeError("Container dashboard did not become healthy")

        wait_for_dashboard()
        info = json.loads(run("inspect", name).stdout)[0]
        assert info["Config"]["User"] == "vibefinance", "Image must not run as root"
        assert not info["NetworkSettings"]["Ports"].get("8000/tcp"), "Internal API must not be published"
        check_api = """
import httpx,os
api='http://127.0.0.1:8000'
assert httpx.get(api+'/profiles').status_code == 401
headers={'Authorization':'Bearer '+os.environ['VIBEFINANCE_API_TOKEN']}
assert httpx.get(api+'/profiles',headers=headers).status_code == 200
result=httpx.post(api+'/analyze',headers=headers,json={'user_id':'arjun','ticker':'RELIANCE.NS'},timeout=60)
assert result.status_code == 200
body=result.json()
assert body['persistence']['status'] == 'saved'
assert len(body['recommendation']['agent_outputs']) == 5
print(body['session_id'])
"""
        session_id = run("exec", name, "python", "-c", check_api).stdout.strip()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, executable_path=args.chromium)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded")
            gate = page.get_by_label("Demo access token", exact=True)
            gate.wait_for(timeout=60000)
            assert not page.get_by_role("tab", name="Analysis", exact=True).count()
            gate.fill(token)
            page.get_by_role("button", name="Open protected demo", exact=True).click()
            page.get_by_role("tab", name="Analysis", exact=True).wait_for(timeout=60000)
            assert not page.locator('[data-testid="stException"]').count()
            browser.close()
        run("restart", name)
        wait_for_dashboard()
        # An exact existing session is the persistence check, not a new generated result.
        check_saved = """
import httpx,os,sys
r=httpx.get('http://127.0.0.1:8000/sessions/'+sys.argv[1],headers={'Authorization':'Bearer '+os.environ['VIBEFINANCE_API_TOKEN']})
assert r.status_code == 200,r.status_code
assert r.json()['session_id'] == sys.argv[1]
"""
        run("exec", name, "python", "-c", check_saved, session_id)
        print(json.dumps({"image": args.image, "dashboard_health": "passed", "non_root": "passed",
                          "api_unpublished": "passed", "api_token": "passed", "dashboard_gate": "passed",
                          "five_agent_analysis": "passed", "persistence_after_restart": "passed"}, indent=2))
    finally:
        if created_container:
            run("stop", name)
            run("rm", name)
        if created_volume:
            run("volume", "rm", volume)
        print("Removed only the verification container and its generated test-data volume.")


if __name__ == "__main__":
    main()
