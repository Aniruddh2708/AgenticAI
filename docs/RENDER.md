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
- Keep the API on `127.0.0.1:8000`. In demo mode (`VIBEFINANCE_AUTH_MODE=demo`,
  the default), Render opens the hackathon dashboard and its API without a
  password. `VIBEFINANCE_PUBLIC_DEMO=1` also enables this explicitly. Leave the
  old securely configured `VIBEFINANCE_API_TOKEN` intact; it is ignored in public
  mode. Remove any explicit `VIBEFINANCE_PUBLIC_DEMO=0` override to go public.
- Public mode creates a separate `public-demo-vibefinance.sqlite3` in the
  existing state directory, seeded with the synthetic investors. Existing
  `vibefinance.sqlite3` profiles/history are preserved and never published.
  New public profiles/history are shared; the dashboard says to use sample data.
  Setting `VIBEFINANCE_PUBLIC_DEMO=0` restores the old token gate and database.
  OIDC/Supabase managed accounts always require sign-in, regardless of this flag.
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
portfolio rules. The latest owner request authorizes a password-free hackathon
demo; earlier instructions to retain its password gate are historical.

## Deploy and verify

1. In the existing Render service, confirm its repository and `main` branch.
2. If commit auto-deploy is enabled, wait for the latest push to become Live.
   Otherwise use **Manual Deploy → Deploy latest commit**. Use the latest main
   SHA shown on GitHub, rather than a restart of an older deployment.
3. Confirm Render's deployment details show that exact commit and successful
   startup. Logs include `Starting VibeFinance revision <full SHA>`.
4. Check the public dashboard health endpoint. A 200 response establishes
   readiness, not release identity.
5. Open `/health` on the public dashboard port: require the exact deployed
   `revision`, `public_demo: true` and `authentication_enabled: false`.
6. Open the site in a private/incognito browser. It must load profiles and an
   analysis directly, with no password prompt. Check its footer revision against
   the deployed commit. Open source passages, compare investors and load history.
   Public analysis writes to the shared public demo database. The original
   private database must stay unchanged.
7. The historical research summary remains at `/evaluation/forecast`, with
   80 observations, 91.25% marginal coverage and research-only/exploratory labels.
   These are recorded results, not newly trained forecasts.

Free-tier local files are ephemeral. Redeployment can discard existing SQLite
profiles/history on that tier; this change does not purchase storage or migrate
or reset application state. Preserve the service's existing storage arrangement.

## Access from the coding environment

Deployment API control needs a securely supplied `RENDER_API_KEY` usable at
`api.render.com`. Public verification needs `vibefinance.onrender.com` allowed by
the environment network policy. The API key is separate from the private demo
password; never send either in chat or commit them.

Without the API-key binding, API deployment control is unavailable. Public health
and the pre-login revision can still be verified independently when that host is
allowed, without a demo password or Render API key. If the public host is blocked,
leave live verification pending; a push or health response alone is not proof of
release identity. Manual deployment through the existing Render dashboard remains
available to the service owner when a release is actually needed.

On 15 October 2026, public health returned 200/`ok` and a TLS-verified public
Streamlit connection showed `Deployed revision: 2ce77198feb5`, matching the pushed
release. This resolves the earlier unknown revision; protected hosted workflows
were not checked. See [evidence](assets/render-release-verification.json).

That is historical release evidence. The current password-free change is
documented separately in [PUBLIC_HACKATHON.md](PUBLIC_HACKATHON.md); a local test
or successful Git push does not establish which revision Render is serving.
