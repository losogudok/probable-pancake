"""Tests for the Scientific Knowledge Graph core components."""

from app.core.ontology import (
    EntityType, RelationType, SourceType, Geography,
    TRUST_SCORES, SYNONYMS, trust_stars, normalize_term
)
from app.core.models import (
    Document, Chunk, detect_language, detect_geography,
    extract_year, extract_title, make_chunk_id, make_doc_id
)


def test_entity_types():
    assert EntityType.MATERIAL.value == "Material"
    assert len(EntityType) >= 10


def test_relation_types():
    assert RelationType.USES_MATERIAL.value == "uses_material"
    assert len(RelationType) >= 10


def test_trust_scores():
    assert TRUST_SCORES[SourceType.SCIENTIFIC_ARTICLE] == 5
    assert TRUST_SCORES[SourceType.UNVERIFIED] == 1


def test_trust_stars():
    assert trust_stars(5) == "★★★★★"
    assert trust_stars(3) == "★★★☆☆"


def test_geography():
    assert Geography.RUSSIA.value == "Russia"


def test_synonyms():
    assert "никель" in SYNONYMS
    assert "nickel" in SYNONYMS["никель"]


def test_normalize_term():
    assert normalize_term("  Никель ") == "никель"


def test_document_creation():
    doc_id = make_doc_id("/path/to/test.pdf")
    doc = Document(
        id=doc_id,
        path="/path/to/test.pdf",
        filename="test.pdf",
        category="articles",
        source_type="scientific_article",
        title="Test Title",
        year=2024, trust=5
    )
    assert doc.id == doc_id
    assert doc.category == "articles"


def test_chunk():
    chunk = Chunk(
        id="doc1_0000", doc_id="doc1",
        text="Test", index=0, page=1
    )
    assert chunk.id == "doc1_0000"


def test_language_detection():
    assert detect_language("Это русский текст") == "ru"
    assert detect_language("This is English text") == "en"


def test_geography_detection():
    geo = detect_geography("Норникель и Российская академия наук", "file.pdf")
    assert geo == "Russia"


def test_year():
    assert extract_year("опубликовано в 2023 году", "file.pdf") == 2023
    assert extract_year("текст", "file.pdf") is None


def test_title():
    title = extract_title("НАЗВАНИЕ СТАТЬИ\nАннотация...", "file.pdf")
    assert title is not None


def test_serialization():
    doc = Document(
        id="test123", path="/p.pdf", filename="p.pdf",
        category="articles", source_type="scientific_article"
    )
    data = doc.to_dict()
    assert data["id"] == "test123"
