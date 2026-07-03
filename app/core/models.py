"""Document and chunk data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib
import re


@dataclass
class Chunk:
    """A text chunk extracted from a document, used for search and RAG."""
    id: str
    doc_id: str
    text: str
    index: int
    page: Optional[int] = None
    embedding: Optional[list[float]] = None
    entities: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "doc_id": self.doc_id,
            "text": self.text,
            "index": self.index,
            "page": self.page,
            "entities": self.entities,
        }
        return d


@dataclass
class Document:
    """A source document in the corpus."""
    id: str
    path: str
    filename: str
    category: str  # article, review, report, journal, conference, patent
    source_type: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    language: str = "ru"
    geography: str = "Unknown"
    num_pages: int = 0
    num_chunks: int = 0
    text_length: int = 0
    imported_at: str = ""
    chunks: list[Chunk] = field(default_factory=list)
    trust: int = 1
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "path": self.path,
            "filename": self.filename,
            "category": self.category,
            "source_type": self.source_type,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "language": self.language,
            "geography": self.geography,
            "num_pages": self.num_pages,
            "num_chunks": self.num_chunks,
            "text_length": self.text_length,
            "imported_at": self.imported_at,
            "trust": self.trust,
            "metadata": self.metadata,
        }


def make_doc_id(path: str) -> str:
    """Stable ID from file path."""
    return hashlib.md5(path.encode()).hexdigest()[:16]


def make_chunk_id(doc_id: str, index: int) -> str:
    return f"{doc_id}_{index:04d}"


def detect_language(text: str) -> str:
    """Simple language detection: count Cyrillic vs Latin chars."""
    cyrillic = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    if cyrillic > latin * 0.5:
        return "ru"
    return "en"


def detect_geography(text: str, filename: str) -> str:
    """Heuristic geography detection from text and filename."""
    text_lower = (text + " " + filename).lower()
    russia_markers = ["росс", "russia", "норильск", "норникель", "nornickel",
                      "жкз", "комсомольский", "надежда", "заполярный", "талнах",
                      "рудник", "шахта", "цвметмет", "цветные металлы"]
    foreign_markers = ["australia", "австралия", "canada", "канада", "chile",
                       "чили", "new caledonia", "новая каледония", "finland",
                       "финляндия", "china", "китай", "japan", "япония",
                       "usa", "сша", "zambia", "замби", "congo", "конго"]

    russia_hits = sum(1 for m in russia_markers if m in text_lower)
    foreign_hits = sum(1 for m in foreign_markers if m in text_lower)

    if russia_hits > 0 and foreign_hits > 0:
        return "Global"
    if russia_hits > 0:
        return "Russia"
    if foreign_hits > 0:
        return "Foreign"
    return "Unknown"


def extract_year(text: str, filename: str) -> Optional[int]:
    """Extract publication year from text or filename."""
    # Look in filename first
    for m in re.finditer(r"(20[0-2]\d|19[8-9]\d)", filename):
        y = int(m.group(1))
        if 1980 <= y <= 2030:
            return y
    # Then in first 2000 chars of text
    for m in re.finditer(r"(20[0-2]\d|19[8-9]\d)", text[:3000]):
        y = int(m.group(1))
        if 1980 <= y <= 2030:
            return y
    return None


def extract_title(text: str, filename: str) -> str:
    """Extract a best-guess title from document text."""
    lines = [l.strip() for l in text[:2000].split("\n") if l.strip()]
    # Skip common headers
    skip_prefixes = ("www.", "http", "issn", "doi", "удк", "ббк", "©",
                     "издается", "ежемесячный", "научно-технический")
    for line in lines[:15]:
        if len(line) > 15 and not line.lower().startswith(skip_prefixes):
            # Clean up
            title = line[:200]
            return title
    # Fallback: filename without extension
    import os
    return os.path.splitext(filename)[0][:200]


def extract_authors(text: str) -> list[str]:
    """Extract author names from the beginning of document text."""
    authors = []
    lines = [l.strip() for l in text[:1500].split("\n") if l.strip()]
    for line in lines[:5]:
        # Pattern: "Иванов И.И., Петров П.П." or "A.B. Smith, C.D. Jones"
        # Cyrillic initials pattern
        cyr = re.findall(
            r"[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ]\.?(?:\s*[А-ЯЁ]\.?)?)", line)
        if cyr and len(line) < 300:
            authors.extend(cyr[:10])
        # Latin initials pattern
        lat = re.findall(
            r"[A-Z][a-z]+(?:\s+[A-Z]\.?(?:\s*[A-Z]\.?)?)", line)
        if lat and len(line) < 300:
            authors.extend(lat[:10])
        if authors:
            break
    return authors[:10]
