"""Retrieval quality on a labelled question set. No LLM calls, so it is free to run on every change."""
import time

from .config import RERANK_THRESHOLD
from .search import Index, get_index

RETRIEVAL_SET = [
    ("How much does WhatsApp order confirmation reduce returns?",                     "AR-MA-0412",  "WhatsApp"),
    ("How much does summer heat reduce charger output?",                             "AR-GCC-0388", "derating"),
    ("How fast did AI diagnostics grow in Saudi Arabia in 2025?",                    "AR-SA-0455",  "61%"),
    ("How much does water desalination add to the cost of hydrogen?",                "AR-NA-0420",  "desalination"),
    ("How much fintech funding did Morocco raise in the first nine months of 2026?", "AR-ME-0471",  "nine months"),
    ("What will green hydrogen cost per kg in 2030?",                                "AR-NA-0420",  "2030"),
    ("How long does delivery take in rural Morocco?",                                "AR-MA-0412",  "4.8 days"),
    ("Do Saudi data residency rules affect health vendors?",                         "AR-SA-0455",  "residency"),
    ("Who are the main EV charging operators in the GCC?",                           "AR-GCC-0388", "VoltSands"),
    ("What share of first purchases starts on social media?",                        "AR-MA-0412",  "social"),
]
VAGUE = [
    ("What does the report say about VoltSands?",      "AR-GCC-0388", "VoltSands"),
    ("Tell me about NajmCharge",                       "AR-GCC-0388", "NajmCharge"),
    ("What about DuneGrid?",                           "AR-GCC-0388", "DuneGrid"),
    ("What is BNPL adoption?",                         "AR-ME-0471",  "BNPL"),
    ("What is RTO?",                                   "AR-MA-0412",  "RTO"),
    ("What are the risks for EV charging in the GCC?", "AR-GCC-0388", "Risks"),
]
UNANSWERABLE = [
    "What is the population of Japan?",
    "What will the Bitcoin price be next year?",
    "How many EVs did Tesla deliver in Q3?",
    "How many EVs did Tesla deliver in Q3 2026?",
    "What is the best football team in Spain?",
    "What is the GDP of Brazil?",
    "How many Uber rides happen in Riyadh per day?",
]
GATE = {"hit_rate": 1.0, "unanswerable_rejected": 1.0, "answerable_recall": 0.9}   # minimums to ship a change


def rank_of(hits, report_id, phrase):
    return next((r for r, (_, c) in enumerate(hits, 1) if c["report_id"] == report_id and phrase in c["text"]), None)


def run(index: Index | None = None, threshold=RERANK_THRESHOLD) -> dict:
    index = index or get_index()
    rows, t0 = [], time.perf_counter()
    for kind, cases in [("answerable", RETRIEVAL_SET), ("vague", VAGUE)]:
        for q, rid, phrase in cases:
            hits = index.search(q, k=3)
            rows.append({"kind": kind, "question": q, "expected": rid, "rank": rank_of(hits, rid, phrase),
                         "top_score": round(hits[0][0], 2), "answered": hits[0][0] >= threshold})
    for q in UNANSWERABLE:
        top = index.search(q, k=1)[0][0]
        rows.append({"kind": "unanswerable", "question": q, "expected": None, "rank": None,
                     "top_score": round(top, 2), "answered": top >= threshold})
    ms = (time.perf_counter() - t0) / len(rows) * 1000

    def of(kind):
        return [r for r in rows if r["kind"] == kind]

    ans, vague, una = of("answerable"), of("vague"), of("unanswerable")
    summary = {
        "hit_rate": sum(r["rank"] is not None for r in ans) / len(ans),
        "mrr": sum(1 / r["rank"] for r in ans if r["rank"]) / len(ans),
        "answerable_recall": sum(r["rank"] is not None and r["answered"] for r in ans) / len(ans),
        "unanswerable_rejected": sum(not r["answered"] for r in una) / len(una),
        "vague_hit_rate": sum(r["rank"] is not None for r in vague) / len(vague),
        "ms_per_query": round(ms),
    }
    gate = {k: {"min": v, "value": summary[k], "ok": summary[k] >= v} for k, v in GATE.items()}
    return {"summary": summary, "gate": gate, "passed": all(g["ok"] for g in gate.values()),
            "threshold": threshold, "rows": rows}


if __name__ == "__main__":
    import json
    import sys

    result = run()
    if "--report" in sys.argv:   # full result (summary, gate, per-question rows) for CI artifacts
        with open(sys.argv[sys.argv.index("--report") + 1], "w") as f:
            json.dump(result, f, indent=2)
    print(json.dumps(result["summary"], indent=2))
    print("GATE:", "PASS" if result["passed"] else "FAIL")
    sys.exit(0 if result["passed"] else 1)   # usable as a CI check
