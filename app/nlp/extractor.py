"""Entity and relation extraction from text.

Two-tier approach:
1. Heuristic keyword matching (fast, always available) — finds materials,
   processes, equipment, parameters, and numeric values using regex/keyword sets.
2. LLM-based extraction (accurate, slower) — uses the LLM to extract structured
   entities and relations from text chunks, with domain-specific prompts.

The heuristic extractor runs on every chunk; the LLM extractor runs on a
sample of chunks per document (to control cost/latency).
"""
from __future__ import annotations

import re
import logging
from typing import Optional

from ..core.ontology import (
    EntityType, RelationType, normalize_term,
    MATERIAL_KEYWORDS, PROCESS_KEYWORDS, EQUIPMENT_KEYWORDS,
    PARAMETER_KEYWORDS, UNIT_PATTERNS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Heuristic entity extraction
# ---------------------------------------------------------------------------

def heuristic_extract_entities(text: str) -> list[dict]:
    """Extract entities using keyword matching and regex patterns.

    Returns list of {"type": ..., "name": ..., "canonical": ..., "value": ...}
    """
    entities = []
    text_lower = text.lower()

    # Materials
    for kw in MATERIAL_KEYWORDS:
        if kw in text_lower:
            canonical = normalize_term(kw)
            entities.append({
                "type": EntityType.MATERIAL.value,
                "name": kw,
                "canonical": canonical,
            })

    # Processes
    for kw in PROCESS_KEYWORDS:
        if kw in text_lower:
            canonical = normalize_term(kw)
            entities.append({
                "type": EntityType.PROCESS.value,
                "name": kw,
                "canonical": canonical,
            })

    # Equipment
    for kw in EQUIPMENT_KEYWORDS:
        if kw in text_lower:
            canonical = normalize_term(kw)
            entities.append({
                "type": EntityType.EQUIPMENT.value,
                "name": kw,
                "canonical": canonical,
            })

    # Parameters (keywords)
    for kw in PARAMETER_KEYWORDS:
        if kw in text_lower:
            canonical = normalize_term(kw)
            entities.append({
                "type": EntityType.PARAMETER.value,
                "name": kw,
                "canonical": canonical,
            })

    # Numeric values with units — critical for metallurgy
    numeric_entities = extract_numeric_values(text)
    entities.extend(numeric_entities)

    # Deduplicate by (type, canonical)
    seen = set()
    unique = []
    for e in entities:
        key = (e["type"], e.get("canonical", e["name"]))
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return unique


def extract_numeric_values(text: str) -> list[dict]:
    """Extract numeric values with units from text.

    Handles patterns like:
    - "концентрация 300 мг/л"
    - "температура 60-80°C"
    - "скорость 0.4 м/с"
    - "≤1000 мг/дм³"
    - "извлечение 95.5%"
    """
    entities = []

    # Pattern: number (with optional range, comparison, decimal) + unit
    # Units are matched from our known set
    unit_alt = "|".join(re.escape(u) for u in sorted(UNIT_PATTERNS, key=len, reverse=True))

    # Pattern for value + unit
    pattern = rf"(?:(?:≤|>=|<=|>|<|≈|~)?\s*)?(\d+(?:[.,]\d+)?)\s*(?:[-–—]\s*(\d+(?:[.,]\d+)?)\s*)?({unit_alt})"
    for m in re.finditer(pattern, text, re.IGNORECASE):
        val1 = float(m.group(1).replace(",", "."))
        val2_str = m.group(2)
        unit = m.group(3)

        # Determine the parameter name from context (look back 50 chars)
        context_start = max(0, m.start() - 50)
        context = text[context_start:m.start()].lower()

        param_name = None
        for pkw in PARAMETER_KEYWORDS:
            if pkw in context:
                param_name = normalize_term(pkw)
                break

        value = val1
        if val2_str:
            value = [val1, float(val2_str.replace(",", "."))]

        entities.append({
            "type": EntityType.PARAMETER.value,
            "name": param_name or f"parameter_{unit}",
            "canonical": param_name or f"parameter_{unit}",
            "value": value,
            "unit": unit,
        })

    return entities


def heuristic_extract_relations(
    entities: list[dict], text: str, doc_id: str
) -> list[dict]:
    """Extract relations between entities based on co-occurrence and patterns.

    Simple co-occurrence heuristic: if two entities of different types appear
    in the same text, create a relation between them.
    """
    relations = []

    # Group entities by type
    by_type: dict[str, list[dict]] = {}
    for e in entities:
        by_type.setdefault(e["type"], []).append(e)

    # Process -> Material (uses_material)
    processes = by_type.get(EntityType.PROCESS.value, [])
    materials = by_type.get(EntityType.MATERIAL.value, [])
    for proc in processes:
        for mat in materials:
            if proc["canonical"] != mat["canonical"]:
                relations.append({
                    "source_type": EntityType.PROCESS.value,
                    "source": proc["canonical"],
                    "target_type": EntityType.MATERIAL.value,
                    "target": mat["canonical"],
                    "type": RelationType.USES_MATERIAL.value,
                    "evidence": text[:200],
                })

    # Process -> Equipment (uses_equipment)
    equipment = by_type.get(EntityType.EQUIPMENT.value, [])
    for proc in processes:
        for eq in equipment:
            relations.append({
                "source_type": EntityType.PROCESS.value,
                "source": proc["canonical"],
                "target_type": EntityType.EQUIPMENT.value,
                "target": eq["canonical"],
                "type": RelationType.USES_EQUIPMENT.value,
                "evidence": text[:200],
            })

    # Process -> Parameter (has_parameter)
    params = by_type.get(EntityType.PARAMETER.value, [])
    for proc in processes:
        for param in params:
            if "value" in param:
                relations.append({
                    "source_type": EntityType.PROCESS.value,
                    "source": proc["canonical"],
                    "target_type": EntityType.PARAMETER.value,
                    "target": param["canonical"],
                    "type": RelationType.HAS_PARAMETER.value,
                    "value": param.get("value"),
                    "unit": param.get("unit"),
                    "evidence": text[:200],
                })

    return relations


# ---------------------------------------------------------------------------
# LLM-based entity extraction
# ---------------------------------------------------------------------------

LLM_EXTRACT_PROMPT = """Ты — эксперт по извлечению сущностей и связей из научных текстов по горно-металлургической тематике.

Извлеки из следующего текста сущности и связи в формате JSON.

Типы сущностей: Material, Process, Equipment, Parameter, Condition, Result, Method, Technology
Типы связей: uses_material, uses_equipment, has_parameter, has_condition, has_result, produces, improves, decreases, requires

Для числовых параметров указывай value (число) и unit (единица измерения).

Текст:
---
{text}
---

Верни ТОЛЬКО JSON в формате:
{{
  "entities": [
    {{"type": "Material", "name": "никель", "canonical": "никель"}},
    {{"type": "Process", "name": "электроэкстракция", "canonical": "электроэкстракция"}},
    {{"type": "Parameter", "name": "скорость циркуляции католита", "value": 0.4, "unit": "м/с"}}
  ],
  "relations": [
    {{"source": "электроэкстракция", "target": "никель", "type": "uses_material"}},
    {{"source": "электроэкстракция", "target": "скорость циркуляции католита", "type": "has_parameter"}}
  ]
}}"""


def llm_extract_entities(
    text: str, llm_client=None, max_tokens: int = 1024
) -> dict:
    """Extract entities and relations using LLM.

    Args:
        text: Text chunk to process.
        llm_client: LLM client instance.
        max_tokens: Max tokens for response.

    Returns:
        {"entities": [...], "relations": [...]}
    """
    if llm_client is None:
        from .llm_client import get_llm
        llm_client = get_llm()

    # Truncate text to fit context
    text_trunc = text[:3000]

    messages = [
        {"role": "system", "content": "Ты извлекаешь сущности из научных текстов. Возвращай только JSON."},
        {"role": "user", "content": LLM_EXTRACT_PROMPT.format(text=text_trunc)},
    ]

    try:
        result = llm_client.extract_json(messages, max_tokens=max_tokens)
        if isinstance(result, dict) and "entities" in result:
            # Normalize entity names
            for e in result.get("entities", []):
                if "canonical" not in e or not e["canonical"]:
                    e["canonical"] = normalize_term(e.get("name", ""))
            return result
    except Exception as e:
        logger.warning(f"LLM entity extraction failed: {e}")

    return {"entities": [], "relations": []}


# ---------------------------------------------------------------------------
# Combined extraction
# ---------------------------------------------------------------------------

def extract_from_chunk(
    text: str,
    doc_id: str,
    use_llm: bool = False,
    llm_client=None,
) -> dict:
    """Extract entities and relations from a text chunk.

    Combines heuristic and (optionally) LLM extraction.

    Args:
        text: Chunk text.
        doc_id: Parent document ID.
        use_llm: Whether to also use LLM extraction.
        llm_client: LLM client for LLM extraction.

    Returns:
        {"entities": [...], "relations": [...]}
    """
    # Heuristic extraction (always)
    entities = heuristic_extract_entities(text)
    relations = heuristic_extract_relations(entities, text, doc_id)

    # LLM extraction (optional, for higher quality)
    if use_llm and llm_client is not None:
        llm_result = llm_extract_entities(text, llm_client)
        llm_entities = llm_result.get("entities", [])
        llm_relations = llm_result.get("relations", [])

        # Merge: add LLM entities not already found heuristically
        existing_keys = {(e["type"], e.get("canonical", e["name"])) for e in entities}
        for e in llm_entities:
            key = (e.get("type", ""), e.get("canonical", e.get("name", "")))
            if key not in existing_keys:
                entities.append(e)
                existing_keys.add(key)

        # Add LLM relations
        relations.extend(llm_relations)

    return {"entities": entities, "relations": relations}
