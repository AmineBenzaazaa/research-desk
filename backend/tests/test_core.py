"""Fast tests for the deterministic parts (no model downloads, no API calls)."""
from desk.agent import run_sql
from desk.extract import Metric, check_metric
from desk.search import BM25, rrf, split_sentences, tokenize


def test_tokenize_keeps_numbers_and_percent_drops_stopwords():
    assert tokenize("What is the COD share, 64% in 2025?") == ["cod", "share", "64%", "2025"]


def test_bm25_ranks_the_rare_exact_word_first():
    bm = BM25(["charging operators in the gulf", "VoltSands runs 400 chargers", "solar panels in the desert"])
    assert bm.scores("VoltSands").argmax() == 1


def test_bm25_unknown_word_scores_zero():
    bm = BM25(["a b c", "d e f"])
    assert bm.scores("tesla").max() == 0


def test_rrf_rewards_items_ranked_well_by_both():
    assert rrf([[1, 2, 3], [3, 1, 2]])[0] == 1


def test_split_sentences_respects_size_and_overlaps():
    text = " ".join(f"Sentence number {i} is here." for i in range(40))
    chunks = split_sentences(text, max_chars=120)
    assert all(len(c) <= 150 for c in chunks)
    assert chunks[1].split(".")[0] in chunks[0]   # one sentence of overlap


def test_run_sql_blocks_writes():
    assert "error" in run_sql("DELETE FROM reports")
    assert "error" in run_sql("WITH x AS (SELECT 1) DELETE FROM reports")   # read-only connection


def test_run_sql_returns_errors_to_the_model():
    assert "no such column" in run_sql("SELECT nope FROM reports")["error"]


def test_run_sql_counts_reports():
    assert run_sql("SELECT COUNT(*) FROM reports")["rows"] == [(6,)]


def test_check_metric_catches_a_wrong_number():
    text = "GMV reached MAD 31.4 billion in 2025."
    good = Metric(name="GMV", value=31.4, unit="MAD bn", year=2025, is_forecast=False, source_quote=text)
    bad = good.model_copy(update={"value": 34.1})
    invented = good.model_copy(update={"source_quote": "GMV reached MAD 34.1 billion in 2025."})
    assert check_metric(good, text) == {"quote_in_doc": True, "value_in_quote": True}
    assert check_metric(bad, text)["value_in_quote"] is False
    assert check_metric(invented, text)["quote_in_doc"] is False
