# Public hackathon demo — 15 October 2026

The owner requested public access without the shared demo password. This change
is isolated on `codex/public-hackathon-demo`, based on main
`ed7a5f4602fa2b241847b366f91e2ff2229500eb`. It does not include the unreviewed
forecast-development branch or change model admission, portfolio safeguards,
research artifacts, dependencies, the Render plan, or provider configuration.

Render supplies `RENDER=true`; in the default demo auth mode this now enables
public access to the HTML dashboard and API. Existing demo tokens can remain
securely configured. The legacy Streamlit dashboard also skips its token form.
`VIBEFINANCE_PUBLIC_DEMO=1` enables the same mode on other hosts; `0` restores
protected demo behavior. Invalid values fail startup. Individual OIDC/Supabase
accounts continue to require verified identities even with the public flag set.

Public storage uses `public-demo-<original filename>` in the same state directory.
It starts with sample profiles and never migrates or reads protected profiles,
sessions or decisions. Original files remain intact. Public profiles and saved
analyses are shared between visitors; both dashboards disclose this before use.
Render Free local storage remains ephemeral across redeploys; no durable paid
resource is created.

## Reproduce

```sh
VIBEFINANCE_EMBEDDINGS=0 VIBEFINANCE_STATE_DIR="$PWD/.runtime/public-demo-tests" \
  .venv/bin/python -m pytest -q --junitxml=.runtime/public-hackathon-tests.xml

# Stop only your own existing services if these ports are already occupied.
RENDER=true PORT=10000 VIBEFINANCE_AUTH_MODE=demo VIBEFINANCE_PUBLIC_DEMO=1 \
  VIBEFINANCE_STATE_DIR="$PWD/.runtime/public-hackathon-local" \
  VIBEFINANCE_EMBEDDINGS=0 .venv/bin/python -m vibefinance.demo
```

Request `/health`, `/profiles` and `POST /analyze` on the dashboard port without
Authorization. Health must report `public_demo: true` and
`authentication_enabled: false`. Analysis must include saved history, citations
and portfolio-risk overrides. The token is unnecessary for this workflow.

## Verification scope

Targeted checks: **34 passed, 1 skipped** (the real PostgreSQL-only fixture).
An actual isolated launcher with Render settings and a retained synthetic old
token passed both-port readiness, HTML/assets, three seeded profiles, saved
five-agent analysis, citation passage and history without sending Authorization.
Meera's concentration reduction remains `REDUCE`. The private-file test hashes
the original database before and after public writes and storage recovery;
the bytes remain unchanged, and protected mode can still read the old data.
The legacy Streamlit UI renders analysis without a password form or token header.

Full suite: **778 passed, 14 skipped** in 41.50 seconds, Linux/Python 3.11.17;
the skips require the existing disposable PostgreSQL fixture. JavaScript syntax
and Git whitespace checks passed. Actual headless Chromium against the real
launcher opened directly, loaded all three profiles and the default analysis,
switched to Meera and displayed `REDUCE`, and loaded saved history. There were
zero password dialogs, HTTP 401 responses or JavaScript exceptions. The shared
demo notice was visible. This is local browser evidence, not hosted acceptance.
See [machine-readable evidence](assets/public-hackathon-verification.json),
including hashes of the verified application files. The branch enables the
existing Linux/Windows/PostgreSQL CI workflow; local results are not CI results.

Live health verification currently fails at the managed outbound proxy, and no
Render deployment credential is configured. No live password-free claim is made.
See [RENDER.md](RENDER.md) for exact deploy and acceptance checks.
