# Authentic text ingestion and retrieval acceptance

The default 21-document synthetic corpus remains unchanged. Authentic sources
are a separate, explicit corpus. The new importer handles multiple permitted
UTF-8 source documents, original hashes, exact spans, security identity and
actual availability timestamps. **No authentic investment corpus or held-out
relevance score is claimed from the format fixtures used in tests.**

## Reproducible import

Place authorized, unmodified UTF-8 source text and a manifest in a private local
directory. Use schema version 1, kind `permitted_authentic_text_corpus`, and a
`sources` array. Each source must have:

| Field | Meaning |
|---|---|
| `source_id`, `ticker`, `doc_type`, `title`, `publisher` | Unique safe ID, one of the five existing securities, results/transcript/risk/disclosure/news/reference and real source identity |
| `path`, `sha256` | Local source-text path confined to the manifest directory and actual SHA-256 |
| `source_url` | Exact HTTPS source location, without embedded credentials |
| `security_identity_evidence` | Real reference supporting the security/document mapping |
| `published_at`, `retrieved_at` | Actual timezone-aware timestamps, not the fiscal period described |
| `timestamp_evidence` | Retained evidence supporting those timestamps |
| `available_at`, `availability_evidence` | Optional actual first-availability timestamp and evidence; otherwise conservatively use retrieval time |
| `rights` | `permission` (`explicit_license`, `written_permission`, or `public_domain`), `identifier`, HTTPS `evidence_url`, and `use: noncommercial_research` |

Public accessibility is not a license. A permission declaration is an operator
attestation; the importer does not certify its authenticity or grant new rights.
Publication <= availability <= retrieval <= current time is enforced. Future or
unqualified date-only timestamps fail. A source can describe 2020 and first become
available in 2026; it must not enter a 2020 backtest. PDF extraction must be
separately reviewed against the original artifact; this command imports text
rather than silently asserting a correct PDF/OCR conversion.

```bash
.venv/bin/python scripts/ingest_authentic.py \
  --manifest /authorized-text/manifest.json --output-dir .runtime/authentic-corpus-v1
VIBEFINANCE_CORPUS_PATH="$PWD/.runtime/authentic-corpus-v1" \
  VIBEFINANCE_EMBEDDINGS=0 .venv/bin/python -m vibefinance.demo
```

`/authorized-text/manifest.json` is a placeholder for actual supplied evidence,
not a file that exists in this checkout. All inputs validate before output is
created; existing output directories are refused. A write interruption can leave
an incomplete output, which must be preserved and inspected. Original body
bytes, including CRLF and repeated whitespace, survive; chunk offsets are Unicode
character spans into the original decoded text. Imported artifact and manifest
hashes are in `import.json`. No synthetic default document is replaced.

Retrieval accepts a timezone-aware ISO cutoff or datetime. A date-only cutoff
conservatively means midnight UTC for authentic documents; intraday publications
are withheld until a precise cutoff or subsequent date. Synthetic date behavior
stays compatible. BM25 and Chroma enforce ticker/type/date filters; source-kind
and timestamp filters are also applied to vector candidates and independently
checked before returning results. Persistent collection identity includes source
kind, original hash, URL and full availability timestamp to avoid stale metadata.
Sentiment checks availability again before making claims.

Citations/session source snapshots add source kind, original URL/hash, publication
and availability timestamps, and exact spans. The validator rejects forged
provenance fields. The HTML source view distinguishes authentic/operator-supplied,
synthetic and computed inputs, shows provenance, and uses exact offsets for
highlighting. Existing fields and portfolio policy rules remain compatible.
Finite quotation/template checks establish their stated support, not arbitrary
semantic entailment or source truth.

## Optional local neural retrieval

A new separate Linux CPU lock freezes all 120 packages with artifact hashes,
including torch 2.7.1+cpu, Chroma 1.0.20 and sentence-transformers 5.1.0. Core,
authentication and database locks remain unchanged. This optional environment is
not required by the demo or the numpy forecasting development:

```bash
UV_PYTHON_INSTALL_DIR="$PWD/.runtime/python" uv venv --python 3.11 .runtime/embeddings-venv
UV_CACHE_DIR="$PWD/.runtime/uv-cache" uv pip sync \
  --python .runtime/embeddings-venv/bin/python --index-strategy unsafe-best-match \
  --require-hashes requirements-embeddings-cpu.lock
HF_HOME="$PWD/.runtime/huggingface" .runtime/embeddings-venv/bin/python \
  scripts/check_embeddings.py --download --output .runtime/neural-check-NEW.json
```

The lock includes the official CPU wheel index; installation retains hash and TLS
verification. `unsafe-best-match` is uv's index-selection name, not a verification
bypass: exact versions and required artifact hashes remain enforced. Use the
optional Linux lock on its declared platform; no new cross-platform neural-package
acceptance is claimed.

The package installation and compatibility check passed. A real Chroma persisted
store/query with explicitly labelled fixture vectors passed. **Real MiniLM
inference did not run**: the runtime blocks huggingface.co, and no local weights
exist. The local-only check returned exit 2, real_model_verified false, and an
explicit BM25 fallback. [Observed evidence](assets/retrieval-development-v2.json)
records the distinction. Required Hugging Face domains were saved to the cloud
configuration draft; a saved draft does not apply runtime access. Do not use
randomly initialized weights, another revision or fixture vectors as a success.

## Held-out ranking and citation acceptance

Prepare an independently judged, predeclared question array with `id`,
`split: held_out`, `query`, `ticker`, precise `as_of`, optional `doc_types`,
`judged_by`, `judgment_evidence`, and `relevance_by_source_id` (grades 0/1/2).
Do not develop model/query settings using this question set. Keep a separate
development set. Include all returned documents in the judgment pool; unjudged
results make aggregate scores unavailable rather than silently counting them as
irrelevant. The checker does not invent questions, relevance judgments or reviewers.

```bash
.runtime/embeddings-venv/bin/python scripts/evaluate_retrieval.py \
  --corpus .runtime/authentic-corpus-v1 --questions /authorized-text/held-out.json \
  --require-vectors --output .runtime/retrieval-acceptance-NEW.json
```

This reports source-level nDCG/recall under a fixed four-chunk retrieval budget,
question/hash identity, exact-span integrity, missing judgments and actual mode.
`--require-vectors` fails when BM25 fallback is active. Repeated source IDs in
returned chunks are deduplicated for ranking. Span integrity is separate from
human semantic claim-support judgments and cannot establish truthful financial
interpretation. No real-source ranking/semantic-support benchmark has run here:
permitted source documents, genuine held-out judgments and model access remain
external prerequisites. Synthetic format fixtures test implementation only.
