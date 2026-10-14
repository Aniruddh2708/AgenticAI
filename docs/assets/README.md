# Actual demo assets

These files were generated from the running application using seeded simulated
market data and fabricated company documents. They are real browser captures, not
mocked screenshots. No real investor data or credentials appear in them.

- `VibeFinance-presentation.pdf`: the eight-page print version of
  [`../PRESENTATION.html`](../PRESENTATION.html).
- `presentation-title.png`: the actual browser-rendered opening slide.
- `demo/`: twelve screenshots covering analysis, the visibly highlighted source
  passage, portfolio what-if, three-user comparison, technical evaluation,
  calibration, policy/latency metrics, history, profile editor, conflict, sentiment
  outage and missing filing.
- `demo/dashboard-backup.mp4`: approximately two minutes (119.3 seconds), recorded
  from the actual Chromium screen stream and encoded by FFmpeg. It is silent and
  automated; it is not a narrated or rehearsed presentation.
- `demo/manifest.json`: capture methods, actual view labels and zero observed
  JavaScript page errors. Its loopback URL describes the recording environment,
  not a published website.

The complete assets total approximately 3.4 MB. Intermediate browser frames,
temporary databases and virtual environments remain under ignored `.runtime/`
directories and are not included here.

The metrics screenshots report the observed values from that capture run. Timing
results depend on workload and host conditions. Synthetic accuracy and calibrated
technical direction scores do not establish investment outperformance or calibrated
recommendation success.

Regenerate with [`../../scripts/capture_demo.py`](../../scripts/capture_demo.py);
see [`../DEPLOYMENT.md`](../DEPLOYMENT.md) for runtime prerequisites. These files
will only appear in GitHub after the corresponding repository changes are committed
and pushed. An internal workspace path is not a public download URL.
