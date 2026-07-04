#!/usr/bin/env python3
"""Паспорт документа для HTML-разметки.

Модуль не запускает отдельный этап пайплайна. Его вызывает главный
run_ontology_markup.py после извлечения сущностей и простых троек.

Задача: показать в верхней части HTML, для каких классов запросов документ
полезен, какие фасеты в нём есть и по каким числовым параметрам его можно
предварительно фильтровать.
"""
from __future__ import annotations

import html
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass
class ParameterFacet:
    name: str
    values: list[str] = field(default_factory=list)
    units: Counter[str] = field(default_factory=Counter)
    examples: list[str] = field(default_factory=list)


@dataclass
class DocumentSummary:
    source_name: str
    title: str
    query_badges: list[str]
    facets: dict[str, list[str]]
    parameter_facets: list[ParameterFacet]
    relation_counts: Counter[str]
    entity_type_counts: Counter[str]


def _get(obj: Any, name: str, default: Any = "") -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _clean(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value.strip(" «»\"'.,;:")


def _canon(entity: Any) -> str:
    return _clean(str(_get(entity, "canonical") or _get(entity, "surface") or ""))


def _surface(entity: Any) -> str:
    return _clean(str(_get(entity, "surface") or _get(entity, "text") or ""))


def _uniq(items: Iterable[str], limit: int = 12) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        item = _clean(item)
        if not item:
            continue
        key = item.casefold().replace("ё", "е")
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out




NOISY_FACET_VALUES = {
    "метод", "метода", "методы", "методах", "методов", "методов определения",
    "модель", "модели", "процесс", "процесса", "анализ", "оценка",
    "установка", "установки", "использование", "применение",
}


def _not_noise(value: str) -> bool:
    key = _clean(value).casefold().replace("ё", "е")
    if not key or key in NOISY_FACET_VALUES:
        return False
    # Одно короткое обычное слово в фасетах почти всегда хуже устойчивой фразы.
    if " " not in key and "-" not in key and len(key) < 5 and not key.isupper():
        return False
    return True


def _uniq_facets(items: Iterable[str], limit: int = 12) -> list[str]:
    return _uniq((item for item in items if _not_noise(item)), limit)

def _short_context(text: str, start: int, end: int, window: int = 90) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    snippet = re.sub(r"<!--\s*image\s*-->", " ", text[left:right], flags=re.IGNORECASE)
    snippet = re.sub(r"(?:<!--\s*)?(?:im)?age\s*-->", " ", snippet, flags=re.IGNORECASE)
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if len(snippet) > 220:
        snippet = snippet[:217].rstrip() + "..."
    return snippet


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip(" #\t")
        if line and line.lower() != "image" and not line.startswith("<!--"):
            return line[:180]
    return fallback


def _parameter_display(entity: Any) -> tuple[str, str, str]:
    name = _canon(entity) or _surface(entity)
    value = str(_get(entity, "value") or "").strip()
    unit = str(_get(entity, "unit") or "").strip()
    operator = str(_get(entity, "operator") or "").strip()
    if value:
        if operator == "range":
            shown = f"{value} {unit}".strip()
        elif operator:
            shown = f"{operator}{value} {unit}".strip()
        else:
            shown = f"{value} {unit}".strip()
    else:
        shown = _surface(entity)
    return name, shown, unit


def build_document_summary(source_path: Path, text: str, entities: list[Any], triples: list[Any]) -> DocumentSummary:
    """Построить компактный паспорт документа для шапки HTML."""
    source_name = source_path.name
    title = _extract_title(text, source_name)

    by_type: dict[str, list[Any]] = defaultdict(list)
    for e in entities:
        typ = str(_get(e, "entity_type") or "")
        if typ:
            by_type[typ].append(e)

    entity_counts = Counter(str(_get(e, "entity_type") or "") for e in entities if _get(e, "entity_type"))
    relation_counts = Counter(str(_get(t, "predicate") or "") for t in triples if _get(t, "predicate"))

    methods = _uniq_facets([_canon(e) for e in by_type.get("Method", [])] + [_canon(e) for e in by_type.get("Process", [])] + [_canon(e) for e in by_type.get("Model", [])], 14)
    equipment = _uniq_facets([_canon(e) for e in by_type.get("Equipment", [])] + [_canon(e) for e in by_type.get("Technology", [])], 14)
    geography = _uniq([_canon(e) for e in by_type.get("Geography", [])], 10)
    people_orgs = _uniq_facets(
        [_canon(e) for e in by_type.get("Expert", [])]
        + [_canon(e) for e in by_type.get("Organization", [])]
        + [_canon(e) for e in by_type.get("OrgUnit", [])]
        + [_canon(e) for e in by_type.get("Role", [])]
        + [_canon(e) for e in by_type.get("AcademicDegree", [])],
        16,
    )
    objects = _uniq_facets(
        [_canon(e) for e in by_type.get("MineObject", [])]
        + [_canon(e) for e in by_type.get("RockMass", [])]
        + [_canon(e) for e in by_type.get("GeologicalFeature", [])]
        + [_canon(e) for e in by_type.get("Material", [])],
        14,
    )

    parameter_map: dict[str, ParameterFacet] = {}
    for e in entities:
        typ = str(_get(e, "entity_type") or "")
        value = str(_get(e, "value") or "").strip()
        if typ not in {"Parameter", "Metric", "Property", "Condition"} or not value:
            continue
        name, shown, unit = _parameter_display(e)
        if not name:
            continue
        facet = parameter_map.setdefault(name, ParameterFacet(name=name))
        if shown not in facet.values:
            facet.values.append(shown)
        if unit:
            facet.units[unit] += 1
        try:
            start = int(_get(e, "start", 0))
            end = int(_get(e, "end", start))
        except Exception:
            start, end = 0, 0
        ctx = _short_context(text, start, end)
        if ctx and ctx not in facet.examples and len(facet.examples) < 3:
            facet.examples.append(ctx)

    parameter_facets = sorted(parameter_map.values(), key=lambda p: (-len(p.values), p.name.casefold()))[:12]

    # Оценка классов запросов — намеренно простые правила, без LLM.
    badges: list[str] = []
    has_method = bool(methods)
    has_param = bool(parameter_facets) or bool(by_type.get("Parameter"))
    has_equipment = bool(equipment)
    has_geo = bool(geography)
    has_expert = bool(by_type.get("Expert") or by_type.get("Organization") or by_type.get("OrgUnit"))
    if has_method and (has_param or has_equipment):
        badges.append("поиск документов по условиям")
    if has_param:
        badges.append("поиск фактов и значений")
    if entities:
        badges.append("доказательства / фрагменты")
    if len(by_type.get("Method", [])) >= 2 or relation_counts.get("measures", 0) >= 2:
        badges.append("сравнение методов")
    if has_method and has_param and (has_geo or has_equipment):
        badges.append("многопараметрический фильтр")
    if has_expert:
        badges.append("поиск экспертов и организаций")
    if relation_counts:
        badges.append("цепочки графа")

    return DocumentSummary(
        source_name=source_name,
        title=title,
        query_badges=_uniq(badges, 8),
        facets={
            "Методы / процессы": methods,
            "Параметры": [f"{p.name}: {', '.join(p.values[:6])}" for p in parameter_facets[:8]],
            "Оборудование": equipment,
            "Объекты / геология": objects,
            "География": geography,
            "Люди и организации": people_orgs,
        },
        parameter_facets=parameter_facets,
        relation_counts=relation_counts,
        entity_type_counts=entity_counts,
    )


def _chips(items: list[str], empty: str = "—") -> str:
    if not items:
        return f'<span class="muted">{html.escape(empty)}</span>'
    return "".join(f'<span class="chip">{html.escape(item)}</span>' for item in items)


def render_summary_html(summary: DocumentSummary) -> str:
    """Сформировать HTML-блок паспорта документа.

    Блок обычный, position: static. Он скроллится вместе с документом.
    """
    facet_cards: list[str] = []
    for title, values in summary.facets.items():
        if not values:
            continue
        facet_cards.append(
            '<section class="summary-card">'
            f'<h3>{html.escape(title)}</h3>'
            f'<div class="chip-row">{_chips(values)}</div>'
            '</section>'
        )

    param_details = []
    for p in summary.parameter_facets:
        examples = "".join(f"<li>{html.escape(ex)}</li>" for ex in p.examples)
        units = ", ".join(f"{u}×{c}" for u, c in p.units.most_common())
        unit_part = f" <span class=\"muted\">({html.escape(units)})</span>" if units else ""
        param_details.append(
            f"<li><b>{html.escape(p.name)}</b>{unit_part}: "
            f"{html.escape(', '.join(p.values[:10]))}"
            f"<ul>{examples}</ul></li>"
        )

    relation_items = "".join(
        f'<span class="mini-stat"><code>{html.escape(pred)}</code> ×{count}</span>'
        for pred, count in summary.relation_counts.most_common(12)
    ) or '<span class="muted">тройки не найдены</span>'

    entity_items = "".join(
        f'<span class="mini-stat">{html.escape(typ)} ×{count}</span>'
        for typ, count in summary.entity_type_counts.most_common(14)
    )

    return f"""
<section class="document-summary">
  <div class="summary-head">
    <div>
      <h2>Паспорт документа</h2>
      <div class="summary-title">{html.escape(summary.source_name)}</div>
      <div class="summary-subtitle">{html.escape(summary.title)}</div>
    </div>
  </div>

  <div class="summary-block">
    <h3>Подходит для запросов</h3>
    <div class="chip-row query-badges">{_chips(summary.query_badges)}</div>
  </div>

  <div class="summary-grid">
    {''.join(facet_cards)}
  </div>

  <details class="summary-details">
    <summary>Показать числовые условия, статистику сущностей и троек</summary>
    <div class="details-grid">
      <section>
        <h3>Числовые параметры с evidence</h3>
        <ul class="param-list">{''.join(param_details) or '<li class="muted">числовые параметры не найдены</li>'}</ul>
      </section>
      <section>
        <h3>Типы сущностей</h3>
        <div class="mini-stat-row">{entity_items}</div>
        <h3>Типы отношений</h3>
        <div class="mini-stat-row">{relation_items}</div>
      </section>
    </div>
  </details>
</section>
"""
