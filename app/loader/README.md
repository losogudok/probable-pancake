# Разметка сущностей для `НДС Комсомольский.md`

Текущий набор файлов — это экспериментальный pipeline без LLM для проверки покрытия онтологии и поиска кандидатов на пополнение.


## Инструменты

| Файл | Назначение |
|---|---|
| `tools/ontology_word_inventory.py` | Строит первичный словарь слов и фраз из текста, без онтологии. |
| `ontology_registry_highlighter.py` | Генерирует по MD HTML с разметкой. Конкретные сущности из онтологии + эвристические кандидаты. |

## Файлы в texts_investigations

| Файл | Что внутри | Как использовать |
|---|---|---|
| `highlighted_entities.html` | Размеченный текст. Сплошное подчёркивание — конкретная сущность `EntityType:canonical`, пунктир — кандидат общего типа. | Открыть в браузере и глазами проверить разметку. |
| `entity_matches.csv` | Все найденные совпадения: позиция, фрагмент, `display_label`, `specificity`, `source`, `term_id`, `canonical`, контекст. | Основная таблица для отладки разметки. Фильтр `specificity=specific` показывает конкретные сущности. |
| `known_entities.csv` | Только сгруппированные конкретные сущности из онтологии. | Быстро ответить на вопрос “что из онтологии реально нашлось в документе”. |
| `ontology_gap_candidates.csv` | Эвристические кандидаты, которых нет в онтологии. | Очередь на ручное ревью и превращение в `TermSpec`. |
| `entity_highlight_stats.json` | Статистика запуска. | Проверка покрытия, числа кандидатов и частоты типов. |

## Команда запуска

```bash
python ontology_entity_highlighter.py "НДС Комсомольский.md"   --ontology ontology2.py   --phrases nds_ontology_inventory/phrase_candidates.csv   --words nds_ontology_inventory/unique_words_entity_guesses.csv   --out-dir nds_entity_highlight   --domains common,underground_mining
```



## Смысл разметки

В HTML и CSV есть два уровня меток:

1. **Конкретная сущность из онтологии** — метка вида `EntityType:canonical`, например `Metric:НДС`. Это значит, что фрагмент совпал с `TermSpec` из `ontology2.py`.
2. **Кандидат общего типа** — метка вида `EntityType`, например `Process` или `Equipment`. Это значит, что фрагмент похож на сущность такого типа, но конкретного `TermSpec` в онтологии пока нет.

Для этого документа запуск выполнен с доменами `common,underground_mining`, чтобы не ловить металлургические омонимы вроде `напряжение` как `Voltage`.

## Главные числа

- Всего совпадений: **266**
- Конкретных ontology-сущностей: **17**
- Эвристических кандидатов: **249**
- Уникальных ontology-сущностей: **5**

## Конкретные сущности, реально найденные в ontology mode

| Метка | term_id | Вхождений | Поверхностные формы |
|---|---:|---:|---|
| `Metric:НДС` | `underground:StressStrainState` | 9 | `НДС` |
| `Parameter:напряжение` | `underground:Stress` | 4 | `Stress; напряжение` |
| `GeologicalFeature:трещиноватость` | `underground:Fracturing` | 2 | `трещиноватость` |
| `Parameter:глубина` | `underground:Depth` | 1 | `глубина` |
| `RockMass:горный массив` | `underground:RockMass` | 1 | `Rock Mass` |
         
## Интерпретация

Если в `display_label` есть двоеточие, это конкретная описанная сущность:

```text
Metric:НДС
Parameter:напряжение
GeologicalFeature:трещиноватость
RockMass:горный массив
```

Если двоеточия нет, это только кандидат общего типа:

```text
Process
Equipment
Method
Model
```

Например, `экстензометр` сейчас подсвечивается как `Equipment`, а не как `Equipment:экстензометр`, потому что в текущей онтологии ещё нет `TermSpec` для экстензометра. После добавления такого термина в ontology module он должен перейти из `ontology_gap_candidates.csv` в `known_entities.csv`.
