# Free accounts, storage and forecasting: current delivery status

Updated 15 October 2026, Asia/Calcutta. Work started from clean `main` at
`459669b`. The user requires **zero spending**. No paid service, database, disk,
subscription, account purchase or live production migration was performed.

Implementation commit: `f7a2358a071f230b813123127fc49ddde47829f0`, pushed to
[`codex/free-accounts-and-data-verification`](https://github.com/Aniruddh2708/AgenticAI/tree/codex/free-accounts-and-data-verification).
[Review the changes against main](https://github.com/Aniruddh2708/AgenticAI/compare/main...codex/free-accounts-and-data-verification).
Main remains `459669b`; the public Render checker independently confirmed that
revision, healthy responses and the enabled demo gate with verified TLS and no
credentials. See [preservation evidence](assets/render-free-candidate-preservation.json).
GitHub's API credential returned HTTP 401, so no draft PR was created; native Git
push and the public review link work. No credential replacement is needed to
review the branch.

Checks passed locally: **760 application tests**, **121 TLS PostgreSQL checks**,
extended dashboard and production/core-only demo containers. Actual
[Linux, Windows and PostgreSQL CI](https://github.com/Aniruddh2708/AgenticAI/actions/runs/38714395220)
also passed for implementation `f7a2358`; remote test counts were not inferred.

The candidate uses the existing free Render service and an owner-created
**Supabase Free** project. Current provider quotas and plan eligibility must be
checked in their dashboards. The implementation does not promise unlimited
capacity, permanent free pricing or continuous availability.

| Requested work | Delivered and checked | Actual remaining dependency |
|---|---|---|
| Independent data verification | Two real official NSE files acquired for spent dates; four vendor placeholders independently confirmed; strict raw import and permission-gated acquisition added | Complete authorized adjusted history, calendar, corporate actions, equivalent adjustment vintage, point-in-time universe and genuine review are absent; full F1 remains unapproved |
| Fresh forecasting outcomes | Idempotent operations runner, witnessed-registration checks, complete-cohort readiness, missed origins and mature-outcome recording | No genuine study is registered. Thirty verified sessions must close after each actual issuance; enough independent origins/regimes take longer. No new score exists |
| Individual accounts | Managed Supabase sign-in/signup confirmation/logout, asymmetric JWT verification, safe refresh, account-change cache clearing; optional OIDC retained | Owner is creating a free project; actual provider URL/configuration, confirmed users and hosted sign-in are not available yet |
| Durable storage | Account-bound PostgreSQL, forced row security, scoped foreign keys, non-administrative app role, TLS verification, explicit owned-data migration | Configure the owner's actual free database and restricted role; verify live persistence and two-account ownership before activation |
| Recovery | Authenticated encrypted application backups, safe empty-application restore, provider-schema preservation, role ownership and sequence recovery | Configure the owner's backup credentials/key, retain an encrypted copy off-service and perform an actual hosted recovery drill; provider Auth is a separate responsibility |
| Protected hosted acceptance | Supabase-aware checker, credential-name validation, explicit analysis-write acknowledgement, empty-account refusal; private-route/isolation and real browser checks passed in owned local fixtures | An existing confirmed test account and profile must be supplied through secure settings. The private existing demo password was not requested |

## What the real source review establishes

Normal verified HTTPS requests to the official archive succeeded for
**31 December 2020** and **18 March 2025** after the runtime policy changed.
On the latter date, NSE records positive volume and nonflat OHLC for all five
securities, while the pinned Yahoo archive contains flat prior-close rows with
zero volume for RELIANCE, TCS, INFY and HDFCBANK. ITC traded in both sources.
This independently confirms the earlier calendar-quality finding.

On the older date, TCS agrees exactly and INFY agrees within floating-point
rounding; three other securities have unresolved corporate-action price-basis
differences. Two raw daily files do not certify adjusted multiyear history.
No frozen source file, prediction or score was repaired or rerun.

The actual official copyright/terms pages were retrieved and reviewed. Narrow
personal/noncommercial/educational viewing/download conditions do not establish
authorization for systematic automated collection, redistribution or simulation.
Further requests stopped. Automated acquisition now requires a scoped local
permission review and hashed evidence before HTTP; this declaration is not a
legal certification. Authorized local imports remain available.

See [the source evidence record](assets/independent-source-review.json),
[acquisition guide](DATA_ACQUISITION.md) and [F1 requirements](DATA_VERIFICATION.md).
Raw source downloads remain private under ignored `.runtime/exchange/`.

## Activate the free candidate once the project exists

1. Create the project using **Supabase Free**. Share only its public project URL
   in chat. Keep passwords, access/refresh tokens, database URLs and recovery
   keys in secure settings. Use a new `sb_publishable_...` public key and
   asymmetric ES256/RS256 Auth signing; admin/service-role keys and legacy
   symmetric JWT signing are rejected by this application.
2. In a trusted operator environment, install the separately hash-locked
   dependencies and run `scripts/bootstrap_production_role.py` with private
   `ADMIN_DATABASE_URL` and `VIBEFINANCE_APP_ROLE_PASSWORD` environment bindings.
   It creates only a new restricted `vibefinance_app` role and refuses an
   existing role or existing application tables. Use the resulting application
   role in the session-pooler connection string, keeping `sslmode=verify-full`.
   Never deploy the administrative database URL to the web application.
3. Prepare Render settings: `VIBEFINANCE_AUTH_MODE=supabase`,
   `VIBEFINANCE_SUPABASE_URL`, `VIBEFINANCE_SUPABASE_PUBLISHABLE_KEY`,
   `VIBEFINANCE_DATABASE_URL` and `VIBEFINANCE_PUBLIC_URL`. The actual database
   URL/password is secret. Follow [deployment](PRODUCTION_DEPLOYMENT.md) and
   [storage](PRODUCTION_STORAGE.md); run the local preflight before switching.
4. Back up any existing shared-demo state before changing the service. Import
   only profiles whose owner has explicitly been established. The application
   does not assign shared demo profiles/history to every new account.
5. Configure `deploy/Dockerfile.production` on the existing free service only
   after the candidate and settings are reviewed. The separate free-only
   Blueprint is a reviewable alternative; it has no paid database/disk and does
   not apply itself. Keep the working shared demo intact until configuration is
   ready; a code push alone does not complete this migration.
6. Confirm a real email account, create its first profile and verify analysis,
   saved history, logout, token renewal and persistence after service restart.
   Repeat with a second account using the same profile ID; neither account may
   access the other's profile, session, decision or sources. Use the protected
   checker only with operator-configured test credentials and its write flag.
   Empty accounts fail acceptance until their owner creates a profile.
7. Configure and exercise [encrypted recovery](PRODUCTION_RECOVERY.md).
   Backups contain application data, not Supabase Auth users/passwords. Retain
   the original verified issuer/subject identity or use a separately reviewed
   provider migration; never silently remap ownership by email.

Actual test evidence is in [VALIDATION.md](VALIDATION.md). The local provider
fixtures and owned PostgreSQL containers do not establish live Supabase or
protected Render acceptance. The original baseline remains eligible and
**predictive advantage remains unproven**.

## Research work after authorized data is available

Finish the complete independent review before registering a future protocol.
The [cycle runner](PROSPECTIVE_OPERATIONS.md) reports missing prerequisites and
unknown maturity without inventing a calendar or backfilling a forecast. Move
the proposed start into the future if registration occurs later; never backdate.
Keep both inspected periods spent and preserve their failed/uncertain results.
Report identical-date baseline scores, uncertainty, coverage and width only
when genuine new outcomes exist. Complexity is optional; a winning baseline
remains the selected result.
