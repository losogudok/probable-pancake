"""RAG answer generation: combines search results + graph facts + LLM.

Generates structured answers with citations, contradictions, experts, and
knowledge gaps — exactly as required by the hackathon task.
"""
from __future__ import annotations

import logging
import re
import threading
from typing import Optional

from ..core.config import settings
from ..core.ontology import EntityType, RelationType, normalize_term, trust_stars
from ..search.hybrid import HybridSearch
from ..graph.kg import KnowledgeGraph
from ..nlp.llm_client import get_llm

logger = logging.getLogger(__name__)


def _timed_call(fn, timeout: float, *args, **kwargs):
    result_holder = []
    error_holder = []

    def _target():
        try:
            result_holder.append(fn(*args, **kwargs))
        except Exception as e:
            error_holder.append(e)

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        raise TimeoutError(f"Operation timed out after {timeout}s")
    if error_holder:
        raise error_holder[0]
    if result_holder:
        return result_holder[0]
    raise RuntimeError("Operation finished abnormally")


# ---------------------------------------------------------------------------
# Query understanding
# ---------------------------------------------------------------------------

def parse_query(query: str) -> dict:
    """Parse a natural language query to extract filters and intent.

    Detects:
    - Geography (Russia/foreign)
    - Year range
    - Numeric conditions
    - Entity types mentioned
    """
    query_lower = query.lower()
    filters = {}
    intent = "search"  # search, compare, gaps, contradictions, experts

    # Geography
    if any(w in query_lower for w in ["российск", "отечествен", "россия", "в россии"]):
        filters["geography"] = ["Russia", "CIS", "Global"]
    if any(w in query_lower for w in ["зарубежн", "мировая практика", "мировой опыт", "международ"]):
        filters["geography"] = ["Foreign", "Global"]

    # Year range
    year_match = re.search(r"(?:за\s+)?(?:последние|прошлые)\s+(\d+)\s+лет", query_lower)
    if year_match:
        years = int(year_match.group(1))
        from datetime import datetime
        filters["year_from"] = datetime.now().year - years
        filters["year_to"] = datetime.now().year

    # Explicit year
    year_explicit = re.findall(r"\b(20[0-2]\d)\b", query)
    if year_explicit:
        filters["year_from"] = int(min(year_explicit))
        filters["year_to"] = int(max(year_explicit))

    # Intent detection
    if any(w in query_lower for w in ["сравн", "vs", "против", "отлич"]):
        intent = "compare"
    elif any(w in query_lower for w in ["пробел", "не изучен", "не исследован", "нет данных"]):
        intent = "gaps"
    elif any(w in query_lower for w in ["противореч", "конфликт", "разноглас"]):
        intent = "contradictions"
    elif any(w in query_lower for w in ["эксперт", "кто занимается", "кто изучает", "специалист"]):
        intent = "experts"

    # Numeric conditions
    numeric_conditions = []
    # Pattern: parameter + comparison + number + unit
    num_pattern = r"(\w+)\s*(≤|<=|>=|>|<|≈|не более|не менее|от|до)?\s*(\d+(?:[.,]\d+)?)\s*(мг/л|мг/дм|г/л|°c|м/с|%|моль/л)?"
    for m in re.finditer(num_pattern, query_lower):
        param = m.group(1)
        op = m.group(2)
        val = m.group(3)
        unit = m.group(4)
        if param and val and op:
            numeric_conditions.append({
                "parameter": param,
                "operator": op,
                "value": float(val.replace(",", ".")),
                "unit": unit or "",
            })

    return {
        "intent": intent,
        "filters": filters,
        "numeric_conditions": numeric_conditions,
        "original_query": query,
    }


# ---------------------------------------------------------------------------
# RAG answer generation
# ---------------------------------------------------------------------------

ANSWER_SYSTEM_PROMPT = """Ты — аналитик научно-технических знаний в области горно-металлургической отрасли.
Твоя задача — давать точные, структурированные ответы на основе предоставленных фрагментов документов и данных из графа знаний.

Правила:
1. Отвечай на русском языке (если вопрос на английском, отвечай на английском).
2. Каждый факт сопровождай ссылкой на источник в формате [Источник N].
3. Если данные противоречивы, укажи это явно.
4. Если данных недостаточно, честно скажи об этом.
5. Указывай уровень доверия к выводам на основе типа источника.
6. Структурируй ответ с заголовками.
"""

ANSWER_USER_TEMPLATE = """Вопрос: {query}

Найденные фрагменты из документов:
{context}

Данные из графа знаний:
{graph_facts}

Дай структурированный ответ:
1. **Ответ на вопрос** — основной вывод
2. **Источники** — список источников с указанием названия, года, уровня доверия
3. **Числовые параметры** — если в вопросе есть числовые условия, проверь их
4. **Противоречия** — если есть расхождения между источниками
5. **Эксперты** — если известны авторы по теме
6. **Пробелы в знаниях** — чего не хватает для полного ответа
"""


class RAGEngine:
    """RAG engine combining search + graph + LLM."""

    def __init__(
        self,
        search_engine: HybridSearch,
        kg: KnowledgeGraph,
        llm_client=None,
    ):
        self.search = search_engine
        self.kg = kg
        self.llm = llm_client or get_llm()

    def answer(
        self,
        query: str,
        top_k: int = 8,
        filters: Optional[dict] = None,
    ) -> dict:
        """Generate a RAG answer for a query.

        Args:
            query: Natural language question.
            top_k: Number of chunks to retrieve.
            filters: Optional pre-parsed filters.

        Returns:
            Dict with answer, sources, graph_facts, contradictions, etc.
        """
        # Parse query
        parsed = parse_query(query)
        effective_filters = filters or parsed["filters"]

        # Search
        results = self.search.search(
            query, top_k=top_k, filters=effective_filters
        )

        # Build context from search results
        context_parts = []
        sources = []
        for i, r in enumerate(results, 1):
            context_parts.append(
                f"[Источник {i}] {r['doc_title']} ({r['doc_year'] or 'н.д.'})\n"
                f"  Файл: {r['doc_filename']}\n"
                f"  Тип: {r['doc_source_type']}, География: {r['doc_geography']}\n"
                f"  Фрагмент: {r['full_text'][:600]}\n"
            )
            sources.append({
                "index": i,
                "title": r["doc_title"],
                "filename": r["doc_filename"],
                "year": r["doc_year"],
                "geography": r["doc_geography"],
                "trust": r["doc_trust"],
                "trust_stars": trust_stars(r["doc_trust"]),
                "category": r["doc_category"],
                "authors": r["doc_authors"],
                "score": r["score"],
                "text_snippet": r["text"][:200],
            })

        context = "\n".join(context_parts) if context_parts else "Подходящие фрагменты не найдены."

        # Get graph facts
        graph_facts = self._get_graph_facts(query)

        # Get contradictions
        contradictions = self.kg.find_contradictions()[:5]

        # Get gaps
        gaps = self.kg.find_gaps()[:5]

        # Generate LLM answer (with short timeout; fallback to context-only answer)
        answer_text = None
        try:
            answer_text = _timed_call(
                self._generate_answer,
                timeout=5.0,
                query=query,
                context=context,
                graph_facts=graph_facts,
                results=results,
            )
        except Exception as e:
            logger.error(f"LLM answer generation failed: {e}")

        if not answer_text:
            # Build a concise answer from retrieved context (no LLM)
            snippets = []
            for r in (results or [])[:4]:
                text = r.get("full_text", "").strip()
                if text:
                    # Take first 180 chars as snippet
                    snippets.append(text[:180].replace("\n", " "))

            answer_parts = []
            if snippets:
                answer_parts.append(
                    "На основе найденных материалов:\n"
                    + "\n".join([f"- {s}" for s in snippets])
                )
            else:
                answer_parts.append(
                    "Прямых фрагментов, отвечающих на ваш вопрос, не найдено."
                )

            if graph_facts and "Релевантные факты из графа не найдены" not in graph_facts:
                answer_parts.append(
                    "Связанные данные из графа знаний:\n"
                    + "\n".join((graph_facts or "").strip().split("\n")[:6])
                )

            answer_parts.append(
                f"Всего использовано источников: {len(results)}.\n"
                "LLM недоступен — ответ сформирован автоматически на основе извлечённых фрагментов."
            )
            answer_text = "\n\n".join(answer_parts)

        return {
            "query": query,
            "intent": parsed["intent"],
            "answer": answer_text,
            "sources": sources,
            "graph_facts": graph_facts,
            "contradictions": contradictions,
            "gaps": gaps,
            "num_results": len(results),
            "filters_applied": effective_filters,
        }

    def _get_graph_facts(self, query: str) -> str:
        """Extract relevant facts from the knowledge graph."""
        facts = []

        # Find entities mentioned in query
        for ent_type, ents in [
            (EntityType.PROCESS.value, self.kg.find_entities(EntityType.PROCESS.value)),
            (EntityType.MATERIAL.value, self.kg.find_entities(EntityType.MATERIAL.value)),
        ]:
            for ent in ents:
                canonical = ent.get("canonical", "")
                if canonical and canonical.lower() in query.lower():
                    # Get neighbors
                    neighbors = self.kg.get_neighbors(ent["id"], max_depth=1, limit=10)
                    for edge in neighbors["edges"]:
                        if edge["source"] == ent["id"]:
                            target_node = self.kg.get_entity(edge["target"])
                            if target_node:
                                facts.append(
                                    f"  {canonical} --{edge['type']}--> "
                                    f"{target_node.get('canonical', '')} "
                                    f"(тип: {target_node.get('type', '')}, "
                                    f"источников: {len(target_node.get('source_ids', []))})"
                                )

        if not facts:
            return "Релевантные факты из графа не найдены."
        return "\n".join(facts[:20])

    def _generate_answer(
        self, query: str, context: str, graph_facts: str, results: list
    ) -> str:
        """Generate the final answer using LLM (may raise if unreachable)."""
        messages = [
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": ANSWER_USER_TEMPLATE.format(
                query=query, context=context, graph_facts=graph_facts
            )},
        ]

        answer = self.llm.chat(
            messages,
            max_tokens=settings.llm.max_tokens,
            temperature=0.2,
        )
        return answer
