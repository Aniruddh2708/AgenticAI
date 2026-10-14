"""Capture real Streamlit screens and a silent browser backup; never mock the UI."""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    parser.add_argument("--output", type=Path, default=Path(".runtime/demo-assets"))
    parser.add_argument("--chromium", default=shutil.which("chromium"))
    parser.add_argument("--duration", type=float, default=120,
                        help="Minimum silent video duration in seconds; 0 for a quick check.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Permit updating an existing capture directory.")
    args = parser.parse_args()
    if args.duration < 0:
        parser.error("--duration must not be negative")
    if args.output.exists() and any(args.output.iterdir()) and not args.overwrite:
        parser.error("Output is not empty; choose a new --output directory or use --overwrite")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        parser.error("Install playwright==1.62.0, then a Chromium browser; see docs/DEPLOYMENT.md")
    args.output.mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffmpeg"):
        parser.error("FFmpeg is required to encode the real browser screencast; see docs/DEPLOYMENT.md")
    frames_dir = args.output / "frames"
    frames_dir.mkdir(exist_ok=True)
    frames = []
    shots = []
    browser_errors = []
    run_started = time.monotonic()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=args.chromium)
        context = browser.new_context(viewport={"width": 1440, "height": 1050})
        page = context.new_page()
        # Public Chromium CDP gives actual screen frames. Encoding with the installed
        # FFmpeg avoids dependence on Playwright's separately downloaded FFmpeg.
        screencast = context.new_cdp_session(page)

        def record_frame(event):
            try:
                filename = f"frame-{len(frames):06d}.jpg"
                (frames_dir / filename).write_bytes(base64.b64decode(event["data"]))
                frames.append((filename, time.monotonic()))
            finally:
                screencast.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})

        screencast.on("Page.screencastFrame", record_frame)
        screencast.send("Page.startScreencast", {"format": "jpeg", "quality": 65,
                        "maxWidth": 1440, "maxHeight": 1050, "everyNthFrame": 3})
        page.on("pageerror", lambda error: browser_errors.append(str(error)))
        page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        page.get_by_role("heading", name="VibeFinance", exact=True).wait_for(timeout=60000)
        access_token = os.getenv("VIBEFINANCE_API_TOKEN", "")
        if access_token:
            gate = page.get_by_label("Demo access token", exact=True)
            gate.wait_for(timeout=60000)
            gate.fill(access_token)
            page.get_by_role("button", name="Open protected demo", exact=True).click()
        page.get_by_role("tab", name="Analysis", exact=True).wait_for(timeout=60000)
        active_tab = "Analysis"

        def ready():
            page.get_by_role("heading", name="VibeFinance", exact=True).wait_for(timeout=60000)
            # Streamlit reruns swap in a disabled Run button while executing.
            page.get_by_role("button", name="Run analysis", exact=True).wait_for(timeout=60000)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                running = page.locator('[data-testid="stSpinner"]').count()
                if not running and page.get_by_role("button", name="Run analysis", exact=True).is_enabled():
                    break
                page.wait_for_timeout(200)
            else:
                raise RuntimeError("Streamlit analysis did not complete")
            errors = page.locator('[data-testid="stException"]')
            if errors.count():
                raise RuntimeError("Dashboard exception: " + errors.first.inner_text())
            page.wait_for_timeout(500)

        def tab(name):
            nonlocal active_tab
            active_tab = name
            page.get_by_role("tab", name=name, exact=True).click()
            ready()

        def capture(name, purpose, focus=None):
            ready()
            # Streamlit reruns can reset the visible native tab even though the
            # button's result exists. Restore the actual intended view before capture.
            selected_tab = page.get_by_role("tab", name=active_tab, exact=True)
            if selected_tab.get_attribute("aria-selected") != "true":
                selected_tab.click()
                page.wait_for_timeout(300)
            assert selected_tab.get_attribute("aria-selected") == "true"
            if focus is not None:
                focus.evaluate("element => element.scrollIntoView({block: 'center'})")
                page.wait_for_timeout(350)
                box = focus.bounding_box()
                assert box and 0 <= box["y"] < 1050, "Requested capture detail is outside the viewport"
            path = args.output / f"{name}.png"
            page.screenshot(path=str(path), full_page=True)
            shots.append({"file": path.name, "tab": active_tab, "purpose": purpose})
            print(f"Captured {path}", flush=True)
            if args.duration:
                page.wait_for_timeout(2500)

        ready()
        capture("01-analysis", "Default RELIANCE analysis, disclosed synthetic inputs")
        tab("Sources")
        # Closed details exclude their buttons from the accessibility tree. Open
        # an actual filing first, then request and verify its highlighted passage.
        summary = page.locator('[data-testid="stExpander"] summary').filter(
            has_text="Quarterly results summary").first
        summary.wait_for(timeout=60000)
        expander = summary.locator("xpath=ancestor::details[1]")
        if expander.get_attribute("open") is None:
            summary.click()
        expander.get_by_role("button", name="Show source passage", exact=True).click()
        ready()
        tab("Sources")
        if expander.get_attribute("open") is None:
            summary.click()
        heading = page.get_by_text("Source document — cited passage highlighted", exact=True)
        heading.wait_for(state="visible", timeout=60000)
        heading.scroll_into_view_if_needed()
        highlight = page.locator("mark").first
        highlight.wait_for(state="visible", timeout=60000)
        capture("02-sources", "Exact synthetic source document with its cited passage visibly highlighted", focus=highlight)
        tab("Portfolio & watchlist")
        capture("03-portfolio", "Cash-aware allocation and illustrative portfolio what-if")
        tab("Compare users")
        page.get_by_role("button", name="Compare all three profiles", exact=True).click()
        ready()
        # The genuine beginner view hides numerical context. Switch explicitly
        # before recording the profile constraints and quantitative evidence.
        beginner = page.get_by_role("checkbox", name="Plain-language mode", exact=True)
        if beginner.count() and beginner.is_checked():
            # Streamlit's toggle uses a hidden input; click its visible label.
            page.get_by_text("Plain-language mode", exact=True).click()
            ready()
        capture("04-comparison", "Three profiles using identical market and document inputs")
        tab("Metrics")
        evaluation_heading = page.get_by_role("heading", name="Walk-forward technical direction evaluation", exact=True)
        if evaluation_heading.count():
            evaluation_heading.scroll_into_view_if_needed()
            capture("05-evaluation", "Actual synthetic sample, baseline comparison and uncertainty disclosure")
        calibration = page.get_by_text("Momentum up-direction probability calibration", exact=True)
        if calibration.count():
            calibration.scroll_into_view_if_needed()
            capture("05-calibration", "Actual defined-outcome calibration chart; action strength is not profit probability")
        replay = page.get_by_role("button", name="Run point-in-time policy replay", exact=True)
        if replay.count():
            replay.click()
            page.get_by_role("heading", name="Full-agent synthetic policy replay", exact=True).wait_for(timeout=60000)
        benchmark = page.get_by_role("button", name="Measure parallel versus sequential agents", exact=True)
        if benchmark.count():
            benchmark.click()
            page.get_by_text("Sequential / parallel time", exact=True).wait_for(timeout=60000)
        capture("05-metrics", "Measured latency and honestly scoped synthetic evaluation")
        tab("History")
        capture("06-history", "Recorded analysis sessions, without creating user decisions")
        profile_editor = page.locator('[data-testid="stSidebar"]').get_by_text(
            "Create or edit an investor profile", exact=True)
        if profile_editor.count():
            profile_editor.click()
            capture("07-profile", "Sidebar profile form; no edits submitted")
            profile_editor.click()

        def choose_ticker(symbol):
            wrapper = page.locator('[data-testid="stSelectbox"]').filter(
                has=page.get_by_text("NSE ticker", exact=True))
            wrapper.get_by_role("combobox").click()
            page.get_by_role("option", name=symbol, exact=True).click()
            ready()
            tab("Analysis")
            page.get_by_role("heading", name=re.compile("^" + re.escape(symbol.removesuffix(".NS")) + " ·")).wait_for(timeout=60000)

        choose_ticker("TCS.NS")
        capture("08-conflict", "Bullish momentum opposed by cautionary synthetic filing")
        choose_ticker("ITC.NS")
        capture("09-outage", "Seeded sentiment outage with degraded analysis")
        choose_ticker("HDFCBANK.NS")
        capture("10-missing-filing", "Missing-document disclosure without fabricated fundamentals")
        # Keep an actual moving browser frame during a longer backup recording.
        recording_started = frames[0][1] if frames else run_started
        remaining = args.duration - (time.monotonic() - recording_started)
        while remaining > 0:
            for name in ("Analysis", "Sources", "Metrics"):
                tab(name)
                page.wait_for_timeout(min(6000, max(0, remaining * 1000)))
                remaining = args.duration - (time.monotonic() - recording_started)
                if remaining <= 0:
                    break
        recording_ended = time.monotonic()
        screencast.send("Page.stopScreencast")
        context.close()
        browser.close()
    if not frames:
        raise RuntimeError("Chromium produced no screencast frames; no backup video was generated")
    # Keep the real elapsed duration between screen updates, including idle periods.
    # This is a browser recording, not an invented screenshot slideshow.
    concat = ["ffconcat version 1.0"]
    for index, (filename, observed) in enumerate(frames):
        next_observed = frames[index + 1][1] if index + 1 < len(frames) else recording_ended
        concat.extend([f"file 'frames/{filename}'", f"duration {max(.04, next_observed - observed):.6f}"])
    concat.append(f"file 'frames/{frames[-1][0]}'")
    concat_file = args.output / "screencast.ffconcat"
    concat_file.write_text("\n".join(concat) + "\n")
    candidate = args.output / "dashboard-backup.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "1",
                    "-i", str(concat_file), "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-r", "10",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(candidate)],
                   check=True)
    manifest = {"dashboard_url": args.url, "screenshots": shots,
                "mp4": candidate.name, "capture_method": "Chromium CDP screencast + system FFmpeg",
                "recorded_browser_frames": len(frames),
                "elapsed_seconds": round(time.monotonic() - run_started, 2),
                "browser_errors": browser_errors,
                "disclosure": "Real browser capture of a synthetic-data demo; silent automation, no narration."}
    # Generated artifact output; no application, test or tracked data is rewritten.
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 1 if browser_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
