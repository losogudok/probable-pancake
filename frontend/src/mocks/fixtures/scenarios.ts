import type { ResearchAnswer } from "../../domain/types";
import { evidenceSources } from "./documents";
import { knowledgeGraph } from "./graph";

const source = (id: string) => evidenceSources.find((item) => item.id === id)!;
const processing = { durationMs: 2140, documentsScanned: 1281, graphNodesVisited: 43, pipelineVersion: "demo-1.0" };
const confidence = (overall: number, label: string) => ({ overall, extraction: overall + 3, sourceQuality: overall, corroboration: overall - 5, label });

export const catholyteAnswer: ResearchAnswer = {
  id: "answer-catholyte", query: "", mode: "literature_review",
  summary: "Для проточной катодной диафрагмы обзор мировой практики указывает типичный расход католита 20–30 л/ч. Регулирование выполняется разностью уровней католита и анолита. Значение нельзя переносить на любую ванну без проверки геометрии ячейки, плотности тока и состава электролита.",
  confidence: confidence(88, "Высокая для найденной конструкции"),
  findings: [
    { id: "f1", title: "Рабочий ориентир", text: "20–30 л/ч — документированный типичный диапазон для катодной проточной диафрагмы.", sourceIds: ["src-catholyte-review"], status: "supported" },
    { id: "f2", title: "Механизм регулирования", text: "Скорость движения задаётся перепадом уровней электролита между катодной ячейкой и электролизёром.", sourceIds: ["src-catholyte-review"], status: "supported" },
    { id: "f3", title: "Ограничение переноса", text: "Оптимум зависит от конструкции и технологического режима; универсальное значение источниками не подтверждено.", sourceIds: ["src-electrowinning-principles", "src-nonferrous-2013"], status: "conditional" },
  ],
  numericParameters: [{ id: "n1", label: "Скорость циркуляции католита", value: "20–30", unit: "л/ч", applicability: "conditional", sourceIds: ["src-catholyte-review"] }],
  comparisons: [
    { id: "c1", method: "Проточная катодная диафрагма", geography: "Мировая практика", parameters: "20–30 л/ч", strengths: "Управляемый перепад уровней", limitations: "Зависимость от геометрии ванны", sourceIds: ["src-catholyte-review"] },
    { id: "c2", method: "Малый контур циркуляции", geography: "Мировая практика", parameters: "Часть католита рециркулирует", strengths: "Снижение общего объёма циркуляции", limitations: "Числовой оптимум в найденном фрагменте не задан", sourceIds: ["src-nonferrous-2013"] },
  ],
  sources: [source("src-catholyte-review"), source("src-electrowinning-principles"), source("src-nonferrous-2013")],
  contradictions: [{ id: "con1", parameter: "Оптимальная скорость", context: "Разные конструкции циркуляционного контура", values: [{ value: "20–30 л/ч", conditions: "Проточная катодная диафрагма", sourceId: "src-catholyte-review" }, { value: "Не задана", conditions: "Малый контур циркуляции", sourceId: "src-nonferrous-2013" }], explanation: "Это пробел сравнения, а не доказанное числовое противоречие.", reviewStatus: "reviewed" }],
  validations: [{ id: "v1", statement: "Скорость циркуляции влияет на перенос ионов и технологические показатели.", sourceIds: ["src-catholyte-review", "src-electrowinning-principles"] }],
  experts: [], gaps: [{ id: "g1", material: "Никелевый католит", process: "Электроэкстракция", condition: "Сопоставимые конструкции ванн", relatedDocuments: 3, recommendation: "Сравнить расход в удельных единицах на площадь катода." }],
  graphPreview: { nodes: knowledgeGraph.nodes.slice(0, 7), edges: knowledgeGraph.edges.slice(0, 6) }, processing,
};

export const desalinationAnswer: ResearchAnswer = {
  id: "answer-desalination", query: "", mode: "comparison",
  summary: "Для достижения сухого остатка ≤1000 мг/л требуется стадия деминерализации. Найденный кейс с сухим остатком 1930 мг/л и сульфатами 1200 мг/л не удовлетворяет цели без дополнительной обработки; обратный осмос представлен как релевантная стадия замкнутого водооборота.",
  confidence: confidence(79, "Средняя: параметры исходной воды отличаются"),
  findings: [{ id: "f1", title: "Проверка ограничения", text: "Кейс 1930 мг/л превышает требование ≤1000 мг/л.", sourceIds: ["src-water-2015"], status: "supported" }, { id: "f2", title: "Кандидатный метод", text: "Обратный осмос применяется в схеме разделения очищенной воды и концентрата.", sourceIds: ["src-water-ro"], status: "conditional" }],
  numericParameters: [{ id: "n1", label: "Сухой остаток найденного кейса", value: "1930", unit: "мг/л", applicability: "outside", sourceIds: ["src-water-2015"] }, { id: "n2", label: "Целевой сухой остаток", value: "≤1000", unit: "мг/л", applicability: "matches", sourceIds: [] }, { id: "n3", label: "Сульфаты найденного кейса", value: "1200", unit: "мг/л", applicability: "outside", sourceIds: ["src-water-2015"] }],
  comparisons: [{ id: "c1", method: "Обратный осмос", geography: "Глобальная", parameters: "Разделение на фильтрат и концентрат", strengths: "Глубокая деминерализация", limitations: "Требует обращения с концентратом", sourceIds: ["src-water-ro"] }],
  sources: [source("src-water-2015"), source("src-water-ro")], contradictions: [],
  validations: [{ id: "v1", statement: "Одной традиционной очистки недостаточно для кейса с сухим остатком 1930 мг/л.", sourceIds: ["src-water-2015"] }], experts: [],
  gaps: [{ id: "g1", material: "Шахтная вода", process: "Обессоливание", condition: "Ca, Mg, Na по 200–300 мг/л", relatedDocuments: 2, recommendation: "Выполнить расчёт recovery и состава концентрата для точного выбора схемы." }], graphPreview: { nodes: [], edges: [] }, processing,
};

export const pgmAnswer: ResearchAnswer = {
  id: "answer-pgm", query: "", mode: "literature_review",
  summary: "Корпус подтверждает преимущественное концентрирование благородных металлов в штейновой фазе и различия коэффициентов распределения для Ag, Au и МПГ. Однако основной профильный обзор датирован 2018 годом, поэтому условие «за последние 5 лет» покрыто недостаточно.",
  confidence: confidence(74, "Средняя: временной фильтр покрыт не полностью"),
  findings: [{ id: "f1", title: "Направление распределения", text: "Исследование указывает преимущественное концентрирование благородных металлов в штейне.", sourceIds: ["src-pgm-study"], status: "supported" }, { id: "f2", title: "Временное ограничение", text: "Профильный обзор 2018 года не входит в последние пять лет.", sourceIds: ["src-pgm-review"], status: "insufficient" }],
  numericParameters: [], comparisons: [], sources: [source("src-pgm-study"), source("src-pgm-review")], contradictions: [], validations: [],
  experts: [{ id: "ex1", name: "Евграфова А. К.", organization: "Институт Гипроникель", expertise: ["штейн", "шлак", "благородные металлы"], publicationCount: 4 }],
  gaps: [{ id: "g1", material: "Au, Ag и МПГ", process: "Плавка", condition: "Публикации 2021–2026", relatedDocuments: 1, recommendation: "Обновить обзор первичными публикациями последних пяти лет." }], graphPreview: { nodes: knowledgeGraph.nodes.slice(7), edges: knowledgeGraph.edges.slice(6) }, processing,
};

export const mineWaterAnswer: ResearchAnswer = {
  id: "answer-mine-water", query: "", mode: "comparison",
  summary: "Корпус содержит российский кейс прекращения закачки сернистых стоков в подземные водоносные горизонты и современный обзор методов обращения с шахтными водами. Данных для достоверного сравнения технико-экономических показателей России и зарубежья недостаточно.",
  confidence: confidence(66, "Ограниченная доказательная база"),
  findings: [{ id: "f1", title: "Российская практика", text: "В описанном производстве закачка сернистых стоков была прекращена после модернизации технологии.", sourceIds: ["src-mine-injection"], status: "supported" }, { id: "f2", title: "Экономические показатели", text: "Сопоставимые CAPEX/OPEX в найденных фрагментах отсутствуют.", sourceIds: ["src-mine-water-review"], status: "insufficient" }],
  numericParameters: [], comparisons: [{ id: "c1", method: "Закачка в водоносные горизонты", geography: "Россия", parameters: "Практика прекращена в описанном кейсе", strengths: "Нет данных для подтверждения", limitations: "Экологические и технологические ограничения", sourceIds: ["src-mine-injection"] }],
  sources: [source("src-mine-injection"), source("src-mine-water-review")], contradictions: [], validations: [], experts: [],
  gaps: [{ id: "g1", material: "Шахтные воды", process: "Глубинная закачка", condition: "Сопоставимые технико-экономические показатели", relatedDocuments: 2, recommendation: "Собрать CAPEX, OPEX, глубину, дебит и нормативные ограничения по каждому объекту." }], graphPreview: { nodes: [], edges: [] }, processing,
};
