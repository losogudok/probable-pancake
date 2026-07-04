#!/usr/bin/env python3
"""Простой извлекатель троек отношений поверх уже найденных сущностей.

Идея намеренно тупая и прозрачная:
  сущность A + текстовый триггер + сущность B -> тройка A --predicate--> B.

Этот файл не занимается поиском сущностей. Он читает entity_matches.csv,
который создаёт ontology_highlighter.py, и строит поверх него отдельный слой
relations_simple/triples.*.

Пример:
  USBM Cell ... Производства Geokon (США)
  -> USBM Cell --produced_by--> Geokon
  -> Geokon --located_in--> США

Usage:
  python ontology_relation_extractor.py input.md \
    --entities markup/highlight/entity_matches.csv \
    --out-dir markup/relations_simple
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class EntityMention:
    id: str
    start: int
    end: int
    surface: str
    entity_type: str
    display_label: str
    source: str
    canonical: str = ""
    term_id: str = ""
    value: str = ""
    unit: str = ""
    operator: str = ""
    confidence: float = 0.0


@dataclass(frozen=True)
class RelationPattern:
    predicate: str
    subject_types: tuple[str, ...]
    object_types: tuple[str, ...]
    triggers: tuple[str, ...]
    confidence: float = 0.75
    max_gap: int = 260
    description: str = ""


@dataclass(frozen=True)
class Triple:
    subject_id: str
    subject_text: str
    subject_type: str
    predicate: str
    object_id: str
    object_text: str
    object_type: str
    trigger: str
    evidence: str
    start: int
    end: int
    confidence: float
    rule: str
    object_value: str = ""
    object_unit: str = ""
    object_operator: str = ""


# Предикаты сознательно ограничены. Это не OpenIE, а контролируемый слой графа.
RELATION_PATTERNS: tuple[RelationPattern, ...] = (
    RelationPattern(
        predicate="produced_by",
        subject_types=("Equipment", "Technology", "Method"),
        object_types=("Organization", "Expert"),
        triggers=("производства", "производитель", "изготовител", "разработка", "разработан", "manufactured by", "made by"),
        confidence=0.90,
        max_gap=320,
        description="Оборудование/метод произведены или разработаны организацией/автором.",
    ),
    RelationPattern(
        predicate="recommended_by_standard",
        subject_types=("Equipment", "Method", "Process"),
        object_types=("Publication", "Method", "Document"),
        triggers=("рекомендован стандартом", "рекомендована стандартом", "по стандарту", "standard test method"),
        confidence=0.86,
        max_gap=360,
        description="Метод или оборудование рекомендованы стандартом.",
    ),
    RelationPattern(
        predicate="uses_equipment",
        subject_types=("Method", "Process", "Model", "Technology"),
        object_types=("Equipment",),
        triggers=("с применением", "с использованием", "использованием", "использует", "применяет", "установка", "установки"),
        confidence=0.78,
        max_gap=260,
        description="Метод/процесс использует оборудование.",
    ),
    RelationPattern(
        predicate="measures",
        subject_types=("Method", "Process", "Equipment"),
        object_types=("Metric", "Property", "Parameter", "Condition"),
        triggers=("для определения", "определения", "измерения", "измерение", "оценки", "анализ"),
        confidence=0.76,
        max_gap=280,
        description="Метод/оборудование измеряет показатель или свойство.",
    ),
    RelationPattern(
        predicate="has_parameter",
        subject_types=("Process", "Method", "MineObject", "Equipment", "Model"),
        object_types=("Parameter", "Metric", "Property"),
        triggers=("диаметром", "диаметр", "глубиной", "глубину", "глубине", "глубина", "длиной", "расстоянии", "шагом", "с шагом", "составляют", "порядка"),
        confidence=0.74,
        max_gap=230,
        description="Процесс/объект имеет числовой или категориальный параметр.",
    ),
    RelationPattern(
        predicate="shows",
        subject_types=("Model", "Process", "Experiment"),
        object_types=("Result", "Claim", "Property", "Metric", "Condition"),
        triggers=("показывает", "показало", "говорит", "определена", "определено", "оценка", "оценки"),
        confidence=0.73,
        max_gap=320,
        description="Модель/эксперимент показывает результат или вывод.",
    ),
    RelationPattern(
        predicate="increases_risk",
        subject_types=("Condition", "Property", "Risk"),
        object_types=("Risk", "Result", "Property"),
        triggers=("увеличивает вероятность", "приводит к", "приводящих к", "приводящие к", "вызывает"),
        confidence=0.78,
        max_gap=320,
        description="Условие повышает риск или приводит к эффекту.",
    ),
    RelationPattern(
        predicate="oriented_along",
        subject_types=("Parameter", "Property", "Metric"),
        object_types=("GeologicalFeature", "Parameter", "MineObject"),
        triggers=("направлено вдоль", "направлен вдоль", "со направленно с", "сонаправленно с", "вдоль"),
        confidence=0.80,
        max_gap=240,
        description="Направление напряжения/параметра вдоль структуры.",
    ),
    RelationPattern(
        predicate="oriented_across",
        subject_types=("Parameter", "Property", "Metric"),
        object_types=("GeologicalFeature", "Parameter", "MineObject"),
        triggers=("направлено поперек", "направлен поперек", "поперек"),
        confidence=0.80,
        max_gap=240,
        description="Направление напряжения/параметра поперёк структуры.",
    ),
)

# Оргформа и страна в скобках после организации — отдельное короткое правило.
GEO_PAREN_GAP_RE = re.compile(r"^[\s,.;:–—\-]*\(?\s*$", re.UNICODE)

# Слишком общие одиночные кандидаты портят тройки. Их лучше не использовать как узлы отношений.
BAD_RELATION_SURFACES = {
    "метод", "метода", "методы", "модель", "модели", "данные", "результат", "результаты",
    "анализ", "оценка", "определение", "введение", "применением", "использованием",
    "пород", "полезных", "ископаемых", "технологии", "технология", "предпочтительным",
    "ооо", "докладчик", "заведующий", "лабораторией", "департамент", "к.т.н",
}


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def norm(value: str) -> str:
    value = value.replace("ё", "е").replace("Ё", "Е")
    value = value.replace("–", "-").replace("—", "-")
    return normalize_space(value).lower()


def html_escape(value: str) -> str:
    return html.escape(value, quote=True)


def read_entities(path: Path) -> list[EntityMention]:
    entities: list[EntityMention] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            surface = (row.get("surface") or "").strip()
            entity_type = (row.get("entity_type") or "").strip()
            if not surface or not entity_type:
                continue
            # Отбрасываем шумные однословные кандидаты, но оставляем известные онтологические сущности.
            is_known = (row.get("source") or "").startswith("ontology")
            if not is_known and norm(surface) in BAD_RELATION_SURFACES:
                continue
            if not is_known and len(surface) < 3:
                continue
            try:
                confidence = float(row.get("confidence") or 0.0)
            except ValueError:
                confidence = 0.0
            entities.append(EntityMention(
                id=f"e{idx}",
                start=int(row["start"]),
                end=int(row["end"]),
                surface=surface,
                entity_type=entity_type,
                display_label=row.get("display_label") or entity_type,
                source=row.get("source") or "",
                canonical=row.get("canonical") or "",
                term_id=row.get("term_id") or "",
                value=row.get("value") or "",
                unit=row.get("unit") or "",
                operator=row.get("operator") or "",
                confidence=confidence,
            ))
    return sorted(entities, key=lambda e: (e.start, e.end))


def type_ok(entity_type: str, allowed: Iterable[str]) -> bool:
    allowed_set = set(allowed)
    return "*" in allowed_set or entity_type in allowed_set


def find_evidence_bounds(text: str, start: int, end: int, padding: int = 120) -> tuple[int, int]:
    """Найти короткий, но читаемый фрагмент-доказательство вокруг пары сущностей."""
    left = text.rfind("\n", 0, start)
    right = text.find("\n", end)
    if left == -1 or start - left > padding:
        left = max(0, start - padding)
    else:
        left += 1
    if right == -1 or right - end > padding:
        right = min(len(text), end + padding)
    evidence = text[left:right]
    # Не даём HTML-комментариям с картинками доминировать в evidence.
    evidence = re.sub(r"<!--\s*image\s*-->", " ", evidence, flags=re.IGNORECASE)
    evidence = normalize_space(evidence)
    if len(evidence) > 420:
        evidence = evidence[:417].rstrip() + "..."
    return left, min(len(text), left + len(evidence))


def compile_trigger(trigger: str) -> re.Pattern[str]:
    # Триггеры задаются как обычные фразы. Пробелы допускают переносы и несколько пробелов.
    body = re.escape(trigger).replace(r"\ ", r"\s+")
    return re.compile(body, re.IGNORECASE | re.UNICODE)


TRIGGER_CACHE = {trigger: compile_trigger(trigger) for p in RELATION_PATTERNS for trigger in p.triggers}


def trigger_in_between(pattern: RelationPattern, between: str) -> str:
    for trigger in pattern.triggers:
        if TRIGGER_CACHE[trigger].search(between):
            return trigger
    return ""


def make_triple(text: str, a: EntityMention, b: EntityMention, predicate: str, trigger: str, confidence: float, rule: str) -> Triple:
    span_start = min(a.start, b.start)
    span_end = max(a.end, b.end)
    ev_start, ev_end = find_evidence_bounds(text, span_start, span_end)
    evidence = normalize_space(re.sub(r"<!--\s*image\s*-->", " ", text[ev_start:ev_end], flags=re.IGNORECASE))
    return Triple(
        subject_id=a.id,
        subject_text=a.surface,
        subject_type=a.entity_type,
        predicate=predicate,
        object_id=b.id,
        object_text=b.surface,
        object_type=b.entity_type,
        trigger=trigger,
        evidence=evidence,
        start=span_start,
        end=span_end,
        confidence=round(confidence, 3),
        rule=rule,
        object_value=b.value,
        object_unit=b.unit,
        object_operator=b.operator,
    )


def extract_pattern_triples(text: str, entities: list[EntityMention]) -> list[Triple]:
    triples: list[Triple] = []
    n = len(entities)
    for i in range(n):
        a = entities[i]
        for j in range(i + 1, n):
            b = entities[j]
            if b.start - a.end > 420:
                break
            between = text[a.end:b.start]
            # Не связываем сущности через границу разделов/абзацев: это главный источник ложных троек.
            if "##" in between or between.count("\n") >= 2 or ("\n" in between and len(between) > 120):
                continue
            between_norm = norm(between)
            if not between_norm:
                continue
            for pattern in RELATION_PATTERNS:
                if b.start - a.end > pattern.max_gap:
                    continue
                if not type_ok(a.entity_type, pattern.subject_types):
                    continue
                if not type_ok(b.entity_type, pattern.object_types):
                    continue
                trigger = trigger_in_between(pattern, between_norm)
                if not trigger:
                    continue
                confidence = pattern.confidence
                if a.source.startswith("ontology"):
                    confidence += 0.04
                if b.source.startswith("ontology"):
                    confidence += 0.04
                if a.value or b.value:
                    confidence += 0.02
                triples.append(make_triple(text, a, b, pattern.predicate, trigger, min(confidence, 0.98), f"trigger:{trigger}"))
    return triples


def extract_geography_triples(text: str, entities: list[EntityMention]) -> list[Triple]:
    triples: list[Triple] = []
    for i, a in enumerate(entities):
        if a.entity_type not in {"Organization", "Equipment"}:
            continue
        for b in entities[i + 1:i + 5]:
            if b.start - a.end > 70:
                break
            if b.entity_type != "Geography":
                continue
            gap = text[a.end:b.start]
            # Geokon (США), Sygra Pty Ltd ... (Австралия) — короткая геопривязка.
            if GEO_PAREN_GAP_RE.match(gap) or "(" in gap:
                pred = "located_in" if a.entity_type == "Organization" else "has_geography"
                triples.append(make_triple(text, a, b, pred, "география в скобках", 0.84, "adjacent_geo_parentheses"))
    return triples



def extract_person_marker_triples(text: str, entities: list[EntityMention]) -> list[Triple]:
    """Связать ФИО с ролью, степенью и подразделением в пределах одной строки."""
    triples: list[Triple] = []
    for person in entities:
        if person.entity_type != "Expert":
            continue
        line_start = text.rfind("\n", 0, person.start) + 1
        line_end = text.find("\n", person.end)
        if line_end == -1:
            line_end = len(text)
        local = [e for e in entities if line_start <= e.start < e.end <= line_end and e.id != person.id]
        for e in local:
            if e.end > person.start:
                continue
            if e.entity_type == "Role":
                triples.append(make_triple(text, person, e, "has_role", "маркер роли перед ФИО", 0.88, "person_line_role"))
            elif e.entity_type == "AcademicDegree":
                triples.append(make_triple(text, person, e, "has_degree", "учёная степень перед ФИО", 0.90, "person_line_degree"))
            elif e.entity_type == "OrgUnit":
                triples.append(make_triple(text, person, e, "affiliated_with", "подразделение в строке ФИО", 0.72, "person_line_org_unit"))
    return triples


def extract_org_unit_triples(text: str, entities: list[EntityMention]) -> list[Triple]:
    """Связать организацию и подразделение в заголовочной строке."""
    triples: list[Triple] = []
    for org in entities:
        if org.entity_type != "Organization":
            continue
        line_end = text.find("\n", org.end)
        if line_end == -1:
            line_end = len(text)
        for unit in entities:
            if unit.entity_type != "OrgUnit":
                continue
            if org.end <= unit.start <= line_end:
                gap = text[org.end:unit.start]
                if len(gap) <= 40 and ":" in gap:
                    triples.append(make_triple(text, org, unit, "has_unit", "двоеточие после организации", 0.86, "organization_header_unit"))
                    triples.append(make_triple(text, unit, org, "part_of", "двоеточие после организации", 0.86, "organization_header_unit_inverse"))
    return triples


def dedupe_triples(triples: list[Triple]) -> list[Triple]:
    best: dict[tuple[str, str, str, str, str], Triple] = {}
    for t in triples:
        key = (norm(t.subject_text), t.subject_type, t.predicate, norm(t.object_text), t.object_type)
        old = best.get(key)
        if old is None or t.confidence > old.confidence or len(t.evidence) < len(old.evidence):
            best[key] = t
    return sorted(best.values(), key=lambda t: (-t.confidence, t.start, t.predicate))


def write_csv(path: Path, triples: list[Triple]) -> None:
    fields = list(asdict(triples[0]).keys()) if triples else [
        "subject_id", "subject_text", "subject_type", "predicate", "object_id", "object_text",
        "object_type", "trigger", "evidence", "start", "end", "confidence", "rule",
        "object_value", "object_unit", "object_operator",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for t in triples:
            writer.writerow(asdict(t))


def write_json(path: Path, triples: list[Triple]) -> None:
    path.write_text(json.dumps([asdict(t) for t in triples], ensure_ascii=False, indent=2), encoding="utf-8")


def write_html(path: Path, triples: list[Triple], source_name: str) -> None:
    rows = []
    for idx, t in enumerate(triples, start=1):
        rows.append(f"""
<tr>
  <td>{idx}</td>
  <td><b>{html_escape(t.subject_text)}</b><br><span>{html_escape(t.subject_type)}</span></td>
  <td><code>{html_escape(t.predicate)}</code><br><span>{html_escape(t.trigger)}</span></td>
  <td><b>{html_escape(t.object_text)}</b><br><span>{html_escape(t.object_type)}</span></td>
  <td>{t.confidence:.2f}</td>
  <td>{html_escape(t.evidence)}</td>
</tr>""")
    body = "\n".join(rows) or '<tr><td colspan="6">Тройки не найдены.</td></tr>'
    html_doc = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8" />
<title>Simple relation triples</title>
<style>
body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin:0; background:#f8fafc; color:#0f172a; }}
header {{ background:#ffffffee; border-bottom:1px solid #e2e8f0; padding:16px 24px; }}
main {{ padding:24px; max-width:1400px; margin:auto; }}
table {{ border-collapse: collapse; width:100%; background:white; border:1px solid #e2e8f0; }}
th, td {{ border-bottom:1px solid #e2e8f0; padding:8px 10px; vertical-align:top; text-align:left; font-size:14px; }}
th {{ background:#f1f5f9; }}
code {{ background:#e2e8f0; padding:2px 4px; border-radius:4px; }}
span {{ color:#64748b; font-size:12px; }}
</style></head><body>
<header>
  <h1 style="margin:0;font-size:20px;">Простые тройки отношений</h1>
  <div style="color:#334155;font-size:14px;margin-top:4px;">{html_escape(source_name)} · найдено троек: {len(triples)}</div>
</header>
<main>
<table>
<thead><tr><th>#</th><th>Subject</th><th>Predicate / trigger</th><th>Object</th><th>Conf.</th><th>Evidence</th></tr></thead>
<tbody>{body}</tbody>
</table>
</main></body></html>"""
    path.write_text(html_doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--entities", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    entities = read_entities(args.entities)
    triples = []
    triples.extend(extract_pattern_triples(text, entities))
    triples.extend(extract_geography_triples(text, entities))
    triples.extend(extract_person_marker_triples(text, entities))
    triples.extend(extract_org_unit_triples(text, entities))
    triples = dedupe_triples(triples)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "triples_simple.csv", triples)
    write_json(args.out_dir / "triples_simple.json", triples)
    write_html(args.out_dir / "triples_simple.html", triples, args.input.name)
    summary = {
        "input": str(args.input),
        "entities": str(args.entities),
        "triples_total": len(triples),
        "by_predicate": {},
    }
    for t in triples:
        summary["by_predicate"][t.predicate] = summary["by_predicate"].get(t.predicate, 0) + 1
    (args.out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
