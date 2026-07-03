# Архитектура — «Научный клубок» (граф знаний R&D)

Граф знаний для горно-металлургического R&D Норникеля: вопрос на естественном языке →
ответ с числами, цитатами, источниками и вычисленными противоречиями/подтверждениями.

## Ключевой принцип

**Детерминированное ядро + опциональный LLM/OCR-слой.**

- **Числа** извлекаются regex-грамматикой величин — не галлюцинируют (ТЗ: «ошибки в
  концентрациях/температурах недопустимы»).
- **Сущности** — газетиром (закрытый металлургический домен, RU↔EN).
- **Таблицы составов** — Yandex Vision OCR (плоское извлечение текста расцепляет
  элемент↔значение — главная слабость, решённая структурным OCR).
- **LLM / эмбеддинги / OCR** — обогащение поверх ядра, отключаемы. Модели open-weight
  (Qwen3, DeepSeek) → self-hostable on-prem. **Без ключа система полнофункциональна**
  (rule-based путь).

---

## 1. Поток данных (build-time) — конвейер извлечения

```
Сырой корпус (2017 файлов: PDF/DOCX/PPTX/XLS + zip/rar/split-архивы)
   │
[0+1] extract.py
   │   MAGIC-сниффинг типа (не по расширению), склейка split-архивов .001/.002,
   │   диспетчер fitz(PDF) / python-docx / soffice(.doc) / pandas(xls),
   │   дедуп по md5 нормализованного текста, year из имени файла,
   │   sensitivity + kg_value по категории
   │   → artifacts/docs.meta.jsonl (в git)  +  data/docs.text.jsonl (локально, gitignored)
   │
[0.5] normalize.py
   │   OCR-нормализация: омоглифы кириллица↔латиница (только С→C для °С),
   │   дегифенация переносов «выщелачива-\nние», удаление колонтитулов
   │
   ├──────────────── ВЕТКА A: текст → факты из прозы ────────────────┐
   │                                                                  │
[2] gazetteer.py            [3] grammar.py             pipeline.process_doc
   PhraseMatcher RU↔EN,      regex-грамматика величин:  сегментация на предложения,
   3 яруса:                  • диапазоны X–Y, от…до, ÷  для каждого:
   • ORTH (регистр:          • компараторы <,≤,не более  • gazetteer.match → упоминания
     Co≠co, Fe/S/Se…)        • канонизация ~8 семейств   • grammar.parse_values → факты
   • LEMMA (падежи)            единиц (мг/л, °C, А/м2…)   • [4-мини] глагольные паттерны →
   • LOWER (EN-алиасы)       • метрика↔единица матрица    uses_material/produces_output/
   ~150 канонов +            • conditions co-extraction   operates_at_condition (source=pattern)
   гео-слой Deposit/         • sanity + confidence        РЕЗОЛЬВЕР: метрика↔ТИП-сущности
   Enterprise/Country                                     (COMPAT), zip перечислений,
                                                          приоритет grammar-материалу
   │                                                                  │
   └────────────────► artifacts/facts.jsonl + artifacts/edges.jsonl ◄─┘
   │
   ├──────────────── ВЕТКА B: таблицы составов (vision.py) ──────────┐
   │   PDF: рендер страницы (пре-фильтр составности) → Yandex Vision  │
   │        OCR model=table → структурные ячейки (строка/столбец)     │
   │   DOCX: python-docx таблицы напрямую (без OCR)                    │
   │   table_to_facts: детект строки-заголовка (элементы), привязка   │
   │        элемент↔значение, склейка диапазонов, инференс единицы     │
   │        (major-оксиды→%), фаза из заголовка, метка≠значение,       │
   │        транспонированные таблицы. Кэш OCR на диске (идемпотентно) │
   │        → artifacts/vision_facts.jsonl                             │
   │
[year_fill.py] год из front-matter/выходных данных для null-доков
   │
[6] graph.py  — загрузка в Neo4j (UNWIND-батчи ~10 запросов):
   │   MERGE Document/Material/Process/Equipment/Phase/Facility/Parameter,
   │   реификация Experiment по (doc_id, conditions) с sanity-гейтом,
   │   дедуп pkey (int/float норм), рёбра MENTIONS/HAS_PARAM/MEASURES/
   │   MEASURED_IN/DESCRIBED_IN + типизированные; индексы (constraint pkey/canon,
   │   RANGE value_low/high, составной metric+unit, FULLTEXT, btree year/geo)
   │
[5] contradictions.py — вычисление верификационного слоя (поверх графа):
   │   группировка (metric, canon, phase, unit) → пары из разных доков:
   │   расхождение ≤10% → VALIDATED_BY, >20% → CONTRADICTS;
   │   гейты: comparator-лимиты, фаза-носитель, sanity-границы, дедуп цитат,
   │   широкие диапазоны; ru_vs_world по доле кириллицы В ТЕЛЕ текста;
   │   kind = ru_vs_world | method_vs_method
   │
[7] embed.py — семантический индекс:
       Yandex text-embeddings-v2 (256d, dense-first порядок) → artifacts/emb.npy
       (numpy-матрица, ноль локального torch/RAM)
```

## 2. Поток запроса (runtime) — search.py + React frontend

```
Вопрос пользователя (RU/EN)
   │
 ┌─ grammar.parse_query — ТА ЖЕ грамматика величин (симметрия запрос↔документ)
 └─ llm.parse_query — DeepSeek-V4-Flash интент (race с rule-based, таймаут 8с → фолбэк)
   │
 Три дорожки:
   ├─ ЧИСЛОВАЯ:  Cypher по Parameter (RANGE-пересечение диапазонов, сортировка по
   │             близости к цели), + эталонные shortcuts q_desalination/q_catholyte/
   │             q_pgm (RU + EN-триггеры)
   ├─ СЕМАНТИЧЕСКАЯ: emb.npy dot-product по запросу (Yandex query-эмбеддинг),
   │             score-floor против шума
   └─ (графовая — окрестность узлов, P2)
   │
 Слияние по doc_id (ref → in_range → близость), дедуп
   │
 RBAC-фильтр (5 ролей: researcher/analyst/project_lead/admin/external_partner;
   sensitivity-сегментация; аудит query/view/export → artifacts/audit.jsonl)
   │
 Композер: экстрактивный ответ (факт + значение + единица + фаза + verbatim-цитата +
   документ), блок «⚠ Противоречия», «✓ Подтверждено», релевантные документы, эксперты
   │
 React + Vite + TypeScript: разделы Поиск / Граф / Источники / Качество / Аналитика;
   React Flow для подграфа, responsive mobile UX, демонстрационный селектор роли,
   эталонные запросы ТЗ и экспорт Markdown / JSON-LD / PDF
```

## 3. Онтология графа (Neo4j)

### Узлы (8 типов ТЗ + служебные)

| Узел | Тип ТЗ | Роль |
|---|---|---|
| `Document` | Publication | публикация/отчёт; year, geo, sensitivity, kg_value |
| `Parameter` | Property | числовой факт: value_low/high, unit_canon, metric, comparator, **confidence, quote, source, extracted_at, pipeline_version** |
| `Experiment` | Experiment | реификация группы Parameter одного (doc_id, conditions) |
| `Material` | Material | вещества/элементы (canon + aliases RU/EN/символы) |
| `Process` | Process | процессы |
| `Equipment` | Equipment | оборудование |
| `Phase` | — | штейн/файнштейн/шлак/раствор/католит/анолит… |
| `Facility` | Facility | месторождения/предприятия (+ geo) |
| `Author`/`Organization` | Expert | из front-matter журналов (индекс-слой) |

### Рёбра (6 связей ТЗ + служебные)

| Ребро | Связь ТЗ |
|---|---|
| `USES_MATERIAL` | uses_material |
| `OPERATES_AT_CONDITION` | operates_at_condition |
| `PRODUCES_OUTPUT` | produces_output |
| `DESCRIBED_IN` | described_in |
| `VALIDATED_BY` | validated_by |
| `CONTRADICTS` | contradicts (+ VARIES_WITH_CONDITIONS) |
| `MEASURES`, `MEASURED_IN`, `HAS_PARAM`, `MENTIONS` | служебные (провенанс/навигация) |

**Модель верификации знаний (ТЗ):** каждый факт несёт источник (doc_id + quote),
уровень достоверности (confidence), дату актуализации (extracted_at) и версию
пайплайна (pipeline_version).

## 4. Стек и обоснование решений

| Слой | Технология | Почему |
|---|---|---|
| Числа | собственная regex-грамматика | детерминизм, «ошибки в концентрациях недопустимы»; одна грамматика на документы И запросы |
| Сущности | spaCy PhraseMatcher + pymorphy3 | закрытый домен, падежи; словарь из корпуса |
| Таблицы | **Yandex Vision OCR** (model=table) | плоский текст расцепляет состав; API → ноль локального RAM; RU+EN |
| LLM build-time | Qwen3-235B (Yandex AI Studio) | лучший RU+JSON; open-weight → self-hostable |
| LLM runtime | DeepSeek-V4-Flash | быстрый парсинг запросов; фолбэк на rule-based |
| Семантика | Yandex text-embeddings-v2 (256d) | RU/EN одно пространство; ноль локального torch |
| Граф | Neo4j 5.26 community (docker) | Cypher, RANGE-индексы, dump, граф-виз |
| UI | React + Vite + TypeScript + React Flow | сложное состояние, интерактивный подграф, mobile UX, тестируемость |

**Отвергнуто:** LLM-извлечение чисел (галлюцинации), FAISS (numpy достаточно),
локальный e5/torch (RAM), C++/Rust (профиль I/O+regex — горячее уже в C/Cython).

## 5. Модули (16 файлов, ~4300 строк)

| Модуль | Строк | Назначение |
|---|---:|---|
| `grammar.py` | 808 | числовая грамматика величин (ядро) |
| `search.py` | 900 | гибридный поиск + композер ответа |
| `frontend/` | — | React SPA: поиск, граф, источники, качество, аналитика |
| `vision.py` | 437 | Vision OCR таблиц + DOCX-таблицы |
| `graph.py` | 423 | Neo4j: схема, батч-загрузка, 3 эталонных запроса |
| `contradictions.py` | 370 | вычисление CONTRADICTS/VALIDATED_BY |
| `pipeline.py` | 309 | оркестрация build-time + резольвер |
| `llm.py` | 239 | Yandex OpenAI-совместимый клиент + кэш |
| `gazetteer.py` | 223 | газетир RU↔EN, 3 яруса |
| `normalize.py` | 184 | OCR-нормализация текста |
| `extract.py` | 182 | извлечение текста из корпуса |
| `embed.py` | 171 | семантика (Yandex embeddings) |
| `config.py`, `load.py`, `year_fill.py` | 151 | конфиг / загрузчик-энтрипоинт / год |

**Тесты:** 12 модулей, **153 теста** (`pytest -p no:randomly`; grammar golden 98.8%).

## 6. Артефакты пайплайна

| Файл | В git | Содержимое |
|---|---|---|
| `artifacts/docs.meta.jsonl` | ✓ | метаданные документов (не текст) |
| `artifacts/facts.jsonl` | ✓ | числовые факты грамматики (провенанс) |
| `artifacts/vision_facts.jsonl` | ✓ | факты из таблиц составов |
| `artifacts/edges.jsonl` | ✓ | типизированные рёбра |
| `artifacts/emb.npy` | ✓ | семантический индекс (numpy) |
| `artifacts/*.dump` | ✓ | Neo4j dump (воспроизводимость) |
| `data/docs.text.jsonl` | ✗ (gitignored) | полнотекст (редистрибуция) |
| `data/ocr_cache/` | ✗ | кэш OCR-ответов |
| `.env` | ✗ | ключ Yandex |

Белый список в `.gitignore`: полнотекст платных журналов не попадает в git.

## 7. Развёртывание

```bash
docker compose up -d neo4j     # граф
make load                      # артефакты → Neo4j (или load-dump из дампа)
cd frontend && npm ci && npm run build
uvicorn app.api.server:app --host 0.0.0.0 --port 8080
```

- `docker-compose.yml`: neo4j:5.26.0 (named volume) + app (python:3.12-slim).
- Frontend использует единый `KnowledgeApi`: `mock`-адаптер для автономного демо и
  `http`-адаптер для FastAPI. Активный режим задаётся `VITE_API_MODE`.
- **Без API-ключа система полнофункциональна**: rule-based парсер запросов, ядро
  числовое+графовое офлайн; отключаются только LLM-обогащение, vision-ре-билд, семантика.
- Кросс-платформенно: build-time бинари (soffice/tesseract) опциональны с graceful skip;
  судьям нужны только артефакты + Neo4j dump (build-time не требуется).

## 8. Соответствие ТЗ (сводка)

- **Онтология 8/8**, **связи 6/6** (см. §3).
- **Числовые диапазоны** («сульфаты <200 мг/л») — грамматика + RANGE-индексы.
- **Мультиязычность RU/EN** — омоглифы, aliases_en, латинские единицы, кросс-язычные эмбеддинги.
- **Модель верификации** — confidence + quote + extracted_at + pipeline_version на каждом факте.
- **Отеч-vs-мир** — ru_vs_world по языку тела; фильтр в UI.
- **Пробелы, противоречия, литобзор** — вычислимые из графа.
- **RBAC 5 ролей + аудит** — конфиг-матрица + sensitivity + JSONL-лог.
- **3 эталонных запроса ТЗ** — отвечают с провенансом.
- Полная трассировка требований — в `PLAN.md` (раздел «Трассировка ТЗ → план»).

## 9. Границы и осознанные решения

- **Покрытие:** глубоко обработано R&D-ядро (Обзоры ~100%, Статьи 57/60, Доклады 16/16 ≈
  175 доков); **журналы (353, цельные номера — нужна сегментация) и рыночные материалы
  конференций (757, Tier B) — индекс-слой, не факты.** 149/1288 доков имеют факты — это
  осознанный выбор качество-vs-покрытие (ценные 12%).
- **Точность:** значения/единицы — детерминированно (golden 98.8%); привязка к сущности
  ~87% на выборке, остаток гейтится confidence (механизм «уровня достоверности» из ТЗ).
- ТЗ **не задаёт числовой порог** точности — требует корректных чисел + указания
  достоверности; и то, и другое обеспечено.
