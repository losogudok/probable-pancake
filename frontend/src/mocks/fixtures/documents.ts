import type { DocumentRecord, EvidenceSource } from "../../domain/types";

export const evidenceSources: EvidenceSource[] = [
  {
    id: "src-catholyte-review", title: "Обзор технических решений в области электролитического производства никеля и меди",
    filename: "Обзор технических решений в области электролитического производства никеля и меди.docx", authors: [], year: 2025,
    geography: "Foreign", sourceType: "review", trust: 4, chunkId: "e7fb17923275db5b_0009",
    section: "Циркуляционные потоки в катодной проточной диафрагме",
    quote: "Необходимая скорость движения католита обеспечивается регулированием разности уровня электролита в катодной ячейке и электролизёре. Скорость циркуляции обычно составляет 20–30 л/ч [2].",
  },
  {
    id: "src-electrowinning-principles", title: "Особенности состава электролита в технологиях электроэкстракции",
    filename: "07_2003_cm.pdf", authors: [], year: 2003, geography: "Global", sourceType: "journal_issue", trust: 4,
    page: 91, chunkId: "b57f23eb9e13b736_0403",
    quote: "Следует учитывать перенос ионов водорода из анодного пространства в катодное в зависимости от скорости циркуляции.",
  },
  {
    id: "src-nonferrous-2013", title: "Новая схема циркуляции растворов при электроэкстракции никеля",
    filename: "Proccedings_Non-Ferrous Metals 2013.pdf", authors: [], year: 2013, geography: "Global", sourceType: "conference_paper", trust: 4,
    page: 345, chunkId: "6d48e64d934f8d7d_1530",
    quote: "Предложена новая схема циркуляции растворов: часть очищенного от примесей никелевого католита циркулирует в малом контуре.",
  },
  {
    id: "src-water-2015", title: "Очистка промышленных стоков цветной металлургии",
    filename: "CM_05_15.pdf", authors: [], year: 2015, geography: "Global", sourceType: "journal_issue", trust: 4,
    page: 68, chunkId: "4aff936f59da1880_0333",
    quote: "Сухой остаток — 1930 мг/л при нормативе не более 1000 мг/л; сульфат-ионы — 1200 мг/л, хлорид-ионы — 256 мг/л.",
  },
  {
    id: "src-water-ro", title: "Замкнутая система водопользования с обратным осмосом",
    filename: "CM_03_10.pdf", authors: [], year: 2010, geography: "Global", sourceType: "journal_issue", trust: 4,
    page: 52, chunkId: "2eaead09cf74b4b2_0229",
    quote: "В таблице приведён состав исходной воды, фильтрата и концентрата обратного осмоса, включая кальций, магний, натрий и сульфаты.",
  },
  {
    id: "src-mine-water-review", title: "Методы очистки шахтных вод",
    filename: "Методы очистки шахтных вод.docx", authors: [], year: 2025, geography: "Global", sourceType: "review", trust: 4,
    section: "Введение", chunkId: "2efcea298dad83ca_0002",
    quote: "Эффективное управление водными ресурсами необходимо для устойчивого развития и соблюдения принципов экономики замкнутого цикла в горной отрасли.",
  },
  {
    id: "src-mine-injection", title: "Развитие автоклавной гидрометаллургии пирротиновых концентратов",
    filename: "11_2004_cm.pdf", authors: [], year: 2004, geography: "Russia", sourceType: "journal_issue", trust: 4,
    page: 36, chunkId: "43f9157e458b127e_0157",
    quote: "За прошедший период технология была усовершенствована; прекращена закачка сернистых стоков в подземные водоносные горизонты.",
  },
  {
    id: "src-pgm-review", title: "Распределение Au, Ag и МПГ между медным/никелевым штейном и шлаком",
    filename: "Распределение Au, Ag и МПГ между меднымникелевым штейном и шлаком.docx", authors: ["Евграфова А. К."], year: 2018,
    geography: "Foreign", sourceType: "review", trust: 4, section: "Введение", chunkId: "a2f56b6b3438d22f_0000",
    quote: "Обзор рассматривает распределение Au, Ag и металлов платиновой группы между медным или никелевым штейном и шлаком по зарубежным источникам.",
  },
  {
    id: "src-pgm-study", title: "Влияние состава штейна на распределение благородных металлов",
    filename: "36 Статья_Готовая..pdf", authors: [], geography: "Global", sourceType: "scientific_article", trust: 5,
    page: 2, chunkId: "80361f9171bda73b_0004",
    quote: "Диапазон рассчитанных коэффициентов распределения благородных металлов увеличивается в ряду Ag→Au→Ru→Ir→Pt (Pd, Rh).",
  },
];

export const documents: DocumentRecord[] = evidenceSources.map((source, index) => ({
  id: source.id, title: source.title, filename: source.filename, authors: source.authors, year: source.year,
  geography: source.geography, sourceType: source.sourceType, trust: source.trust, language: "ru",
  sensitivity: index === 5 ? "internal" : "public", factCount: [18, 11, 14, 22, 17, 31, 9, 46, 13][index] ?? 8,
  status: "indexed", snippet: source.quote,
}));
