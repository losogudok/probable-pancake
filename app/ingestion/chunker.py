"""Text chunking with overlap for RAG."""
from __future__ import annotations

import re
from typing import Optional


def chunk_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[tuple[str, Optional[int]]]:
    """Split text into overlapping chunks.

    Tries to break on sentence/paragraph boundaries.
    Returns list of (chunk_text, page_number) — page is None since we
    operate on full text. Page-level chunking is done in the pipeline.

    Args:
        text: Full document text.
        chunk_size: Target chunk size in characters.
        overlap: Overlap between consecutive chunks.

    Returns:
        List of (chunk_text, None) tuples.
    """
    if not text or not text.strip():
        return []

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        if end >= text_len:
            chunk = text[start:]
            if len(chunk.strip()) > 50:
                chunks.append((chunk, None))
            break

        # Try to find a sentence boundary near the end
        # Look for period followed by space/newline in last 200 chars
        boundary = -1
        for pattern in [r'[.!?]\s+', r'\n\n', r'\n']:
            matches = list(re.finditer(pattern, text[end - 200:end + 50]))
            if matches:
                boundary = end - 200 + matches[-1].end()
                break

        if boundary > start + 100:
            end = boundary

        chunk = text[start:end].strip()
        if len(chunk) > 50:
            chunks.append((chunk, None))

        start = end - overlap
        if start <= 0:
            start = end

    return chunks


def chunk_pages(
    pages: list[str],
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[tuple[str, Optional[int]]]:
    """Chunk text with page attribution.

    For paginated documents (PDF), chunks preserve page numbers.
    For non-paginated, page is None.

    Args:
        pages: List of per-page text. If single element, treated as non-paginated.
        chunk_size: Target chunk size in characters.
        overlap: Overlap between chunks.

    Returns:
        List of (chunk_text, page_number) tuples.
    """
    if len(pages) == 1:
        return chunk_text(pages[0], chunk_size, overlap)

    results = []
    for page_num, page_text in enumerate(pages, 1):
        page_chunks = chunk_text(page_text, chunk_size, overlap)
        for chunk_text_str, _ in page_chunks:
            results.append((chunk_text_str, page_num))
    return results
