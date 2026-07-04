#!/usr/bin/env python3
"""
ontology_word_inventory.py

Small helper for ontology bootstrapping from a Markdown/text document.

It does NOT try to build the final graph. It prepares a reviewable inventory:
- unique word/token list with counts, contexts and heuristic entity-type guesses;
- phrase candidates, because ontology objects are often multi-word spans;
- a compact Markdown report.

Usage:
    python ontology_word_inventory.py input.md --out out_dir

Optional:
    python ontology_word_inventory.py input.md --out out_dir --min-count 2
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable


class EntityType(str, Enum):
    # Evidence / RAG layer
    DOCUMENT = "Document"
    SOURCE_SPAN = "SourceSpan"
    CLAIM = "Claim"

    # Original mining-metallurgy core
    MATERIAL = "Material"
    PROCESS = "Process"
    EQUIPMENT = "Equipment"
    FACILITY = "Facility"
    EXPERIMENT = "Experiment"
    PUBLICATION = "Publication"
    PATENT = "Patent"
    PROPERTY = "Property"
    PARAMETER = "Parameter"
    EXPERT = "Expert"
    ORGANIZATION = "Organization"
    RECOMMENDATION = "Recommendation"
    TECHNOLOGY = "Technology"
    METHOD = "Method"
    RESULT = "Result"
    CHEMICAL = "Chemical"
    CONDITION = "Condition"

    # Useful generic extensions
    MODEL = "Model"
    METRIC = "Metric"
    RISK = "Risk"
    ENGINEERING_SOLUTION = "EngineeringSolution"

    # Underground mining / geomechanics extension
    MINE_OBJECT = "MineObject"
    ROCK_MASS = "RockMass"
    GEOLOGICAL_FEATURE = "GeologicalFeature"


# Intentionally small. Extend from ontology modules later.
DOMAIN_LEXICON: dict[EntityType, set[str]] = {
    EntityType.MATERIAL: {
        "керн", "керна", "образец", "образца", "порода", "пород", "руда", "руды",
        "полезных", "ископаемых",
    },
    EntityType.ROCK_MASS: {
        "массив", "массива", "пород", "трещиноватость", "трещиноватости",
    },
    EntityType.PROCESS: {
        "бурение", "разгрузка", "разгрузки", "обуривание", "разбуривание", "проходка",
        "проходке", "измерение", "измерений", "измерения", "тарировка", "моделирование",
        "полимеризации", "отбор", "установка", "контроль", "анализ", "интерпретация",
    },
    EntityType.METHOD: {
        "overcoring", "dra", "hydrofracturing", "isrm", "astm", "fidesys", "метод", "метода",
        "методы", "методов", "гидроразрыва", "гидродомкратов", "кирша",
    },
    EntityType.EQUIPMENT: {
        "экстензометр", "экстензометра", "экстензометров", "деформометр", "деформометра",
        "тензодатчик", "тензодатчиков", "датчик", "датчиков", "lvdt", "usbm", "cell",
        "zetlab", "zett901", "geokon", "видеоэндоскоп", "тензостанция", "коронка", "коронки",
        "станок", "став", "сальник", "вертлюг", "шпур", "шпура",
    },
    EntityType.MINE_OBJECT: {
        "рудник", "рудника", "выработка", "выработки", "скважина", "скважины", "скважин",
        "шпур", "шпура", "месторождение", "месторождения", "горизонт", "горизонтов",
        "талнахского", "норильского", "рудного", "узла",
    },
    EntityType.GEOLOGICAL_FEATURE: {
        "нхр", "горсты", "грабены", "нарушения", "разрывные", "складчато", "надвиговых",
        "поясов", "структура", "структур", "блоковые", "литолого", "структурной",
    },
    EntityType.PROPERTY: {
        "ндс", "напряжение", "напряжений", "напряжения", "деформация", "деформаций",
        "перемещения", "перемещений", "тензор", "тензора", "состояние", "состояния",
    },
    EntityType.PARAMETER: {
        "глубина", "глубины", "диаметр", "диаметром", "мм", "см", "м", "мпа", "па", "радиус",
        "радиусов", "температура", "время", "шаг", "этапов",
    },
    EntityType.CONDITION: {
        "высокие", "критических", "пластических", "влияния", "концентраций", "литостатическим",
        "горизонтальных", "сжимающих",
    },
    EntityType.RESULT: {
        "результат", "результаты", "результатов", "вывод", "выводы", "пик", "отсутствие",
        "разрушению", "дискование", "дисковании",
    },
    EntityType.MODEL: {
        "модель", "модели", "моделирования", "численное", "конечных", "элементов", "cae",
    },
    EntityType.ORGANIZATION: {
        "ооо", "институт", "гипроникель", "geokon", "sygra", "pty", "ltd", "россия", "сша",
        "австралия", "департамент", "лаборатория", "лабораторией",
    },
    EntityType.EXPERT: {
        "трофимов", "докладчик", "заведующий", "к.т.н", "gray", "ian",
    },
    EntityType.RECOMMENDATION: {
        "рекомендации", "рекомендован", "необходимо", "оптимальной", "предпочтительным",
    },
    EntityType.TECHNOLOGY: {
        "технология", "технологии", "геомеханических", "геологоразведочного",
    },
}

RU_STOPWORDS = {
    "а", "без", "более", "бы", "был", "была", "были", "было", "в", "во", "все", "всех",
    "где", "да", "для", "до", "его", "ее", "если", "есть", "еще", "же", "за", "здесь",
    "и", "из", "или", "им", "их", "к", "как", "ко", "на", "над", "не", "нет", "но", "о", "об",
    "от", "по", "под", "при", "с", "со", "так", "также", "то", "у", "чем", "что", "это",
    "этого", "этой", "этом", "этот", "является", "являются", "который", "которая", "которые",
    "которых", "далее", "данных", "данные", "порядка", "наиболее", "момент", "сегодняшний",
}

EN_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "in", "is", "of", "on", "or",
    "the", "to", "with", "method", "standard", "test", "tool",
}

STOPWORDS = RU_STOPWORDS | EN_STOPWORDS

# Cyrillic, Latin, digits, Greek sigma, internal separators. Keeps things like ASTM, D4623-2016, ZETT901, σ1.
TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁёΣσ0-9]+(?:[.\-–—_/][A-Za-zА-Яа-яЁёΣσ0-9]+)*", re.UNICODE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。])\s+|\n+")


def normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("ё", "е").replace("Ё", "Е")
    # Drop markdown image placeholders and HTML comments.
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    # Drop markdown heading/list markers but keep content.
    text = re.sub(r"^[#>*\-]+\s*", "", text, flags=re.MULTILINE)
    return text


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def norm_token(token: str) -> str:
    return token.strip("._-–—/").lower()


def classify_token(token: str) -> tuple[str, float, str, str]:
    """Return entity_type, confidence, reason, action."""
    raw = token.strip()
    t = norm_token(raw)
    if not t:
        return "", 0.0, "empty", "drop"

    if t in STOPWORDS:
        return "", 0.0, "stopword", "drop"

    # Numeric-only tokens are usually parameters only when context/units are known.
    if re.fullmatch(r"\d+(?:[.,]\d+)?", t):
        return EntityType.PARAMETER.value, 0.35, "number; needs nearby unit/context", "review"

    # Units and stress symbols.
    if t in {"мм", "см", "м", "мпа", "па", "k", "h", "min", "м3", "σ1", "σ2", "σ3"} or re.fullmatch(r"σ\d+", t):
        return EntityType.PARAMETER.value, 0.85, "known unit/stress-symbol", "keep_candidate"

    # Organization-like all caps / standards.
    if raw.isupper() and len(raw) >= 2:
        if t in {"ндс"}:
            return EntityType.PROPERTY.value, 0.9, "domain abbreviation: stress-strain state", "keep_candidate"
        if t in {"ооо", "isrm", "astm", "cae", "usbm", "hq"}:
            if t in {"isrm", "astm"}:
                return EntityType.METHOD.value, 0.75, "standard/method abbreviation", "keep_candidate"
            return EntityType.ORGANIZATION.value if t == "ооо" else EntityType.EQUIPMENT.value, 0.65, "uppercase abbreviation", "review"

    # Dictionary pass.
    hits: list[tuple[EntityType, float]] = []
    for etype, words in DOMAIN_LEXICON.items():
        if t in words:
            hits.append((etype, 0.85))

    if hits:
        # Prefer more specific mining extension labels over generic ones for collisions.
        priority = [
            EntityType.MINE_OBJECT,
            EntityType.ROCK_MASS,
            EntityType.GEOLOGICAL_FEATURE,
            EntityType.EQUIPMENT,
            EntityType.METHOD,
            EntityType.PROCESS,
            EntityType.PROPERTY,
            EntityType.PARAMETER,
            EntityType.ORGANIZATION,
            EntityType.EXPERT,
            EntityType.RESULT,
        ]
        hits.sort(key=lambda x: priority.index(x[0]) if x[0] in priority else 999)
        etype, conf = hits[0]
        also = [h[0].value for h in hits[1:]]
        reason = "dictionary match" + (f"; also: {', '.join(also)}" if also else "")
        return etype.value, conf, reason, "keep_candidate"

    # Simple morphological cues.
    if t.endswith(("ость", "ости")):
        return EntityType.PROPERTY.value, 0.45, "Russian abstract/property-like suffix; weak cue", "review"
    if t.endswith(("ирование", "ения", "ение")):
        return EntityType.PROCESS.value, 0.4, "process-like nominalization; weak cue", "review"

    return "", 0.0, "unknown", "review"


def sentence_contexts(text: str, tokens: Iterable[str], max_contexts: int = 3) -> dict[str, list[str]]:
    sents = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    wanted = {norm_token(t) for t in tokens}
    out: dict[str, list[str]] = {t: [] for t in wanted}
    for sent in sents:
        sent_tokens = {norm_token(t) for t in tokenize(sent)}
        for t in wanted & sent_tokens:
            if len(out[t]) < max_contexts:
                out[t].append(re.sub(r"\s+", " ", sent)[:320])
    return out


def phrase_candidates(text: str, max_n: int = 5) -> Counter[str]:
    """Generate rough phrase candidates from adjacent non-stopword tokens."""
    counts: Counter[str] = Counter()
    for sent in SENTENCE_SPLIT_RE.split(text):
        toks = [tok for tok in tokenize(sent) if norm_token(tok) and norm_token(tok) not in STOPWORDS]
        if len(toks) < 2:
            continue
        for n in range(2, max_n + 1):
            for i in range(0, len(toks) - n + 1):
                window = toks[i : i + n]
                # Keep phrases with at least one domain-like or capitalized token.
                cls = [classify_token(w)[0] for w in window]
                if any(cls) or any(w[:1].isupper() for w in window):
                    phrase = " ".join(window)
                    if len(phrase) >= 5:
                        counts[phrase] += 1
    return counts


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def analyze_file(input_path: Path, out_dir: Path, min_count: int = 1) -> dict[str, object]:
    raw = input_path.read_text(encoding="utf-8")
    text = normalize_text(raw)
    tokens = tokenize(text)
    norm_counts = Counter(norm_token(t) for t in tokens if norm_token(t))
    display: dict[str, str] = {}
    for t in tokens:
        nt = norm_token(t)
        if nt and nt not in display:
            display[nt] = t

    contexts = sentence_contexts(text, display.values(), max_contexts=3)

    word_rows: list[dict[str, object]] = []
    for nt in sorted(norm_counts, key=lambda x: x.casefold()):
        count = norm_counts[nt]
        if count < min_count:
            continue
        token = display.get(nt, nt)
        etype, conf, reason, action = classify_token(token)
        word_rows.append(
            {
                "term": token,
                "normalized": nt,
                "count": count,
                "entity_type_guess": etype,
                "confidence": conf,
                "action": action,
                "reason": reason,
                "contexts": " | ".join(contexts.get(nt, [])),
            }
        )

    phrase_counts = phrase_candidates(text)
    phrase_rows: list[dict[str, object]] = []
    for phrase, count in phrase_counts.most_common(500):
        low = phrase.lower()
        # Avoid huge amount of noisy singleton phrases; keep repeated or clearly domain phrases.
        if count < 2 and not any(k in low for k in ["метод", "ндс", "керн", "скваж", "массив", "напряж", "экстенз", "модел"]):
            continue
        # Guess by strongest token inside phrase.
        guesses = [classify_token(tok)[0] for tok in tokenize(phrase)]
        guess_counts = Counter(g for g in guesses if g)
        etype = guess_counts.most_common(1)[0][0] if guess_counts else ""
        phrase_rows.append(
            {
                "phrase": phrase,
                "count": count,
                "entity_type_guess": etype,
                "notes": "phrase candidate; needs manual/LLM review",
            }
        )

    by_type: dict[str, int] = defaultdict(int)
    for r in word_rows:
        if r["entity_type_guess"]:
            by_type[str(r["entity_type_guess"])] += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    words_csv = out_dir / "unique_words_entity_guesses.csv"
    phrases_csv = out_dir / "phrase_candidates.csv"
    summary_json = out_dir / "summary.json"
    report_md = out_dir / "report.md"

    write_csv(
        words_csv,
        word_rows,
        ["term", "normalized", "count", "entity_type_guess", "confidence", "action", "reason", "contexts"],
    )
    write_csv(phrases_csv, phrase_rows, ["phrase", "count", "entity_type_guess", "notes"])

    summary = {
        "input": str(input_path),
        "token_count": len(tokens),
        "unique_word_count": len(word_rows),
        "phrase_candidate_count": len(phrase_rows),
        "entity_type_guess_counts": dict(sorted(by_type.items(), key=lambda x: (-x[1], x[0]))),
        "outputs": {
            "words_csv": str(words_csv),
            "phrases_csv": str(phrases_csv),
            "report_md": str(report_md),
        },
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Compact report with top candidates.
    lines = [
        f"# Ontology word inventory report",
        "",
        f"Input: `{input_path.name}`",
        "",
        f"- Tokens: {len(tokens)}",
        f"- Unique words emitted: {len(word_rows)}",
        f"- Phrase candidates emitted: {len(phrase_rows)}",
        "",
        "## Guessed entity type counts",
        "",
    ]
    for k, v in summary["entity_type_guess_counts"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Top word candidates by entity type", ""]
    for etype in sorted(by_type):
        rows = [r for r in word_rows if r["entity_type_guess"] == etype and r["action"] != "drop"]
        rows = sorted(rows, key=lambda r: (-int(r["count"]), str(r["term"]).casefold()))[:20]
        if not rows:
            continue
        lines += [f"### {etype}", "", "| term | count | reason |", "|---|---:|---|"]
        for r in rows:
            reason = str(r["reason"]).replace("|", "/")
            lines.append(f"| {r['term']} | {r['count']} | {reason} |")
        lines.append("")
    lines += ["## Top phrase candidates", "", "| phrase | count | guess |", "|---|---:|---|"]
    for r in phrase_rows[:80]:
        phrase = str(r["phrase"]).replace("|", "/")
        lines.append(f"| {phrase} | {r['count']} | {r['entity_type_guess']} |")
    report_md.write_text("\n".join(lines), encoding="utf-8")

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract unique words and heuristic ontology entity guesses from a text/Markdown file.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, default=Path("ontology_inventory_out"))
    parser.add_argument("--min-count", type=int, default=1)
    args = parser.parse_args()

    summary = analyze_file(args.input, args.out, args.min_count)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
