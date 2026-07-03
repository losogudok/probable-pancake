import type { KnowledgeApi } from "./knowledge-api";
import type { AnalysisMode, AskRequest, DashboardData, DocumentPage, DocumentRecord, DocumentSearchRequest, EntitySummary, GraphRequest, ImportedDocument, KnowledgeSubgraph, ParsedQuery, QualityItemGroup, ResearchAnswer, UploadProgress, UploadRequest } from "../domain/types";
import { catholyteAnswer, desalinationAnswer, mineWaterAnswer, pgmAnswer } from "../mocks/fixtures/scenarios";
import { documents, evidenceSources } from "../mocks/fixtures/documents";
import { knowledgeGraph } from "../mocks/fixtures/graph";
import { dashboard, quality } from "../mocks/fixtures/dashboard";
import { persistence } from "../mocks/persistence";

const delay = (ms: number, signal?: AbortSignal) => import.meta.env.MODE === "test" ? Promise.resolve() : new Promise<void>((resolve, reject) => {
  const timer = window.setTimeout(resolve, ms);
  signal?.addEventListener("abort", () => { window.clearTimeout(timer); reject(new DOMException("Операция отменена", "AbortError")); }, { once: true });
});
const clone = <T,>(value: T): T => structuredClone(value);

function detectMode(query: string): AnalysisMode {
  const q = query.toLowerCase();
  if (/сравн|росси|зарубеж|вариант/.test(q)) return "comparison";
  if (/обзор|публикац|за последние|миров.*практик/.test(q)) return "literature_review";
  return "answer";
}

function deepScenario(query: string): ResearchAnswer | undefined {
  const q = query.toLowerCase();
  if (/католит|электроэкстракц.*никел|циркуляц.*электролит/.test(q)) return clone(catholyteAnswer);
  if (/обессол|сухой остаток|сульфат.*хлорид/.test(q)) return clone(desalinationAnswer);
  if (/мпг|штейн.*шлак|au.*ag|благородн.*металл/.test(q)) return clone(pgmAnswer);
  if (/закач.*вод|шахтн.*вод.*горизонт|глубок.*горизонт/.test(q)) return clone(mineWaterAnswer);
}

function parse(query: string): ParsedQuery {
  const q = query.toLowerCase();
  const token = (id: string, label: string, value = label) => ({ id, label, value });
  const materials = [
    ["никел", "Никель"], ["католит", "Католит"], ["сульфат", "Сульфаты"], ["хлорид", "Хлориды"],
    ["шахтн", "Шахтные воды"], ["штейн", "Штейн"], ["шлак", "Шлак"], ["мпг", "МПГ"],
  ].filter(([key]) => q.includes(key)).map(([key, label]) => token(`m-${key}`, label));
  const processes = [
    ["электроэкстрак", "Электроэкстракция"], ["обессол", "Обессоливание"], ["закач", "Глубинная закачка"],
    ["распредел", "Распределение"], ["плавк", "Плавка"],
  ].filter(([key]) => q.includes(key)).map(([key, label]) => token(`p-${key}`, label));
  const geography = [] as ParsedQuery["geography"];
  if (/росси|отечествен/.test(q)) geography.push("Russia");
  if (/зарубеж|миров/.test(q)) geography.push("Foreign", "Global");
  const conditions: ParsedQuery["conditions"] = [];
  const range = query.match(/(\d+[.,]?\d*)\s*[–-]\s*(\d+[.,]?\d*)\s*(мг\/л|мг\/дм³|л\/ч|%)/i);
  if (range) conditions.push({ id: "range-1", parameter: q.includes("сух") ? "Сухой остаток" : "Концентрация", operator: "range", value: Number(range[1].replace(",", ".")), valueTo: Number(range[2].replace(",", ".")), unit: range[3] });
  const max = query.match(/(?:≤|не более|до)\s*(\d+[.,]?\d*)\s*(мг\/л|мг\/дм³|л\/ч|%)/i);
  if (max) conditions.push({ id: "max-1", parameter: q.includes("сух") ? "Сухой остаток" : "Параметр", operator: "≤", value: Number(max[1].replace(",", ".")), unit: max[2] });
  const years = q.match(/последн(?:ие|их)\s+(\d+)\s+лет/);
  const yearRange = years ? [new Date().getFullYear() - Number(years[1]), new Date().getFullYear()] as [number, number] : undefined;
  return { intent: detectMode(query), materials, processes, conditions, geography, yearRange, language: /[а-яё]/i.test(query) ? "ru" : "en" };
}

function genericAnswer(request: AskRequest): ResearchAnswer {
  const words = request.query.toLowerCase().split(/\W+/).filter((w) => w.length > 3);
  const ranked = evidenceSources.map((s) => ({ source: s, score: words.filter((w) => `${s.title} ${s.quote}`.toLowerCase().includes(w)).length })).filter((x) => x.score > 0).sort((a, b) => b.score - a.score).slice(0, 4).map((x) => x.source);
  return {
    id: `generic-${Date.now()}`, query: request.query, mode: request.mode === "auto" ? detectMode(request.query) : request.mode,
    summary: "Недостаточно структурированных данных для полного аналитического вывода. Ниже показаны совпавшие материалы корпуса; уточните материал, процесс, географию или числовой диапазон.",
    confidence: { overall: 42, extraction: 70, sourceQuality: 64, corroboration: 18, label: "Недостаточно данных" },
    findings: ranked.length ? [{ id: "generic-f1", title: "Найдены тематические материалы", text: `Совпадений в демонстрационном корпусе: ${ranked.length}.`, sourceIds: ranked.map((s) => s.id), status: "insufficient" }] : [],
    numericParameters: [], comparisons: [], sources: ranked, contradictions: [], validations: [], experts: [],
    gaps: [{ id: "generic-gap", material: "Не определён", process: "Не определён", condition: "Недостаточно параметров запроса", relatedDocuments: ranked.length, recommendation: "Укажите материал, процесс, условия и период." }],
    graphPreview: { nodes: [], edges: [] }, processing: { durationMs: 1760, documentsScanned: 1281, graphNodesVisited: 0, pipelineVersion: "demo-1.0" },
  };
}

export class MockKnowledgeApi implements KnowledgeApi {
  async parseQuery(query: string): Promise<ParsedQuery> { await delay(180); return parse(query); }
  async ask(request: AskRequest): Promise<ResearchAnswer> {
    await delay(1850);
    const answer = deepScenario(request.query) ?? genericAnswer(request);
    answer.query = request.query;
    if (request.mode !== "auto") answer.mode = request.mode;
    persistence.addHistory(request.query);
    return answer;
  }
  async searchDocuments(request: DocumentSearchRequest): Promise<DocumentPage> {
    await delay(260);
    let items: DocumentRecord[] = [...persistence.getImports(), ...documents];
    const query = request.query?.toLowerCase().trim();
    if (query) items = items.filter((d) => `${d.title} ${d.filename} ${d.snippet ?? ""}`.toLowerCase().includes(query));
    if (request.geography) items = items.filter((d) => d.geography === request.geography);
    if (request.sourceType) items = items.filter((d) => d.sourceType === request.sourceType);
    if (request.trustMin) items = items.filter((d) => d.trust >= request.trustMin!);
    if (request.yearFrom) items = items.filter((d) => (d.year ?? 0) >= request.yearFrom!);
    if (request.sort === "date") items.sort((a, b) => (b.year ?? 0) - (a.year ?? 0));
    if (request.sort === "trust") items.sort((a, b) => b.trust - a.trust);
    const page = request.page ?? 1; const pageSize = request.pageSize ?? 20;
    return { items: items.slice((page - 1) * pageSize, page * pageSize), total: items.length, page, pageSize };
  }
  async suggestEntities(query: string): Promise<EntitySummary[]> {
    await delay(120); const q = query.toLowerCase();
    return knowledgeGraph.nodes.filter((node) => !q || `${node.label} ${node.aliases?.join(" ") ?? ""}`.toLowerCase().includes(q)).slice(0, 8).map(({ id, label, type, sourceCount }) => ({ id, label, type, sourceCount }));
  }
  async getGraph(request: GraphRequest): Promise<KnowledgeSubgraph> {
    await delay(420); const root = knowledgeGraph.nodes.find((n) => n.id === request.entityId) ?? knowledgeGraph.nodes[0];
    const included = new Set([root.id]);
    for (let depth = 0; depth < request.depth; depth += 1) knowledgeGraph.edges.forEach((edge) => { if (included.has(edge.source) || included.has(edge.target)) { included.add(edge.source); included.add(edge.target); } });
    return { nodes: knowledgeGraph.nodes.filter((n) => included.has(n.id)), edges: knowledgeGraph.edges.filter((e) => included.has(e.source) && included.has(e.target)) };
  }
  async getQuality(): Promise<QualityItemGroup> { await delay(280); return clone(quality); }
  async getDashboard(): Promise<DashboardData> { await delay(280); return clone(dashboard); }
  async uploadDocuments(request: UploadRequest, onProgress: (event: UploadProgress) => void): Promise<ImportedDocument[]> {
    const stages: UploadProgress["stage"][] = ["upload", "recognition", "normalization", "extraction", "indexing", "complete"];
    for (let i = 0; i < stages.length; i += 1) { await delay(260, request.signal); request.files.forEach((file) => onProgress({ fileName: file.name, stage: stages[i], percent: Math.round(((i + 1) / stages.length) * 100) })); }
    if (request.signal?.aborted) throw new DOMException("Операция отменена", "AbortError");
    const imported = request.files.map((file, index): ImportedDocument => ({ id: `import-${Date.now()}-${index}`, title: file.name.replace(/\.[^.]+$/, ""), filename: file.name, authors: [], year: new Date().getFullYear(), geography: request.geography, sourceType: request.category, trust: 1, language: request.language, sensitivity: request.sensitivity, factCount: Math.max(3, Math.round(file.size / 100_000)), status: "indexed", importedAt: new Date().toISOString() }));
    persistence.setImports([...imported, ...persistence.getImports()]); return imported;
  }
}
