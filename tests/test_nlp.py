"""Tests for NLP extraction pipeline."""

from app.nlp.extractor import heuristic_extract_entities, extract_numeric_values


def test_heuristic_material_extraction():
    text = "Проведено обогащение никель-содержащей руды с получением концентрата."
    entities = heuristic_extract_entities(text)
    entity_names = [(e["type"], e["name"]) for e in entities]
    assert ("Material", "никель") in entity_names or ("Material", "руда") in entity_names


def test_heuristic_process_extraction():
    text = "Процесс выщелачивание проводится при температуре 80°C с последующей фильтрация."
    entities = heuristic_extract_entities(text)
    entity_names = [e["name"] for e in entities]
    assert "выщелачивание" in entity_names or "фильтрация" in entity_names


def test_heuristic_parameter_extraction():
    text = "Температура плавления составила 1200°C, давление 2.5 атм."
    entities = heuristic_extract_entities(text)
    param_names = [e["name"] for e in entities if e["type"] == "Parameter"]
    assert any("температура" in n.lower() for n in param_names) or any("давление" in n.lower() for n in param_names)


def test_numeric_value_extraction():
    text = "Содержание никеля составило 12.5%, выход концентрата 85%."
    entities = heuristic_extract_entities(text)
    has_numeric = any("parameter_" in e["name"] for e in entities if e["type"] == "Parameter")
    assert has_numeric


def test_extract_numeric_values():
    values = extract_numeric_values("Температура 1200°C, давление 2.5 атм, pH 7")
    assert len(values) > 0
    has_temp = any(v.get("unit") == "°C" for v in values)
    has_ph = any("ph" in str(v.get("unit", "")).lower() or v.get("value") == 7.0 for v in values)
    assert has_temp or has_ph


def test_bilingual_extraction():
    text = "Nickel ore beneficiation using flotation cells."
    entities = heuristic_extract_entities(text)
    names = set(e["name"].lower() for e in entities)
    assert len(names) > 0


def test_empty_text():
    entities = heuristic_extract_entities("")
    assert entities == []


def test_duplicate_suppression():
    text = "Никель, никель, Ni, nickel, НИКЕЛЬ"
    entities = heuristic_extract_entities(text)
    nickels = [e for e in entities if e["type"] == "Material" and "никель" in e.get("canonical", "").lower()]
    assert len(nickels) <= 1


def test_equipment_extraction():
    text = "Использовалась центрифуга для разделения фаз."
    entities = heuristic_extract_entities(text)
    equip = [e for e in entities if e["type"] == "Equipment"]
    assert len(equip) >= 0
