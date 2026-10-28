from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from desk import evals
from desk.agent import ask, metrics, reports
from desk.config import DOCS
from desk.extract import check_metric, extract, read_pdf
from desk.llm import QuotaExceeded
from desk.search import get_index
from desk.tracing import flush


@asynccontextmanager
async def lifespan(app):
    get_index()   # load embedder + reranker once, not on the first question
    yield
    flush()   # send buffered Langfuse spans before exit


app = FastAPI(title="Research Desk", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
MAX_PDF_BYTES = 10 * 1024 * 1024


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@app.get("/api/reports")
def list_reports():
    rows = reports.fillna("").to_dict(orient="records")
    files = {p.name: p.name for p in DOCS.glob("*.pdf")}
    return {"reports": rows, "files": sorted(files), "metric_rows": len(metrics)}


@app.post("/api/ask")
def ask_endpoint(body: Question):
    try:
        return ask(body.question)
    except QuotaExceeded as e:
        raise HTTPException(429, str(e))


def extraction_response(data: bytes):
    text = read_pdf(data)
    if len(text.strip()) < 200:
        raise HTTPException(422, "No text found in this PDF (scanned image? it would need OCR first).")
    try:
        result, cached = extract(text)
    except QuotaExceeded as e:
        raise HTTPException(429, str(e))
    rows = [{**m.model_dump(), **check_metric(m, text)} for m in result.headline_metrics]
    return {"report": result.model_dump(exclude={"headline_metrics"}), "metrics": rows, "cached": cached,
            "checks_passed": sum(r["quote_in_doc"] and r["value_in_quote"] for r in rows), "checks_total": len(rows)}


@app.post("/api/extract")
async def extract_upload(file: UploadFile = File(...)):
    data = await file.read()
    if not data.startswith(b"%PDF") or len(data) > MAX_PDF_BYTES:
        raise HTTPException(400, "Please upload a PDF under 10 MB.")
    return extraction_response(data)


@app.post("/api/extract/sample/{name}")
def extract_sample(name: str):
    path = DOCS / name
    if path.parent != DOCS or not path.exists():   # no path traversal
        raise HTTPException(404, "Unknown report")
    return extraction_response(path.read_bytes())


@lru_cache(maxsize=1)
def quality_cached():
    return evals.run()


@app.get("/api/quality")
def quality(refresh: bool = False):
    if refresh:
        quality_cached.cache_clear()
    return quality_cached()
