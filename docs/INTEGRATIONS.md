# Optional integrations and observed blockers

Core operation uses no external model, live feed or LLM. Its hash-pinned lock is
separate from optional dependencies. The optional packages below were installed in
isolated Linux/Python 3.11 environments; these commands are not a claim of tested
native macOS integration.

## Local embeddings

```sh
UV_CACHE_DIR="$PWD/.runtime/uv-cache" uv venv .runtime/embeddings-venv --python .venv/bin/python
UV_CACHE_DIR="$PWD/.runtime/uv-cache" uv pip install --python .runtime/embeddings-venv/bin/python --index-url https://download.pytorch.org/whl/cpu 'torch==2.7.1+cpu'
UV_CACHE_DIR="$PWD/.runtime/uv-cache" uv pip install --python .runtime/embeddings-venv/bin/python --index-url https://pypi.org/simple -r requirements-embeddings.txt
UV_CACHE_DIR="$PWD/.runtime/uv-cache" uv pip install --python .runtime/embeddings-venv/bin/python --require-hashes -r requirements.lock
HF_HOME="$PWD/.runtime/huggingface" .runtime/embeddings-venv/bin/python scripts/check_embeddings.py
```

The model check exits 2 when real MiniLM retrieval cannot be established. That is
the observed result in this workspace: Hugging Face returned HTTPS CONNECT 403,
including an out-of-sandbox read-only check. No weights were obtained and no TLS
verification was bypassed. Chroma was exercised separately with labeled fixture
vectors; this does not count as neural-model success.

The environment draft adds huggingface.co to its required domains. Saving that
draft does not apply network changes. Review/save the settings and publish through
the product; when runtime access changes, retry the pinned download:

```sh
HF_HOME="$PWD/.runtime/huggingface" .runtime/embeddings-venv/bin/python scripts/check_embeddings.py --download
HF_HOME="$PWD/.runtime/huggingface" VIBEFINANCE_EMBEDDINGS=1 make demo PYTHON=.runtime/embeddings-venv/bin/python
```

The integration script pins MiniLM revision
c9745ed1d9f207416be6d2e6f8de32d1f16199bf and checks real hybrid queries, ticker/type
filters, availability-date cutoffs and persistent reopen. Inspect redirected model
hosts only after the first request succeeds; do not guess an unlimited allowlist.
The application itself loads models locally only and falls back transparently.
Never run core-only `uv pip sync` against an optional environment you want to retain.

## Yahoo market prices

```sh
UV_CACHE_DIR="$PWD/.runtime/uv-cache" uv venv .runtime/live-venv --python .venv/bin/python
UV_CACHE_DIR="$PWD/.runtime/uv-cache" uv pip install --python .runtime/live-venv/bin/python -r requirements-live.txt
.runtime/live-venv/bin/python scripts/check_live.py --require-live
```

Observed: fc.yahoo.com returned CONNECT 403; the strict live check exited 1.
The seeded 300-row fallback passed market validation. The draft records fc.yahoo.com,
query1.finance.yahoo.com and query2.finance.yahoo.com as required Yahoo destinations.
Only fc.yahoo.com denial was observed; the query hosts were not reached in that run.
Additional consent/redirect hosts may need diagnosis after access is restored.
Network availability or provider rate limits are not repaired by inventing credentials.

The dashboard can try live prices, exposes the actual data mode, and uses the same
session rows for its chart and recommendation. All filings remain fictional.

## Hosting

The user confirmed no current hosting account. No provider, public URL or external
service was provisioned. The Docker deployment and shared access gate were tested
locally. Use docs/DEPLOYMENT.md once a host and persistent disk are available.

Shared access is a demo password, not per-user security. LLM narration, brokerage
execution, real filings and production regulatory/privacy controls are unimplemented.
