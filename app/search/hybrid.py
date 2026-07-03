"""Hybrid search engine: BM25 + dense vector embeddings + graph traversal.

Combines sparse (BM25) and dense (rubert-tiny2) retrieval with graph-based
filtering for multi-hop queries.
"""
from __future__ import annotations

import json
import logging
import re
import math
import threading
from pathlib import Path
from typing import Optional
from collections import defaultdict

import numpy as np

from ..core.config import settings, INDEX_PATH, DOCS_DB_PATH
from ..core.models import Document, Chunk, make_chunk_id
from ..core.ontology import normalize_term, MATERIAL_KEYWORDS, PROCESS_KEYWORDS

logger = logging.getLogger(__name__)


def _timed_call(fn, timeout: float, *args, **kwargs):
    """Run fn in a thread with a timeout; if it exceeds, raise TimeoutError.
    Used to avoid long hangs when loading models or network calls."""
    result_holder = []
    error_holder = []

    def _target():
        try:
            result_holder.append(fn(*args, **kwargs))
        except Exception as e:
            error_holder.append(e)

    t = threading.Thread(target=_target)
    t.daemon = True
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        raise TimeoutError(f"Operation timed out after {timeout}s")
    if error_holder:
        raise error_holder[0]
    if result_holder:
        return result_holder[0]
    # If we get here with no result and no error, treat as failure
    raise RuntimeError("Operation finished abnormally")


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """Simple tokenizer for Russian + English text."""
    text = text.lower()
    # Split on non-alphanumeric (keeps Cyrillic and Latin)
    tokens = re.findall(r"[а-яёa-z0-9]+", text)
    return [t for t in tokens if len(t) > 1]


# ---------------------------------------------------------------------------
# BM25 Index
# ---------------------------------------------------------------------------

class BM25Index:
    """Simple in-memory BM25 index."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_ids: list[str] = []
        self.doc_tokens: list[list[str]] = []
        self.doc_len: list[int] = []
        self.avg_len: float = 0.0
        self.term_freqs: list[dict[str, int]] = []
        self.idf: dict[str, float] = {}
        self.inverted: dict[str, list[int]] = defaultdict(list)

    def add(self, doc_id: str, text: str) -> None:
        """Add a document to the index."""
        tokens = tokenize(text)
        idx = len(self.doc_ids)
        self.doc_ids.append(doc_id)
        self.doc_tokens.append(tokens)
        self.doc_len.append(len(tokens))

        tf: dict[str, int] = defaultdict(int)
        for t in tokens:
            tf[t] += 1
        self.term_freqs.append(dict(tf))

        for term in tf:
            self.inverted[term].append(idx)

    def build(self) -> None:
        """Compute IDF and average document length."""
        N = len(self.doc_ids)
        self.avg_len = sum(self.doc_len) / max(N, 1)

        self.idf = {}
        for term, doc_list in self.inverted.items():
            df = len(doc_list)
            self.idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1)

    def search(self, query: str, top_k: int = 15) -> list[tuple[str, float]]:
        """Search and return (doc_id, score) pairs."""
        if not self.doc_ids or not self.idf:
            return []

        query_tokens = tokenize(query)
        scores: dict[int, float] = defaultdict(float)

        for term in query_tokens:
            if term not in self.idf:
                continue
            idf = self.idf[term]
            for idx in self.inverted.get(term, []):
                tf = self.term_freqs[idx].get(term, 0)
                dl = self.doc_len[idx]
                norm = 1 - self.b + self.b * dl / max(self.avg_len, 1)
                score = idf * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)
                scores[idx] += score

        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
        return [(self.doc_ids[idx], score) for idx, score in ranked]


# ---------------------------------------------------------------------------
# Vector Index
# ---------------------------------------------------------------------------

class VectorIndex:
    """Dense vector index using sentence-transformers + numpy."""

    def __init__(self, model_name: str = "", dim: int = 312):
        self.model_name = model_name or settings.embedding.model_name
        self.dim = dim
        self.doc_ids: list[str] = []
        self.embeddings: Optional[np.ndarray] = None
        self._model = None

    def _get_model(self):
        """Lazy-load the sentence transformer model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            self.dim = self._model.get_sentence_embedding_dimension()
        return self._model

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Encode texts into dense vectors."""
        model = self._get_model()
        embeddings = model.encode(
            texts, batch_size=batch_size, show_progress_bar=False,
            normalize_embeddings=True,
        )
        return np.array(embeddings, dtype=np.float32)

    def add(self, doc_id: str, text: str) -> None:
        """Add a document (encodes on the fly)."""
        emb = self.encode([text])
        if self.embeddings is None:
            self.embeddings = emb
        else:
            self.embeddings = np.vstack([self.embeddings, emb])
        self.doc_ids.append(doc_id)

    def add_batch(self, doc_ids: list[str], texts: list[str]) -> None:
        """Add documents in batch (more efficient)."""
        embs = self.encode(texts, batch_size=settings.embedding.batch_size)
        if self.embeddings is None:
            self.embeddings = embs
        else:
            self.embeddings = np.vstack([self.embeddings, embs])
        self.doc_ids.extend(doc_ids)

    def search(self, query: str, top_k: int = 15) -> list[tuple[str, float]]:
        """Search and return (doc_id, score) pairs."""
        if self.embeddings is None or len(self.doc_ids) == 0:
            return []

        query_emb = self.encode([query])
        # Cosine similarity (embeddings are normalized)
        scores = (self.embeddings @ query_emb.T).flatten()
        top_indices = np.argsort(-scores)[:top_k]
        return [(self.doc_ids[i], float(scores[i])) for i in top_indices]


# ---------------------------------------------------------------------------
# Hybrid Search Engine
# ---------------------------------------------------------------------------

class HybridSearch:
    """Combines BM25 + vector search with graph filtering."""

    def __init__(self):
        self.bm25 = BM25Index()
        self.vector = VectorIndex()
        self.chunks: dict[str, dict] = {}  # chunk_id -> {text, doc_id, ...}
        self.documents: dict[str, dict] = {}  # doc_id -> document dict
        self._built = False

    def add_document(self, doc: Document) -> None:
        """Add a document and its chunks to the search index."""
        self.documents[doc.id] = doc.to_dict()

        chunk_ids = []
        chunk_texts = []
        for chunk in doc.chunks:
            self.chunks[chunk.id] = {
                "text": chunk.text,
                "doc_id": chunk.doc_id,
                "index": chunk.index,
                "page": chunk.page,
            }
            self.bm25.add(chunk.id, chunk.text)
            chunk_ids.append(chunk.id)
            chunk_texts.append(chunk.text)

        # Batch encode for efficiency
        if chunk_ids:
            self.vector.add_batch(chunk_ids, chunk_texts)

    def build(self) -> None:
        """Build indices after all documents are added."""
        self.bm25.build()
        self._built = True
        logger.info(f"Search index built: {len(self.chunks)} chunks, "
                     f"{len(self.documents)} documents")

    def search(
        self,
        query: str,
        top_k: int = 15,
        bm25_weight: Optional[float] = None,
        vector_weight: Optional[float] = None,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """Hybrid search combining BM25 and vector retrieval.

        Args:
            query: Natural language query.
            top_k: Number of results to return.
            bm25_weight: Weight for BM25 scores.
            vector_weight: Weight for vector scores.
            filters: Optional filters (geography, year_range, category, etc.)

        Returns:
            List of result dicts with chunk_id, text, doc_id, score.
        """
        if not self._built:
            self.build()

        bm25_weight = bm25_weight or settings.bm25_weight
        vector_weight = vector_weight or settings.vector_weight

        # Lazy-load embeddings on first vector search
        self._ensure_embeddings(index_path=INDEX_PATH)

        # BM25 results
        bm25_results = dict(self.bm25.search(query, top_k=top_k * 2))

        # Vector results (only if embeddings are loaded and available)
        if self.vector.embeddings is not None:
            try:
                vector_results = dict(
                    _timed_call(
                        lambda q=query, tk=top_k * 2: self.vector.search(q, top_k=tk),
                        timeout=10.0,
                    )
                )
            except Exception as e:
                logger.warning(f"Vector search failed (BM25-only fallback): {e}")
                vector_results = {}
        else:
            vector_results = {}

        # Normalize scores
        all_chunk_ids = set(bm25_results.keys()) | set(vector_results.keys())

        bm25_max = max(bm25_results.values()) if bm25_results else 1.0
        vec_max = max(vector_results.values()) if vector_results else 1.0

        # Combine scores
        combined: dict[str, float] = {}
        for chunk_id in all_chunk_ids:
            bm25_score = bm25_results.get(chunk_id, 0) / max(bm25_max, 1e-9)
            vec_score = vector_results.get(chunk_id, 0) / max(vec_max, 1e-9)
            combined[chunk_id] = bm25_weight * bm25_score + vector_weight * vec_score

        # Sort and take top_k
        ranked = sorted(combined.items(), key=lambda x: -x[1])[:top_k * 2]

        # Apply filters
        results = []
        for chunk_id, score in ranked:
            chunk = self.chunks.get(chunk_id)
            if chunk is None:
                continue
            doc = self.documents.get(chunk["doc_id"], {})

            if filters and not self._matches_filters(doc, filters):
                continue

            results.append({
                "chunk_id": chunk_id,
                "text": chunk["text"][:500],
                "full_text": chunk["text"],
                "doc_id": chunk["doc_id"],
                "page": chunk.get("page"),
                "score": round(score, 4),
                "doc_title": doc.get("title", ""),
                "doc_filename": doc.get("filename", ""),
                "doc_category": doc.get("category", ""),
                "doc_year": doc.get("year"),
                "doc_geography": doc.get("geography", ""),
                "doc_trust": doc.get("trust", 1),
                "doc_authors": doc.get("authors", []),
                "doc_source_type": doc.get("source_type", ""),
            })

            if len(results) >= top_k:
                break

        return results

    def _matches_filters(self, doc: dict, filters: dict) -> bool:
        """Check if a document matches the given filters."""
        if "geography" in filters:
            geo = filters["geography"]
            if isinstance(geo, str):
                geo = [geo]
            if doc.get("geography") not in geo:
                return False

        if "year_from" in filters and doc.get("year"):
            if doc["year"] < filters["year_from"]:
                return False

        if "year_to" in filters and doc.get("year"):
            if doc["year"] > filters["year_to"]:
                return False

        if "category" in filters:
            cat = filters["category"]
            if isinstance(cat, str):
                cat = [cat]
            if doc.get("category") not in cat:
                return False

        if "source_type" in filters:
            st = filters["source_type"]
            if isinstance(st, str):
                st = [st]
            if doc.get("source_type") not in st:
                return False

        if "language" in filters:
            if doc.get("language") != filters["language"]:
                return False

        return True

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    def _save_bm25(self, path: Path) -> None:
        """Save BM25 index using pickle (fast and compact)."""
        import pickle
        data = {
            "doc_ids": self.bm25.doc_ids,
            "doc_len": self.bm25.doc_len,
            "avg_len": self.bm25.avg_len,
            "term_freqs": self.bm25.term_freqs,
            "idf": self.bm25.idf,
            "inverted": dict(self.bm25.inverted),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(data, f, protocol=4)

    def _load_bm25(self, path: Path) -> bool:
        """Load BM25 index from pickle. Returns False if not present."""
        import pickle
        from collections import defaultdict
        if not path.exists():
            return False
        with open(path, "rb") as f:
            d = pickle.load(f)
        self.bm25.doc_ids = d["doc_ids"]
        self.bm25.doc_len = d["doc_len"]
        self.bm25.avg_len = float(d["avg_len"])
        self.bm25.term_freqs = d["term_freqs"]
        self.bm25.idf = d["idf"]
        self.bm25.inverted = defaultdict(list, d["inverted"])
        self.bm25.doc_tokens = [[] for _ in self.bm25.doc_ids]
        return True

    def save(self, index_path: Optional[Path] = None, docs_path: Optional[Path] = None) -> None:
        """Save the search index to disk."""
        index_path = index_path or INDEX_PATH
        docs_path = docs_path or DOCS_DB_PATH
        bm25_path = (docs_path or DOCS_DB_PATH).with_suffix(".bm25.pkl")

        # Save vector embeddings
        if self.vector.embeddings is not None:
            np.savez(
                str(index_path),
                embeddings=self.vector.embeddings,
                doc_ids=np.array(self.vector.doc_ids, dtype=object),
            )

        # Save chunks and documents (no BM25 inline)
        data = {
            "chunks": self.chunks,
            "documents": self.documents,
        }
        with open(docs_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        # Save BM25 separately (faster load)
        self._save_bm25(bm25_path)

        logger.info(f"Saved search index: {len(self.chunks)} chunks -> {index_path}")

    def _ensure_embeddings(self, index_path: Optional[Path] = None, timeout: float = 15.0) -> None:
        """Load embeddings lazily on first use (best-effort, with timeout)."""
        if self.vector.embeddings is not None:
            return
        index_path = index_path or INDEX_PATH
        if not index_path.exists():
            return
        try:
            logger.info("Loading vector embeddings...")
            _timed_call(
                lambda: (
                    setattr(self.vector, "embeddings", None),
                    setattr(self.vector, "doc_ids", []),
                )[0]
                or self._load_embeddings_impl(index_path),
                timeout=timeout,
            )
            logger.info(f"Loaded {len(self.vector.doc_ids)} embeddings")
        except Exception as e:
            logger.warning(f"Failed to load vector embeddings (BM25-only mode): {e}")

    def _load_embeddings_impl(self, index_path: Path) -> None:
        loaded = np.load(str(index_path), allow_pickle=True)
        self.vector.embeddings = loaded["embeddings"]
        self.vector.doc_ids = list(loaded["doc_ids"])

    def load(self, index_path: Optional[Path] = None, docs_path: Optional[Path] = None) -> bool:
        """Load the search index from disk (embeddings loaded lazily)."""
        index_path = index_path or INDEX_PATH
        docs_path = docs_path or DOCS_DB_PATH

        if not docs_path.exists():
            return False

        # Load chunks and documents
        with open(docs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.chunks = data["chunks"]
        self.documents = data["documents"]

        # Do NOT load embeddings here; they are loaded lazily on first search.

        # Load BM25 from pickle if available; otherwise rebuild
        bm25_path = (docs_path or DOCS_DB_PATH).with_suffix(".bm25.pkl")
        if not self._load_bm25(bm25_path):
            for chunk_id, chunk_data in self.chunks.items():
                self.bm25.add(chunk_id, chunk_data["text"])
            self.bm25.build()
            self._save_bm25(bm25_path)

        self._built = True
        logger.info(f"Loaded search index: {len(self.chunks)} chunks")
        return True
