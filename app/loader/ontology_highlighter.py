#!/usr/bin/env python3
"""Главный запуск онтологической разметки одного Markdown/текстового файла.

Вся последовательность живёт здесь, а рабочие слои импортируются как модули:
- tools.ontology_word_inventory: черновой словарь кандидатов;
- ontology_highlighter: сущности и HTML-разметка текста;
- ontology_relation_extractor: простые тройки отношений;
- ontology_document_summary: паспорт документа для шапки HTML.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ontology_word_inventory import analyze_file

import words_highlighter as highlighter
import ontology_relation_extractor as rel
from ontology_document_summary import build_document_summary, render_summary_html


def _json_dump(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _zip_dir(src_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(src_dir.rglob("*")):
            if file.is_file():
                zf.write(file, file.relative_to(src_dir.parent))


def extract_entities(input_path: Path, ontology_path: Path, inventory_dir: Path, highlight_dir: Path, domains: str) -> tuple[list[highlighter.Match], dict[str, object], str]:
    text = input_path.read_text(encoding="utf-8")
    module = highlighter.load_ontology_module(ontology_path)
    registry = highlighter.registry_from_module(module)
    domain_set = {d.strip() for d in domains.split(",") if d.strip()} if domains else None

    ontology_candidates = highlighter.collect_ontology_candidates(registry, domain_set)
    phrase_candidates = highlighter.load_phrase_candidates(inventory_dir / "phrase_candidates.csv", min_count=2)
    word_candidates = highlighter.load_word_candidates(inventory_dir / "unique_words_entity_guesses.csv", min_confidence=0.65)
    ontology_alias_keys = {highlighter.norm_text(c.text) for c in ontology_candidates}
    heuristic_candidates = [c for c in phrase_candidates + word_candidates if highlighter.norm_text(c.text) not in ontology_alias_keys]

    value_matches = highlighter.collect_parameter_value_matches(text, registry, module, domain_set)
    compound_matches = highlighter.find_compound_rule_matches(text)
    raw = highlighter.find_raw_matches(text, ontology_candidates + heuristic_candidates) + value_matches + compound_matches
    matches = highlighter.merge_neighbouring_organizations(text, highlighter.resolve_overlaps(raw))

    highlight_dir.mkdir(parents=True, exist_ok=True)
    highlighter.write_matches_csv(highlight_dir / "entity_matches.csv", text, matches)
    highlighter.write_known_entities_csv(highlight_dir / "known_entities.csv", text, matches)
    highlighter.write_gap_csv(highlight_dir / "ontology_gap_candidates.csv", matches)

    stats: dict[str, object] = {
        "input": str(input_path),
        "ontology": str(ontology_path),
        "matches_total": len(matches),
        "known_matches": sum(1 for m in matches if m.source.startswith("ontology")),
        "candidate_matches": sum(1 for m in matches if not m.source.startswith("ontology")),
        "unique_known_terms": len({m.term_id for m in matches if m.source.startswith("ontology")}),
        "ontology_candidates_loaded": len(ontology_candidates),
        "heuristic_candidates_loaded": len(heuristic_candidates),
        "ontology_value_matches_raw": len(value_matches),
        "compound_rule_matches_raw": len(compound_matches),
        "by_type": dict(Counter(m.entity_type for m in matches).most_common()),
        "by_source": dict(Counter(m.source for m in matches).most_common()),
        "top_labels": Counter(m.display_label for m in matches).most_common(40),
        "top_known_labels": Counter(m.display_label for m in matches if m.source.startswith("ontology")).most_common(40),
        "top_candidate_labels": Counter(m.display_label for m in matches if not m.source.startswith("ontology")).most_common(40),
    }
    _json_dump(highlight_dir / "entity_highlight_stats.json", stats)
    return matches, stats, text


def extract_relations(text: str, input_path: Path, entity_csv: Path, relation_dir: Path) -> list[rel.Triple]:
    entities_for_rel = rel.read_entities(entity_csv)
    triples: list[rel.Triple] = []
    triples.extend(rel.extract_pattern_triples(text, entities_for_rel))
    triples.extend(rel.extract_geography_triples(text, entities_for_rel))
    triples.extend(rel.extract_person_marker_triples(text, entities_for_rel))
    triples.extend(rel.extract_org_unit_triples(text, entities_for_rel))
    triples = rel.dedupe_triples(triples)

    relation_dir.mkdir(parents=True, exist_ok=True)
    rel.write_csv(relation_dir / "triples_simple.csv", triples)
    # JSON оставлен как технический файл совместимости; новый обязательный JSON для фасетов не создаётся.
    rel.write_json(relation_dir / "triples_simple.json", triples)
    rel.write_html(relation_dir / "triples_simple.html", triples, input_path.name)

    summary = {
        "input": str(input_path),
        "entities": str(entity_csv),
        "triples_total": len(triples),
        "by_predicate": dict(Counter(t.predicate for t in triples).most_common()),
    }
    _json_dump(relation_dir / "summary.json", summary)
    return triples


def run(input_path: Path, out_dir: Path, ontology_path: Path, domains: str, clean: bool) -> dict[str, object]:
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    inventory_dir = out_dir / "inventory"
    highlight_dir = out_dir / "highlight"
    relation_dir = out_dir / "relations_simple"

    inventory_summary = analyze_file(input_path, inventory_dir, min_count=1)
    _json_dump(out_dir / "inventory_run.json", inventory_summary)

    matches, highlight_stats, text = extract_entities(input_path, ontology_path, inventory_dir, highlight_dir, domains)
    _json_dump(out_dir / "highlight_run.json", highlight_stats)

    triples = extract_relations(text, input_path, highlight_dir / "entity_matches.csv", relation_dir)
    relations_summary = {
        "input": str(input_path),
        "triples_total": len(triples),
        "by_predicate": dict(Counter(t.predicate for t in triples).most_common()),
    }
    _json_dump(out_dir / "relations_run.json", relations_summary)

    document_summary = build_document_summary(input_path, text, matches, triples)
    summary_html = render_summary_html(document_summary)
    highlighter.write_html(highlight_dir / "highlighted_entities.html", text, matches, highlight_stats, document_summary_html=summary_html)

    return {
        "input": str(input_path),
        "out_dir": str(out_dir),
        "html": str(highlight_dir / "highlighted_entities.html"),
        "triples_html": str(relation_dir / "triples_simple.html"),
        "triples_csv": str(relation_dir / "triples_simple.csv"),
        "entities": len(matches),
        "triples": len(triples),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ontology entity markup, simple triples and document passport in one pipeline.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--ontology", type=Path, default=ROOT / "ontology2.py")
    parser.add_argument("--domains", default="common,underground_mining")
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args()

    result = run(args.input, args.out_dir, args.ontology, args.domains, clean=not args.no_clean)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
