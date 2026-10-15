# Update the existing Render service

Deploy the existing `vibefinance` service from `Aniruddh2708/AgenticAI`, branch
`main`. Do not create a second service, rotate its demo token, change its plan,
or replace its existing state configuration just to release new code.

## Runtime configuration

The application supports both existing Docker and native Python services:

- Start command: `python -m vibefinance.demo` (root `python demo.py` delegates
  to the same implementation).
- For native Python builds: `python -m pip install --require-hashes -r requirements.lock`.
  The repository pins Python 3.11.17 in `.python-version`; an existing Render
  `PYTHON_VERSION` override takes precedence and should remain compatible.
- Render supplies `RENDER=true` and `PORT`. The dashboard binds to the assigned
  port and public interface by default. Existing explicit
  `VIBEFINANCE_DASHBOARD_HOST`/`VIBEFINANCE_DASHBOARD_PORT` settings take precedence.
- Keep the API on `127.0.0.1:8000`. Keep the existing securely configured
  `VIBEFINANCE_API_TOKEN`; externally bound startup still requires it.
- Keep the existing BM25 configuration. Do not enable embeddings or train models
  during a free-tier deployment.
- Health check: `/_stcore/health` on the public dashboard port.

On Render, the report defaults to the tracked corrected summary at
`docs/assets/forecast-followup-summary.json`. Both Docker recipes copy this file;
native builds already have it in the checkout. Ignored workstation `.runtime`
files and historical downloads are unnecessary. An explicit
`VIBEFINANCE_FORECAST_REPORT` setting is preserved; if it points at an old/missing
workstation report, update that setting to
`docs/assets/forecast-followup-summary.json`.

The report remains research-only, with failed admission and spent/exploratory
labels. Publishing this dashboard does not promote a forecasting model or alter
portfolio rules. The demo access gate and API authentication remain enabled.

## Deploy and verify

1. In the existing Render service, confirm its repository and `main` branch.
2. If commit auto-deploy is enabled, wait for the latest push to become Live.
   Otherwise use **Manual Deploy → Deploy latest commit**. Use the latest main
   SHA shown on GitHub, rather than a restart of an older deployment.
3. Confirm Render's deployment details show that exact commit and successful
   startup. Logs include `Starting VibeFinance revision <full SHA>`.
4. Check the public dashboard health endpoint. A 200 response establishes
   readiness, not release identity.
5. Refresh the dashboard. `Deployed revision: <12-character SHA>` is visible on
   the login page before any password is entered; compare it with the deployed
   commit. No private demo password is needed to check the release marker.
6. Authorized viewers can open Metrics → **Load real-history forecast audit**.
   It should show 80 observations, 91.25% marginal coverage, the exploratory
   correction with ten complete origins/twelve excluded partial origins, and
   research-only status. These are recorded results, not newly trained forecasts.

Free-tier local files are ephemeral. Redeployment can discard existing SQLite
profiles/history on that tier; this change does not purchase storage or migrate
or reset application state. Preserve the service's existing storage arrangement.

## Access from the coding environment

Deployment API control needs a securely supplied `RENDER_API_KEY` usable at
`api.render.com`. Public verification needs `vibefinance.onrender.com` allowed by
the environment network policy. The API key is separate from the private demo
password; never send either in chat or commit them.

If those bindings are unavailable, the code can be prepared, tested and pushed,
but API deployment and live-release verification must not be claimed complete.
Manual deployment through the existing Render dashboard remains available to
the service owner.
