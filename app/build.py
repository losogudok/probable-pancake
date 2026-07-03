"""Build pipeline: ingest documents, extract entities, build KG and search index.

Usage:
    python -m app.build                    # full build
    python -m app.build --max-docs 50      # limited build for testing
    python -m app.build --use-llm          # also use LLM extraction
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from .core.config import settings, GRAPH_PATH, INDEX_PATH, DOCS_DB_PATH
from .ingestion.pipeline import ingest_corpus
from .nlp.extractor import extract_from_chunk
from .nlp.llm_client import get_llm
from .graph.kg import KnowledgeGraph
from .search.hybrid import HybridSearch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def build(
    max_docs: int = 0,
    use_llm: bool = False,
    llm_sample_rate: int = 5,
) -> None:
    """Run the full build pipeline.

    Args:
        max_docs: Maximum documents to process (0 = all).
        use_llm: Whether to use LLM for entity extraction.
        llm_sample_rate: If use_llm, use LLM on every Nth chunk (to control cost).
    """
    start_time = time.time()

    # Initialize components
    kg = KnowledgeGraph()
    search = HybridSearch()
    llm = get_llm() if use_llm else None

    # Try to load existing data for incremental builds
    existing_ids: set[str] = set()
    if DOCS_DB_PATH.exists():
        search.load()
        existing_ids = set(search.documents.keys())
        logger.info(f"Found {len(existing_ids)} existing documents for incremental update")

    if GRAPH_PATH.exists():
        kg.load()

    # Ingest documents
    doc_count = 0
    chunk_count = 0
    entity_count = 0

    for doc in ingest_corpus(max_docs=max_docs, skip_existing=True, existing_ids=existing_ids):
        doc_count += 1

        # Add to search index
        search.add_document(doc)

        # Add document to knowledge graph
        kg.add_document(doc)

        # Extract entities from chunks
        for i, chunk in enumerate(doc.chunks):
            use_llm_for_chunk = use_llm and (i % llm_sample_rate == 0)
            extraction = extract_from_chunk(
                chunk.text, doc.id,
                use_llm=use_llm_for_chunk,
                llm_client=llm,
            )
            chunk.entities = extraction.get("entities", [])
            entity_count += len(chunk.entities)

            # Add to knowledge graph
            kg.add_extraction(doc, chunk, extraction)

            chunk_count += 1

        if doc_count % 10 == 0:
            elapsed = time.time() - start_time
            logger.info(
                f"Progress: {doc_count} docs, {chunk_count} chunks, "
                f"{entity_count} entities, {elapsed:.1f}s elapsed"
            )

    # Build search index
    search.build()

    # Save everything
    kg.save()
    search.save()

    elapsed = time.time() - start_time
    stats = kg.get_stats()
    logger.info(f"=== Build complete in {elapsed:.1f}s ===")
    logger.info(f"Documents: {doc_count}")
    logger.info(f"Chunks: {chunk_count}")
    logger.info(f"Entities extracted: {entity_count}")
    logger.info(f"Graph nodes: {stats['total_nodes']}")
    logger.info(f"Graph edges: {stats['total_edges']}")
    logger.info(f"Nodes by type: {stats['nodes_by_type']}")


def main():
    parser = argparse.ArgumentParser(description="Build the Scientific Knowledge Graph")
    parser.add_argument("--max-docs", type=int, default=0,
                        help="Maximum documents to process (0 = all)")
    parser.add_argument("--use-llm", action="store_true",
                        help="Use LLM for entity extraction (slower but more accurate)")
    parser.add_argument("--llm-sample-rate", type=int, default=5,
                        help="Use LLM on every Nth chunk (default: 5)")
    args = parser.parse_args()

    build(
        max_docs=args.max_docs,
        use_llm=args.use_llm,
        llm_sample_rate=args.llm_sample_rate,
    )


if __name__ == "__main__":
    main()
