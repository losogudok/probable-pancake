"""Main ingestion pipeline: scan sources, parse, chunk, extract metadata."""
from __future__ import annotations

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Iterator, Optional

from ..core.config import settings, SOURCES_DIR
from ..core.models import (
    Document, Chunk, make_doc_id, make_chunk_id,
    detect_language, detect_geography, extract_year,
    extract_title, extract_authors,
)
from ..core.ontology import SourceType, TRUST_SCORES, Geography
from .parser import parse_document
from .chunker import chunk_pages

logger = logging.getLogger(__name__)

# Category mapping from top-level directory names
CATEGORY_MAP = {
    "Статьи": ("article", SourceType.SCIENTIFIC_ARTICLE),
    "Обзоры": ("review", SourceType.REVIEW),
    "Доклады": ("report", SourceType.INTERNAL_REPORT),
    "Журналы": ("journal", SourceType.JOURNAL_ISSUE),
    "Материалы конференций": ("conference", SourceType.CONFERENCE_PAPER),
}

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".docm", ".xlsx", ".xls", ".pptx", ".txt"}


def scan_sources(sources_dir: Optional[Path] = None) -> list[Path]:
    """Scan the sources directory and return all supported files."""
    sources_dir = sources_dir or SOURCES_DIR
    if not sources_dir.exists():
        logger.error(f"Sources directory not found: {sources_dir}")
        return []

    files = []
    for root, dirs, filenames in os.walk(sources_dir):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                files.append(Path(root) / fname)
    logger.info(f"Found {len(files)} supported files in {sources_dir}")
    return sorted(files)


def classify_document(path: Path) -> tuple[str, SourceType]:
    """Classify document by its path category."""
    parts = path.parts
    for part in parts:
        if part in CATEGORY_MAP:
            return CATEGORY_MAP[part]
    # Fallback by extension
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "article", SourceType.SCIENTIFIC_ARTICLE
    return "report", SourceType.INTERNAL_REPORT


def ingest_document(path: Path) -> Optional[Document]:
    """Parse, chunk, and create a Document object with metadata.

    Args:
        path: Path to the source file.

    Returns:
        Document object with chunks, or None if parsing failed.
    """
    path = Path(path)
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return None

    # Parse
    full_text, pages = parse_document(str(path))
    if not full_text or len(full_text.strip()) < 100:
        logger.warning(f"Empty or too short text from: {path.name}")
        return None

    # Classify
    category, source_type = classify_document(path)
    doc_id = make_doc_id(str(path))

    # Extract metadata
    language = detect_language(full_text)
    geography = detect_geography(full_text, path.name)
    year = extract_year(full_text, path.name)
    title = extract_title(full_text, path.name)
    authors = extract_authors(full_text)
    trust = TRUST_SCORES.get(source_type, 1)

    # Chunk
    chunk_results = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)

    chunks = []
    for idx, (chunk_text, page_num) in enumerate(chunk_results):
        chunk = Chunk(
            id=make_chunk_id(doc_id, idx),
            doc_id=doc_id,
            text=chunk_text,
            index=idx,
            page=page_num,
        )
        chunks.append(chunk)

    doc = Document(
        id=doc_id,
        path=str(path),
        filename=path.name,
        category=category,
        source_type=source_type.value,
        title=title,
        authors=authors,
        year=year,
        language=language,
        geography=geography,
        num_pages=len(pages),
        num_chunks=len(chunks),
        text_length=len(full_text),
        imported_at=datetime.now().isoformat(),
        chunks=chunks,
        trust=trust,
        metadata={
            "size_bytes": path.stat().st_size,
            "extension": path.suffix.lower(),
        },
    )

    logger.info(
        f"Ingested: {path.name} | pages={doc.num_pages} chunks={doc.num_chunks} "
        f"lang={language} geo={geography} year={year}"
    )
    return doc


def ingest_corpus(
    sources_dir: Optional[Path] = None,
    max_docs: int = 0,
    skip_existing: bool = True,
    existing_ids: Optional[set[str]] = None,
) -> Iterator[Document]:
    """Ingest the entire corpus, yielding documents one by one.

    Args:
        sources_dir: Override sources directory.
        max_docs: Maximum number of documents to ingest (0 = all).
        skip_existing: Skip documents already ingested.
        existing_ids: Set of already-ingested document IDs.

    Yields:
        Document objects.
    """
    files = scan_sources(sources_dir)
    if max_docs > 0:
        files = files[:max_docs]

    existing_ids = existing_ids or set()
    count = 0
    failed = 0

    for path in files:
        doc_id = make_doc_id(str(path))
        if skip_existing and doc_id in existing_ids:
            continue
        doc = ingest_document(path)
        if doc is None:
            failed += 1
            continue
        count += 1
        yield doc

    logger.info(f"Ingestion complete: {count} docs ingested, {failed} failed")
