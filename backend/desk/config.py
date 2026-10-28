from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = DATA / "docs"
CACHE = DATA / "cache"

load_dotenv(ROOT / ".env")

MODEL = "gemini-3.5-flash-lite"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
RERANK_THRESHOLD = 0.0   # answer or refuse, decided on the BEST reranker score only
REFUSAL = "I couldn't find this in the available reports."
