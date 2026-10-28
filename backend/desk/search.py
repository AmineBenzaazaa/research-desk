"""Hybrid retrieval: BM25 (exact words: names, codes, numbers) + embeddings (meaning),
merged with Reciprocal Rank Fusion, then a cross-encoder reranks the top candidates.
Superseded report versions are never returned."""
import collections
import math
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from pypdf import PdfReader

from .config import DATA, DOCS, EMBED_MODEL, RERANK_MODEL
from .tracing import span

STOP = set("the a an of in to and is for on what how much many does did do will by with from at as be are was "
           "it this that which who per".split())


def tokenize(text):
    return [w for w in re.findall(r"[a-z0-9%.]+", text.lower()) if w not in STOP]


def split_sentences(text, max_chars=600, overlap_sentences=1):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], []
    for s in sentences:
        if current and len(" ".join(current + [s])) > max_chars:
            chunks.append(" ".join(current))
            current = current[-overlap_sentences:]
        current.append(s)
    if current:
        chunks.append(" ".join(current))
    return chunks


def pdf_text(path: Path) -> str:
    return " ".join(" ".join(p.extract_text() for p in PdfReader(path).pages).split())


class BM25:
    def __init__(self, texts, k1=1.5, b=0.75):
        self.docs = [tokenize(t) for t in texts]
        self.k1, self.b = k1, b
        self.avg_len = sum(map(len, self.docs)) / len(self.docs)
        df = collections.Counter(w for d in self.docs for w in set(d))
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.tfs = [collections.Counter(d) for d in self.docs]

    def scores(self, query):
        q = tokenize(query)
        out = np.zeros(len(self.docs))
        for i, (doc, tf) in enumerate(zip(self.docs, self.tfs)):
            norm = self.k1 * (1 - self.b + self.b * len(doc) / self.avg_len)
            out[i] = sum(self.idf[w] * tf[w] * (self.k1 + 1) / (tf[w] + norm) for w in q if w in tf)
        return out


def rrf(rankings, k=60):
    """Reciprocal Rank Fusion: only ranks matter, so BM25 and cosine scores never need the same scale."""
    fused = collections.defaultdict(float)
    for ranking in rankings:
        for rank, i in enumerate(ranking, start=1):
            fused[i] += 1 / (k + rank)
    return sorted(fused, key=fused.get, reverse=True)


class Index:
    def __init__(self, docs_dir=DOCS, reports_csv=DATA / "reports.csv"):
        from fastembed import TextEmbedding
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        reports = pd.read_csv(reports_csv)
        superseded = {s for s in reports.supersedes if isinstance(s, str)}
        published = dict(zip(reports.report_id, reports.published))
        self.chunks = []
        for pdf in sorted(Path(docs_dir).glob("*.pdf")):
            text = pdf_text(pdf)
            rid = re.search(r"Report ID (AR-[A-Z]+-\d+)", text).group(1)
            for piece in split_sentences(text):
                self.chunks.append({"report_id": rid, "published": published.get(rid),
                                    "is_latest": rid not in superseded, "text": piece})
        self.embedder = TextEmbedding(EMBED_MODEL)
        self.reranker = TextCrossEncoder(RERANK_MODEL)
        vecs = np.array(list(self.embedder.embed([c["text"] for c in self.chunks])))
        self.vectors = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
        self.bm25 = BM25([c["text"] for c in self.chunks])

    def _latest(self, order):
        return [int(i) for i in order if self.chunks[i]["is_latest"]]

    def dense_ranking(self, query):
        q = np.array(list(self.embedder.embed([query]))[0])
        return self._latest(np.argsort(-(self.vectors @ (q / np.linalg.norm(q)))))

    def bm25_ranking(self, query):
        return self._latest(np.argsort(-self.bm25.scores(query)))

    def search(self, query, k=3, pool=10, threshold=None):
        """Top k as [(score, chunk)]. With a threshold, refuse ([]) when even the BEST chunk scores below it:
        a per-chunk cut would drop useful neighbours (e.g. a 'Risks' section scoring lower than its title)."""
        with span("retrieve", as_type="retriever", input=query, metadata={"pool": pool}) as sp:
            candidates = rrf([self.dense_ranking(query), self.bm25_ranking(query)])[:pool]
            sp.update(output=[self.chunks[i]["report_id"] for i in candidates])
        with span("rerank", input={"query": query, "candidates": len(candidates)}, metadata={"threshold": threshold}) as sp:
            scores = self.reranker.rerank(query, [self.chunks[i]["text"] for i in candidates])
            hits = sorted(((float(s), self.chunks[i]) for s, i in zip(scores, candidates)), key=lambda h: -h[0])
            refused = threshold is not None and hits[0][0] < threshold
            sp.update(output={"top_score": round(hits[0][0], 2), "refused": refused,
                              "top": [{"report_id": c["report_id"], "score": round(s, 2)} for s, c in hits[:k]]})
        return [] if refused else hits[:k]


@lru_cache(maxsize=1)
def get_index() -> Index:
    return Index()
