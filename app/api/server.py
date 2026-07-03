"""FastAPI server for the Scientific Knowledge Graph platform."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from ..core.config import settings, GRAPH_PATH, INDEX_PATH, DOCS_DB_PATH, BASE_DIR
from ..core.ontology import EntityType, RelationType, trust_stars
from ..graph.kg import KnowledgeGraph
from ..search.hybrid import HybridSearch
from ..rag.engine import RAGEngine, parse_query
from ..nlp.llm_client import get_llm

logger = logging.getLogger(__name__)

# Global state
kg = KnowledgeGraph()
search = HybridSearch()
rag: Optional[RAGEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load data on startup."""
    global rag
    logging.basicConfig(level=logging.INFO)

    logger.info("Loading knowledge graph...")
    if GRAPH_PATH.exists():
        kg.load()
    else:
        logger.warning("No knowledge graph found. Run build first.")

    logger.info("Loading search index...")
    if DOCS_DB_PATH.exists():
        search.load()
    else:
        logger.warning("No search index found. Run build first.")

    rag = RAGEngine(search, kg)
    logger.info(f"Ready: {kg.get_stats()}")
    yield


app = FastAPI(
    title="Научный клубок — Scientific Knowledge Graph",
    description="R&D Knowledge Graph platform for mining & metallurgy",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    top_k: int = 8
    filters: Optional[dict] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 15
    filters: Optional[dict] = None


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    """Health check."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/stats")
async def stats():
    """Get knowledge graph statistics."""
    return kg.get_stats()


@app.post("/api/search")
async def search_docs(req: SearchRequest):
    """Semantic search across documents."""
    results = search.search(req.query, top_k=req.top_k, filters=req.filters)
    return {"query": req.query, "results": results, "count": len(results)}


@app.post("/api/ask")
async def ask(req: QueryRequest):
    """RAG answer generation."""
    if rag is None:
        raise HTTPException(503, "RAG engine not initialized")
    try:
        result = rag.answer(req.query, top_k=req.top_k, filters=req.filters)
        return result
    except Exception as e:
        logger.error(f"/api/ask error: {e}", exc_info=True)
        return {
            "query": req.query,
            "answer": f"Ошибка при обработке запроса: {e}\nОтвет сгенерирован на основе найденных фрагментов без LLM.",
            "sources": [],
            "graph_facts": [],
            "contradictions": [],
            "gaps": [],
            "num_results": 0,
        }


@app.get("/api/entities")
async def get_entities(
    entity_type: Optional[str] = None,
    name: Optional[str] = None,
    limit: int = 50,
):
    """List entities in the knowledge graph."""
    results = kg.find_entities(entity_type=entity_type, name=name)
    return {"entities": results[:limit], "count": len(results)}


@app.get("/api/graph/{node_id}")
async def get_graph(node_id: str, depth: int = 2, limit: int = 50):
    """Get subgraph around a node."""
    subgraph = kg.get_neighbors(node_id, max_depth=depth, limit=limit)
    return subgraph


@app.get("/api/contradictions")
async def get_contradictions():
    """Find contradicting data in the knowledge graph."""
    return {"contradictions": kg.find_contradictions()}


@app.get("/api/gaps")
async def get_gaps():
    """Find knowledge gaps."""
    return {"gaps": kg.find_gaps()}


@app.get("/api/documents")
async def list_documents(
    category: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    geography: Optional[str] = None,
    limit: int = 50,
):
    """List documents in the corpus."""
    docs = list(search.documents.values())

    if category:
        docs = [d for d in docs if d.get("category") == category]
    if year_from:
        docs = [d for d in docs if d.get("year") and d["year"] >= year_from]
    if year_to:
        docs = [d for d in docs if d.get("year") and d["year"] <= year_to]
    if geography:
        docs = [d for d in docs if d.get("geography") == geography]

    docs = sorted(docs, key=lambda d: d.get("year") or 0, reverse=True)
    return {"documents": docs[:limit], "count": len(docs)}


@app.get("/api/dashboard")
async def dashboard():
    """Dashboard metrics for leadership."""
    stats = kg.get_stats()

    # Documents by category
    by_category: dict[str, int] = {}
    by_geography: dict[str, int] = {}
    by_year: dict[int, int] = {}
    for doc in search.documents.values():
        cat = doc.get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1

        geo = doc.get("geography", "Unknown")
        by_geography[geo] = by_geography.get(geo, 0) + 1

        year = doc.get("year")
        if year:
            by_year[year] = by_year.get(year, 0) + 1

    contradictions = kg.find_contradictions()
    gaps = kg.find_gaps()

    return {
        "graph_stats": stats,
        "documents_by_category": by_category,
        "documents_by_geography": by_geography,
        "documents_by_year": dict(sorted(by_year.items())),
        "total_documents": len(search.documents),
        "total_chunks": len(search.chunks),
        "contradictions_count": len(contradictions),
        "gaps_count": len(gaps),
        "top_contradictions": contradictions[:5],
        "top_gaps": gaps[:5],
    }


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

frontend_dir = BASE_DIR / "frontend"
frontend_dist = frontend_dir / "dist"
frontend_assets = frontend_dist / "assets"
if frontend_assets.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_assets)), name="frontend-assets")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the production React application."""
    index_html = frontend_dist / "index.html"
    if index_html.exists():
        return FileResponse(index_html)
    return HTMLResponse(
        "<h1>Научный клубок API</h1>"
        "<p>Frontend не собран. Выполните <code>cd frontend && npm ci && npm run build</code>.</p>"
    )


@app.get("/{frontend_path:path}", include_in_schema=False)
async def frontend_spa(frontend_path: str):
    """Return the React entrypoint for client-side routes and 404 for missing assets."""
    if frontend_path.startswith("api/") or frontend_path.startswith("assets/"):
        raise HTTPException(404, "Not found")
    index_html = frontend_dist / "index.html"
    if index_html.exists():
        return FileResponse(index_html)
    raise HTTPException(404, "Frontend build not found")
