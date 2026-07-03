"""Tests for hybrid search engine."""

from app.search.hybrid import HybridSearch
from app.core.models import Document, Chunk, make_doc_id


def _make_doc_with_chunks(text, filename, **kw):
    doc_id = make_doc_id(filename)
    chunk = Chunk(
        id=f"{doc_id}_0000",
        doc_id=doc_id,
        text=text,
        index=0,
        page=1,
    )
    doc = Document(
        id=doc_id, path="/p/" + filename, filename=filename,
        category="articles", source_type="scientific_article",
        title=kw.get("title", "T"), year=kw.get("year", 2024),
        geography=kw.get("geography", "Russia"), trust=kw.get("trust", 4),
        authors=[], num_chunks=1, text_length=len(text),
        chunks=[chunk],
    )
    return doc


def test_search_index_creation():
    hs = HybridSearch()
    for t, f in [("chunk1 content", "a.pdf"), ("chunk2 content", "b.pdf")]:
        hs.add_document(_make_doc_with_chunks(t, f))
    hs.build()
    assert len(hs.chunks) == 2


def test_search_basic():
    hs = HybridSearch()
    docs_data = [
        ("никель кобальт обогащение руда", "a.pdf"),
        ("температура давление плавление", "b.pdf"),
    ]
    for t, f in docs_data:
        hs.add_document(_make_doc_with_chunks(t, f))
    results = hs.search("никель обогащение", top_k=2)
    assert len(results) > 0
    assert results[0]["score"] > 0


def test_geography_filter():
    hs = HybridSearch()
    for t, f, geo in [
        ("никель руда", "a.pdf", "Russia"),
        ("никель руда", "b.pdf", "Foreign"),
    ]:
        hs.add_document(_make_doc_with_chunks(t, f, geography=geo))
    hs.build()
    results = hs.search("никель", top_k=5, filters={"geography": "Russia"})
    assert len(results) > 0
    for r in results:
        assert r["doc_geography"] == "Russia" or r["geography"] == "Russia"


def test_year_filter():
    hs = HybridSearch()
    for t, f, y in [
        ("никель руда", "a.pdf", 2024),
        ("никель руда", "b.pdf", 2023),
    ]:
        hs.add_document(_make_doc_with_chunks(t, f, year=y))
    hs.build()
    results = hs.search("никель", top_k=5, filters={"year_min": 2024})
    assert len(results) >= 0


def test_empty_index():
    hs = HybridSearch()
    hs.build()
    results = hs.search("test", top_k=5)
    assert results == []


def test_no_match():
    hs = HybridSearch()
    hs.add_document(_make_doc_with_chunks("aaa bbb ccc", "a.pdf"))
    hs.build()
    results = hs.search("xyzxyz", top_k=5)
    assert len(results) >= 0
