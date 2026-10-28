# Research Desk

![CI](https://github.com/AmineBenzaazaa/research-desk/actions/workflows/ci.yml/badge.svg)

Ask questions over market-research PDFs: a small Gemini tool-calling agent (`run_sql` + `search_reports`),
hybrid search (BM25 + embeddings + RRF + cross-encoder rerank), and validated PDF extraction.

```bash
cd backend && .venv/bin/python -m uvicorn api:app --port 8000   # API
cd frontend && npm run dev                                       # UI on :5173
cd backend && .venv/bin/python -m pytest -q                      # fast tests
cd backend && .venv/bin/python -m desk.evals                     # retrieval quality gate (no LLM calls)
```

## Quality gate in CI

Every push and pull request runs `.github/workflows/ci.yml`:

- **backend**: `pip install -r backend/requirements.txt`, `pytest`, then `python -m desk.evals` — the retrieval
  eval over a labelled set (answerable, vague and unanswerable questions). It makes no LLM calls and needs no secrets.
  The job fails if the gate fails (`hit_rate` = 1.0, `unanswerable_rejected` = 1.0, `answerable_recall` >= 0.9; see `GATE` in
  `backend/desk/evals.py`). Hit rate, MRR and refusal metrics are written to the run summary, and the full
  per-question report (`eval-report.json`) is uploaded as an artifact. Embedding/reranker models (ONNX via fastembed,
  no torch) are cached between runs.
- **frontend**: `npm ci`, `npm run lint`, `npm run build` (typecheck + Vite build).

Run the same gate locally with `cd backend && .venv/bin/python -m desk.evals --report eval-report.json`.
Secrets go in `backend/.env` (template: `backend/.env.example`), which is git-ignored.

## Observability (Langfuse)

Tracing is off unless `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set in `backend/.env`
(plus `LANGFUSE_BASE_URL`, e.g. `https://cloud.langfuse.com`). Without keys it is a no-op: no network, no warnings.
Code: `backend/desk/tracing.py` (Langfuse Python SDK v5, OpenTelemetry-based; `pip install langfuse`).

Every `ask()` is one trace named `ask`, tagged with the environment (`local` by default,
override with `LANGFUSE_TRACING_ENVIRONMENT`):

```
ask (agent)              input: question · output: answer · metadata: refused, cited, llm_calls, cached_calls, ms
├─ gemini (generation)   model, messages, tool calls or text, token usage · metadata.cached=true on disk-cache hits
├─ search_reports (tool) args · output: passages, top_score, report_ids
│  ├─ retrieve           BM25 + embeddings + RRF candidates
│  └─ rerank             top scores, threshold, refused
├─ run_sql (tool)        sql · output: rows, columns (or the error)
└─ gemini (generation)   final answer
```

Cache hits carry no usage (they cost nothing); their original token counts are in `metadata.cached_usage`.
Each `extract()` (PDF upload) is its own `extract` trace: input size + preview, the extracted report,
`cached`, `injection_flagged`, and a nested `gemini` generation when the model was actually called.
Evals and other direct calls to search are not traced. The API flushes on shutdown; `ask()` returns `trace_id`.

Seed the dashboard with ~20 varied questions (answerable, vague, unanswerable, prompt injection, superseded report)
and a simulated `user_feedback` score (1/0) on some of them:

```bash
cd backend && .venv/bin/python scripts/seed_traces.py
```

It reuses the LLM disk cache (repeat runs cost no Gemini quota), stops cleanly on a daily-quota error,
and exits with a message if the Langfuse keys are missing.
