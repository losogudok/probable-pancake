#!/usr/bin/env python3
"""Ontology/entity highlighter: known ontology terms vs heuristic candidates.

No LLM.

It marks text spans in two levels:
  1) ontology-known: the span matches TermSpec canonical/alias from ontology2.py.
     Label format in HTML: "<EntityType>:<canonical>".
     Example: "Metric:НДС".
  2) heuristic-candidate: the span is guessed from candidate CSVs, but is not a
     registered ontology term. Label format: "<EntityType>" only.
     Example: "Process".

This supports the workflow:
  known ontology coverage + gaps for ontology extension.

Inputs:
  - input markdown/text file
  - ontology2.py-style module with DEFAULT_REGISTRY
  - optional phrase_candidates.csv from ontology_word_inventory.py
  - optional unique_words_entity_guesses.csv from ontology_word_inventory.py

Outputs:
  - highlighted_entities.html
  - entity_matches.csv
  - entity_highlight_stats.json
  - ontology_gap_candidates.csv

Also extracts simple ontology-known parameter value mentions, for example:
  "на глубину 10 м" -> "Parameter:глубина=10 м"

Usage:
  python ontology_entity_highlighter.py "НДС Комсомольский.md" \
    --ontology ontology2.py \
    --phrases nds_ontology_inventory/phrase_candidates.csv \
    --words nds_ontology_inventory/unique_words_entity_guesses.csv \
    --out-dir nds_entity_highlight
"""
from __future__ import annotations

import argparse
import csv
import html
import importlib.util
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Candidate:
    text: str
    entity_type: str
    source: str  # ontology | heuristic_phrase | heuristic_word
    canonical: str = ""
    term_id: str = ""
    domain: str = ""
    match_policy: str = ""
    confidence: float = 0.0
    count: int = 0


@dataclass(frozen=True)
class Match:
    start: int
    end: int
    surface: str
    entity_type: str
    source: str
    canonical: str = ""
    term_id: str = ""
    domain: str = ""
    match_policy: str = ""
    confidence: float = 0.0
    count: int = 0
    value: str = ""
    unit: str = ""

    @property
    def specificity(self) -> str:
        return "specific" if self.source.startswith("ontology") else "generic"

    @property
    def display_label(self) -> str:
        if self.source.startswith("ontology") and self.canonical:
            if self.value:
                unit_part = f" {self.unit}" if self.unit else ""
                return f"{self.entity_type}:{self.canonical}={self.value}{unit_part}"
            return f"{self.entity_type}:{self.canonical}"
        return self.entity_type


COLOR_BY_TYPE = {
    "Document": "#7c3aed",
    "SourceSpan": "#64748b",
    "Claim": "#334155",
    "Material": "#f59e0b",
    "Chemical": "#d97706",
    "Process": "#0ea5e9",
    "Equipment": "#8b5cf6",
    "Facility": "#14b8a6",
    "Experiment": "#2563eb",
    "Publication": "#6366f1",
    "Patent": "#7c3aed",
    "Property": "#10b981",
    "Parameter": "#84cc16",
    "Condition": "#65a30d",
    "Metric": "#22c55e",
    "Result": "#059669",
    "Expert": "#ec4899",
    "Organization": "#db2777",
    "Recommendation": "#e11d48",
    "Technology": "#f97316",
    "Method": "#06b6d4",
    "Model": "#0891b2",
    "Risk": "#dc2626",
    "EngineeringSolution": "#ea580c",
    "MineObject": "#78350f",
    "RockMass": "#78716c",
    "GeologicalFeature": "#92400e",
}

# Standalone tokens that are usually too ambiguous to mark without context.
STOP_ALIASES = {
    "q", "в", "a", "с", "м", "t", "%", "cell", "level", "shaft", "stope",
    "печь", "ванна", "скорость", "степень", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
}

STOP_HEURISTIC_WORDS = {
    "введение", "image", "рисунок", "слайд", "пример", "данные", "работы", "работ", "момент",
    "метод", "процесс", "результаты", "анализ", "обзор", "оценка", "определение", "проведения",
    "использованием", "применением", "основе", "состояния", "различных",
}

VALID_TYPES = set(COLOR_BY_TYPE)


def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("ё", "е").replace("Ё", "Е")
    s = s.replace("–", "-").replace("—", "-").replace("−", "-")
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def load_ontology_module(path: Path) -> Any:
    path = path.resolve()
    spec = importlib.util.spec_from_file_location("_ontology_runtime_entity", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import ontology module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def registry_from_module(module: Any) -> Any:
    if hasattr(module, "DEFAULT_REGISTRY"):
        return module.DEFAULT_REGISTRY
    if hasattr(module, "build_default_registry"):
        return module.build_default_registry()
    raise RuntimeError("Ontology module must expose DEFAULT_REGISTRY or build_default_registry()")


def collect_ontology_candidates(registry: Any, domains: set[str] | None) -> list[Candidate]:
    out: list[Candidate] = []
    for term in registry.terms.values():
        if domains is not None and term.domain not in domains and term.domain != "common":
            continue
        for alias in term.all_names():
            alias = alias.strip()
            if not alias:
                continue
            if norm_text(alias) in STOP_ALIASES:
                continue
            out.append(Candidate(
                text=alias,
                entity_type=str(term.type),
                source="ontology",
                canonical=str(term.canonical),
                term_id=str(term.id),
                domain=str(term.domain),
                match_policy=str(term.match),
                confidence=1.0,
                count=0,
            ))
    return out


def russian_single_word_forms_regex(term: str) -> str:
    """Very small non-LLM morphology helper for common Russian parameter mentions.

    It is deliberately conservative: only single Cyrillic words get generated
    endings. This is enough to match depth -> глубина/глубину/глубине/глубинах.
    """
    t = term.strip()
    if not re.fullmatch(r"[А-Яа-яЁё]{4,}", t):
        return re.escape(t)
    low = t.lower().replace("ё", "е")
    # Common feminine nouns ending with -а, such as глубина.
    if low.endswith("а"):
        root = re.escape(t[:-1])
        return root + r"(?:а|у|е|ой|ы|ах|ам|ами)?"
    # Common masculine/neuter fallback: exact or simple plural/prepositional tails.
    root = re.escape(t)
    return root + r"(?:а|у|ом|е|ы|ов|ах|ам|ами)?"


def unit_regex_from_ontology(module: Any) -> str:
    units = list(getattr(module, "UNIT_PATTERNS", set()))
    # Exclude one-letter Latin/cyrillic electric units that cause noise; keep м/m.
    units = [u for u in units if u and u.lower() not in {"в", "v", "а", "a", "с"}]
    units.sort(key=len, reverse=True)
    escaped = [re.escape(u).replace(r"\ ", r"\s+") for u in units]
    return r"(?:" + "|".join(escaped) + r")"


def collect_parameter_value_matches(text: str, registry: Any, module: Any, domains: set[str] | None) -> list[Match]:
    """Find simple typed parameter-value spans for known ontology parameters.

    Example: ontology has canonical "глубина". Text has "на глубину 10 м".
    Output label becomes "Parameter:глубина=10 м".
    """
    unit_rx = unit_regex_from_ontology(module)
    if not unit_rx or unit_rx == r"(?:)":
        return []
    number_rx = r"(?P<value>\d+(?:\s*[,.]\s*\d+)?(?:\s*[-–—−]\s*\d+(?:\s*[,.]\s*\d+)?)?)"
    word = r"[A-Za-zА-Яа-яЁё0-9_\-]+"
    matches: list[Match] = []

    for term in registry.terms.values():
        if domains is not None and term.domain not in domains and term.domain != "common":
            continue
        if str(term.type) not in {"Parameter", "Metric", "Property", "Condition"}:
            continue
        aliases = [a for a in term.all_names() if a and norm_text(a) not in STOP_ALIASES]
        if not aliases:
            continue
        alias_pats = [russian_single_word_forms_regex(a) for a in aliases]
        alias_rx = r"(?:" + "|".join(alias_pats) + r")"
        # Optional preposition before parameter and up to 3 filler words between term and number.
        # Covers: "на глубину 10 м", "глубина скважины 10 м", "на глубинах скважины 9-12 м".
        pat = re.compile(
            rf"(?<![A-Za-zА-Яа-я0-9])"
            rf"(?P<span>(?:(?:на|при|до|от|с|в)\s+)?{alias_rx}"
            rf"(?:\s+{word}){{0,3}}?\s+{number_rx}\s*(?P<unit>{unit_rx}))"
            rf"(?![A-Za-zА-Яа-я0-9])",
            re.IGNORECASE | re.UNICODE,
        )
        for m in pat.finditer(text):
            raw_value = re.sub(r"\s+", "", m.group("value")).replace(",", ".")
            raw_unit = m.group("unit")
            matches.append(Match(
                start=m.start("span"),
                end=m.end("span"),
                surface=m.group("span"),
                entity_type=str(term.type),
                source="ontology_value",
                canonical=str(term.canonical),
                term_id=str(term.id),
                domain=str(term.domain),
                match_policy="parameter_value",
                confidence=1.0,
                count=0,
                value=raw_value,
                unit=raw_unit,
            ))
    return matches


def load_phrase_candidates(path: Path | None, *, min_count: int = 2) -> list[Candidate]:
    if path is None or not path.exists():
        return []
    out: list[Candidate] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            phrase = (row.get("phrase") or "").strip()
            typ = (row.get("entity_type_guess") or "").strip()
            try:
                count = int(float(row.get("count") or "0"))
            except ValueError:
                count = 0
            if not phrase or typ not in VALID_TYPES or count < min_count:
                continue
            if len(norm_text(phrase)) < 4:
                continue
            if norm_text(phrase) in STOP_HEURISTIC_WORDS:
                continue
            out.append(Candidate(
                text=phrase,
                entity_type=typ,
                source="heuristic_phrase",
                confidence=0.55,
                count=count,
            ))
    return out


def load_word_candidates(path: Path | None, *, min_confidence: float = 0.65, min_count: int = 1) -> list[Candidate]:
    if path is None or not path.exists():
        return []
    out: list[Candidate] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            surface = (row.get("term") or row.get("normalized") or "").strip()
            normalized = (row.get("normalized") or surface).strip()
            typ = (row.get("entity_type_guess") or "").strip()
            try:
                conf = float(row.get("confidence") or "0")
            except ValueError:
                conf = 0.0
            try:
                count = int(float(row.get("count") or "0"))
            except ValueError:
                count = 0
            if typ not in VALID_TYPES or conf < min_confidence or count < min_count:
                continue
            key = norm_text(normalized or surface)
            if not key or key in STOP_ALIASES or key in STOP_HEURISTIC_WORDS:
                continue
            if len(key) < 4 and not re.search(r"[A-ZА-Я]{2,}", surface):
                continue
            # Prefer normalized as matching string if it is not a pure number.
            text = normalized or surface
            if re.fullmatch(r"\d+(?:[,.]\d+)?", text):
                continue
            out.append(Candidate(
                text=text,
                entity_type=typ,
                source="heuristic_word",
                confidence=conf,
                count=count,
            ))
    return out


def build_pattern(text: str, match_policy: str = "") -> re.Pattern[str] | None:
    s = text.strip()
    if not s:
        return None
    if len(norm_text(s)) <= 1:
        return None
    escaped = re.escape(s)
    escaped = escaped.replace(r"\ ", r"\s+")
    escaped = escaped.replace(r"\-", r"[-–—−]")
    # tolerant spaces around hyphens in converted PDFs/markdown
    escaped = re.sub(r"\\s\+\[\-–—−\]", r"\\s*[-–—−]\\s*", escaped)
    pattern = rf"(?<![A-Za-zА-Яа-я0-9]){escaped}(?![A-Za-zА-Яа-я0-9])"
    return re.compile(pattern, re.IGNORECASE | re.UNICODE)


def find_raw_matches(text: str, candidates: list[Candidate]) -> list[Match]:
    raw: list[Match] = []
    seen_candidates = set()
    for c in candidates:
        key = (norm_text(c.text), c.entity_type, c.source, c.term_id)
        if key in seen_candidates:
            continue
        seen_candidates.add(key)
        if c.match_policy == "context_required" and len(norm_text(c.text)) < 4:
            continue
        pat = build_pattern(c.text, c.match_policy)
        if pat is None:
            continue
        for m in pat.finditer(text):
            raw.append(Match(
                start=m.start(),
                end=m.end(),
                surface=text[m.start():m.end()],
                entity_type=c.entity_type,
                source=c.source,
                canonical=c.canonical,
                term_id=c.term_id,
                domain=c.domain,
                match_policy=c.match_policy,
                confidence=c.confidence,
                count=c.count,
            ))
    return raw


def resolve_overlaps(raw: list[Match]) -> list[Match]:
    def priority(m: Match) -> tuple[int, int, float, int]:
        # Higher is better: ontology over heuristic, longer spans, confidence, count.
        source_score = {"ontology_value": 4, "ontology": 3, "heuristic_phrase": 2, "heuristic_word": 1}.get(m.source, 0)
        return (source_score, m.end - m.start, m.confidence, m.count)

    # Sort by best first, then accept non-overlapping. This lets known ontology terms
    # win over broad heuristic phrases. Then output sorted by position.
    raw_sorted = sorted(raw, key=lambda m: (*priority(m), -m.start), reverse=True)
    accepted: list[Match] = []
    intervals: list[tuple[int, int]] = []
    for m in raw_sorted:
        if any(not (m.end <= s or m.start >= e) for s, e in intervals):
            continue
        accepted.append(m)
        intervals.append((m.start, m.end))
    return sorted(accepted, key=lambda m: m.start)


def context(text: str, start: int, end: int, window: int = 100) -> str:
    s = max(0, start - window)
    e = min(len(text), end + window)
    return re.sub(r"\s+", " ", text[s:e]).strip()


def write_matches_csv(path: Path, source_text: str, matches: list[Match]) -> None:
    fieldnames = [
        "start", "end", "surface", "display_label", "specificity", "entity_type", "source",
        "canonical", "term_id", "domain", "match_policy", "value", "unit", "confidence", "count", "context",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for m in matches:
            w.writerow({
                "start": m.start,
                "end": m.end,
                "surface": m.surface,
                "display_label": m.display_label,
                "specificity": m.specificity,
                "entity_type": m.entity_type,
                "source": m.source,
                "canonical": m.canonical,
                "term_id": m.term_id,
                "domain": m.domain,
                "match_policy": m.match_policy,
                "value": m.value,
                "unit": m.unit,
                "confidence": m.confidence,
                "count": m.count,
                "context": context(source_text, m.start, m.end),
            })


def write_gap_csv(path: Path, matches: list[Match]) -> None:
    rows = [m for m in matches if m.source != "ontology"]
    counter = Counter((norm_text(m.surface), m.surface, m.entity_type, m.source) for m in rows)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["candidate", "entity_type", "source", "matches", "suggested_action"])
        w.writeheader()
        for (_, surface, typ, source), cnt in counter.most_common():
            w.writerow({
                "candidate": surface,
                "entity_type": typ,
                "source": source,
                "matches": cnt,
                "suggested_action": f"review: add TermSpec as {typ} if meaningful",
            })



def write_known_entities_csv(path: Path, source_text: str, matches: list[Match]) -> None:
    """Write only ontology-registered concrete entities grouped by term_id/surface."""
    rows = [m for m in matches if m.source.startswith("ontology")]
    grouped: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for m in rows:
        key = (m.term_id, m.display_label, m.entity_type, m.canonical, m.domain)
        g = grouped.setdefault(key, {
            "term_id": m.term_id,
            "display_label": m.display_label,
            "entity_type": m.entity_type,
            "canonical": m.canonical,
            "domain": m.domain,
            "matches": 0,
            "surface_forms": set(),
            "example_context": "",
        })
        g["matches"] += 1
        g["surface_forms"].add(m.surface)
        if not g["example_context"]:
            g["example_context"] = context(source_text, m.start, m.end)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["term_id", "display_label", "entity_type", "canonical", "domain", "matches", "surface_forms", "example_context"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in sorted(grouped.values(), key=lambda r: (-r["matches"], r["display_label"])):
            out = dict(row)
            out["surface_forms"] = "; ".join(sorted(out["surface_forms"]))
            w.writerow(out)

def write_html(path: Path, source_text: str, matches: list[Match], stats: dict[str, Any]) -> None:
    parts: list[str] = []
    pos = 0
    for m in matches:
        parts.append(html.escape(source_text[pos:m.start]))
        color = COLOR_BY_TYPE.get(m.entity_type, "#475569")
        specific = m.source.startswith("ontology")
        border_style = "solid" if specific else "dashed"
        background = f"{color}26" if specific else f"{color}12"
        title = (
            f"{m.display_label}\n"
            f"source={m.source}\n"
            f"specificity={m.specificity}\n"
            f"canonical={m.canonical}\n"
            f"term_id={m.term_id}\n"
            f"confidence={m.confidence}"
        )
        tag_extra = "known" if specific else "candidate"
        parts.append(
            f'<mark class="ent {tag_extra}" '
            f'style="background:{background};border-bottom:2px {border_style} {color};" '
            f'title="{html.escape(title)}">{html.escape(source_text[m.start:m.end])}'
            f'<span class="tag" style="background:{color};">{html.escape(m.display_label)}</span></mark>'
        )
        pos = m.end
    parts.append(html.escape(source_text[pos:]))
    body = "".join(parts)

    by_type_items = "\n".join(
        f'<span class="legend-item"><span class="swatch" style="background:{COLOR_BY_TYPE.get(t, "#475569")};"></span>{html.escape(t)}: {c}</span>'
        for t, c in stats["by_type"].items()
    )
    known_labels = ", ".join(html.escape(label) + f" ×{count}" for label, count in stats.get("top_known_labels", [])[:20]) or "none"

    html_doc = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8" />
<title>Entity ontology highlight</title>
<style>
body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; line-height:1.55; margin:0; background:#f8fafc; color:#0f172a; }}
header {{ position: sticky; top:0; background:#ffffffee; backdrop-filter: blur(8px); border-bottom:1px solid #e2e8f0; padding:16px 24px; z-index:2; }}
main {{ padding:24px; max-width:1200px; margin:auto; }}
pre {{ white-space:pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:14px; background:white; padding:24px; border:1px solid #e2e8f0; border-radius:12px; }}
mark.ent {{ padding:1px 3px; border-radius:4px; color:inherit; }}
mark.known {{ box-shadow: inset 0 -1px 0 rgba(15,23,42,.08); }}
mark.candidate {{ opacity:.92; }}
.tag {{ color:white; font-size:9px; padding:1px 3px; border-radius:3px; margin-left:3px; vertical-align:10%; font-family:system-ui; font-weight:600; }}
.legend {{ display:flex; flex-wrap:wrap; gap:8px 14px; margin-top:10px; }}
.legend-item {{ font-size:13px; }}
.swatch {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; }}
.stats {{ font-size:14px; color:#334155; }}
.mode {{ display:inline-block; padding:2px 6px; border-radius:999px; border:1px solid #cbd5e1; font-size:12px; margin-right:8px; }}
.known-list {{ margin-top:8px; font-size:13px; color:#0f172a; }}
</style></head><body>
<header>
  <h1 style="margin:0 0 6px 0;font-size:20px;">Entity ontology highlighting, no LLM</h1>
  <div class="stats">
    Matches: {stats['matches_total']} · known ontology: {stats['known_matches']} · heuristic candidates: {stats['candidate_matches']} · unique known terms: {stats['unique_known_terms']}
  </div>
  <div style="margin-top:8px;"><span class="mode">solid underline = EntityType:canonical</span><span class="mode">dashed underline = generic EntityType candidate</span></div>
  <div class="known-list"><b>Known entities:</b> {known_labels}</div>
  <div class="legend">{by_type_items}</div>
</header>
<main><pre>{body}</pre></main>
</body></html>"""
    path.write_text(html_doc, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--ontology", type=Path, required=True)
    ap.add_argument("--phrases", type=Path)
    ap.add_argument("--words", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--domains", default="common,underground_mining")
    ap.add_argument("--word-min-confidence", type=float, default=0.65)
    ap.add_argument("--phrase-min-count", type=int, default=2)
    args = ap.parse_args()

    text = args.input.read_text(encoding="utf-8")
    module = load_ontology_module(args.ontology)
    registry = registry_from_module(module)
    domains = {d.strip() for d in args.domains.split(",") if d.strip()} if args.domains else None

    ontology_candidates = collect_ontology_candidates(registry, domains)
    phrase_candidates = load_phrase_candidates(args.phrases, min_count=args.phrase_min_count)
    word_candidates = load_word_candidates(args.words, min_confidence=args.word_min_confidence)

    ontology_alias_keys = {norm_text(c.text) for c in ontology_candidates}
    # Do not add heuristic candidates that are exact aliases already in ontology.
    heuristic_candidates = [c for c in phrase_candidates + word_candidates if norm_text(c.text) not in ontology_alias_keys]

    value_matches = collect_parameter_value_matches(text, registry, module, domains)
    raw = find_raw_matches(text, ontology_candidates + heuristic_candidates) + value_matches
    matches = resolve_overlaps(raw)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_matches_csv(args.out_dir / "entity_matches.csv", text, matches)
    write_known_entities_csv(args.out_dir / "known_entities.csv", text, matches)
    write_gap_csv(args.out_dir / "ontology_gap_candidates.csv", matches)

    stats = {
        "input": str(args.input),
        "ontology": str(args.ontology),
        "matches_total": len(matches),
        "known_matches": sum(1 for m in matches if m.source.startswith("ontology")),
        "candidate_matches": sum(1 for m in matches if not m.source.startswith("ontology")),
        "unique_known_terms": len({m.term_id for m in matches if m.source.startswith("ontology")}),
        "ontology_candidates_loaded": len(ontology_candidates),
        "heuristic_candidates_loaded": len(heuristic_candidates),
        "ontology_value_matches_raw": len(value_matches),
        "by_type": dict(Counter(m.entity_type for m in matches).most_common()),
        "by_source": dict(Counter(m.source for m in matches).most_common()),
        "top_labels": Counter(m.display_label for m in matches).most_common(40),
        "top_known_labels": Counter(m.display_label for m in matches if m.source.startswith("ontology")).most_common(40),
        "top_candidate_labels": Counter(m.display_label for m in matches if not m.source.startswith("ontology")).most_common(40),
    }
    (args.out_dir / "entity_highlight_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    write_html(args.out_dir / "highlighted_entities.html", text, matches, stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
