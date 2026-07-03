import type { KnowledgeApi } from "./knowledge-api";
import type {
  CompareRequest,
  CompareResponse,
  ContradictionKind,
  ContradictionItem,
  CoverageDomain,
  CoverageGeo,
  CoverageYear,
  DashboardActivity,
  DashboardExpert,
  DashboardSummary,
  ExportFormat,
  Fact,
  FilterOptions,
  Filters,
  LiteratureReviewRequest,
  LiteratureReviewResponse,
  NotifyCheckItem,
  NotifySubscription,
  Role,
  RiskZones,
  SearchRequest,
  SearchResponse,
  SubgraphRequest,
  SubgraphResponse,
} from "../domain/types";
import { confidenceLabel } from "../domain/types";
import { buildSubgraph } from "../mocks/fixtures/graph";
import { fetchContradictions } from "../mocks/fixtures/contradictions";
import {
  compareTechnologies,
  coverageByDomain,
  coverageByGeo,
  coverageByYear,
  dashboardActivity as activityFixture,
  dashboardExperts as expertsFixture,
  dashboardSummary,
  riskZones,
} from "../mocks/fixtures/dashboard";
import {
  docById,
  emptyDocs,
  experts as expertIndex,
  facts as factTable,
  filterOptions,
  resolveScenario,
} from "../mocks/fixtures/facts";
import { persistence } from "../mocks/persistence";

const delay = (ms: number, signal?: AbortSignal) =>
  import.meta.env.MODE === "test"
    ? Promise.resolve()
    : new Promise<void>((resolve, reject) => {
        const timer = window.setTimeout(resolve, ms);
        signal?.addEventListener(
          "abort",
          () => {
            window.clearTimeout(timer);
            reject(new DOMException("Операция отменена", "AbortError"));
          },
          { once: true },
        );
      });

const clone = <T,>(value: T): T => structuredClone(value);

function passesFilters(fact: Fact, filters: Filters): boolean {
  if (filters.min_confidence != null && (fact.confidence ?? 0.5) < filters.min_confidence) return false;
  if (filters.confidence?.length) {
    const level = confidenceLabel(fact.confidence ?? 0.5);
    if (!filters.confidence.includes(level)) return false;
  }
  if (filters.year && Array.isArray(filters.year) && filters.year.length === 2) {
    const [from, to] = filters.year as [number, number];
    if (fact.year != null && (fact.year < from || fact.year > to)) return false;
  }
  if (filters.geo?.length) {
    const doc = docById(fact.doc_id);
    const geo = doc?.geo ?? "WORLD";
    if (!filters.geo.includes(geo)) return false;
  }
  if (filters.material?.length && !filters.material.some((m) => fact.canon.toLowerCase().includes(m.toLowerCase()))) return false;
  if (filters.process?.length && !filters.process.some((p) => fact.canon.toLowerCase().includes(p.toLowerCase()))) return false;
  return true;
}

function describeFilters(filters: Filters): string | null {
  const parts: string[] = [];
  if (filters.year && Array.isArray(filters.year) && filters.year.length === 2) {
    const [from, to] = filters.year as [number, number];
    if (from || to) parts.push(`год ${from}–${to}`);
  }
  if (filters.geo?.length) parts.push(`гео: ${filters.geo.join(", ")}`);
  if (filters.material?.length) parts.push(`материал: ${filters.material.join(", ")}`);
  if (filters.process?.length) parts.push(`процесс: ${filters.process.join(", ")}`);
  if (filters.confidence?.length) parts.push(`достоверность: ${filters.confidence.join(", ")}`);
  if (filters.min_confidence != null) parts.push(`≥ ${filters.min_confidence}`);
  return parts.length ? parts.join("; ") : null;
}

function genericResponse(query: string, role: Role, filters: Filters): SearchResponse {
  const words = query.toLowerCase().split(/\W+/).filter((w) => w.length > 3);
  const ranked = factTable
    .map((fact) => ({ fact, score: words.filter((w) => `${fact.canon} ${fact.metric ?? ""} ${fact.quote}`.toLowerCase().includes(w)).length }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((x) => x.fact);
  const selected = ranked.filter((f) => passesFilters(f, filters)).slice(0, 8);
  return assemble(role, filters, "search", selected, "Недостаточно структурированных данных для полного вывода. Уточните материал, процесс, географию или числовой диапазон.");
}

function assemble(role: Role, filters: Filters, intent: SearchResponse["intent"], selectedRaw: Fact[], answerMd: string): SearchResponse {
  const visible = selectedRaw.filter((f) => passesFilters(f, filters));
  const restricted = role === "external_partner";
  const publicFacts = restricted ? visible.filter((f) => (f.sensitivity ?? "public") === "public") : visible;
  const hiddenCount = visible.length - publicFacts.length;
  const docIds = Array.from(new Set(publicFacts.map((f) => f.doc_id)));
  const docHits = emptyDocs(docIds);
  const expertsWithDocs = expertIndex.filter((e) => e.doc_ids.some((id) => docIds.includes(id)));
  const adjacentTopics = Array.from(
    new Set(publicFacts.map((f) => f.canon).filter((c) => !filters.process?.includes(c) && !filters.material?.includes(c))),
  ).slice(0, 4).map((canon) => {
    const doc = factTable.find((f) => f.canon === canon);
    return { doc_id: doc?.doc_id ?? canon, source: canon };
  });
  return {
    intent,
    answer_md: answerMd,
    facts: publicFacts,
    docs: docHits,
    experts: expertsWithDocs,
    recommendations: {
      similar_cases: docHits.slice(1),
      adjacent_topics: adjacentTopics.map((t) => ({ doc_id: t.doc_id, source: t.source })),
      experts: expertsWithDocs,
    },
    hidden_count: hiddenCount,
    filters_applied: describeFilters(filters),
  };
}

function literatureMarkdown(query: string): string {
  const scenario = resolveScenario(query);
  if (!scenario) {
    return `## Литературный обзор\n\nПо запросу «${query}» не найдено достаточно профильных публикаций. Уточните материал, процесс или период.`;
  }
  const ids = scenario.selectDocIds;
  const docsList = ids.map((id, i) => `${i + 1}. ${docById(id)?.title ?? id}`).join("\n");
  return `${scenario.answerMd(ids)}\n\n## Источники\n\n${docsList}`;
}

export class MockKnowledgeApi implements KnowledgeApi {
  async search(request: SearchRequest): Promise<SearchResponse> {
    await delay(1850);
    const { query, role, filters } = request;
    const scenario = resolveScenario(query);
    const selected = scenario ? factTable.filter((f) => scenario.selectDocIds.includes(f.doc_id)) : [];
    const response = scenario
      ? assemble(role, filters, scenario.intent, selected, scenario.answerMd(scenario.selectDocIds))
      : genericResponse(query, role, filters);
    persistence.addHistory(query);
    return clone(response);
  }
  async getFilterOptions(): Promise<FilterOptions> {
    await delay(180);
    return clone(filterOptions);
  }
  async literatureReview(request: LiteratureReviewRequest): Promise<LiteratureReviewResponse> {
    await delay(1500);
    return { markdown: literatureMarkdown(request.query) };
  }
  async graphSubgraph(request: SubgraphRequest): Promise<SubgraphResponse> {
    await delay(420);
    return clone(buildSubgraph(request.doc_ids, request.limit));
  }
  async fetchContradictions(kind?: ContradictionKind): Promise<ContradictionItem[]> {
    await delay(280);
    return fetchContradictions(kind);
  }
  async dashboardSummary(): Promise<DashboardSummary> { await delay(280); return clone(dashboardSummary); }
  async dashboardCoverageDomain(): Promise<CoverageDomain[]> { await delay(180); return clone(coverageByDomain); }
  async dashboardCoverageYear(): Promise<CoverageYear[]> { await delay(180); return clone(coverageByYear); }
  async dashboardCoverageGeo(): Promise<CoverageGeo[]> { await delay(180); return clone(coverageByGeo); }
  async dashboardRisks(): Promise<RiskZones> { await delay(280); return clone(riskZones); }
  async dashboardActivity(limit = 50): Promise<DashboardActivity[]> { await delay(280); return clone(activityFixture.slice(0, limit)); }
  async dashboardExperts(limit = 50): Promise<DashboardExpert[]> { await delay(280); return clone(expertsFixture.slice(0, limit)); }
  async dashboardCompare(request: CompareRequest): Promise<CompareResponse> { await delay(320); return clone(compareTechnologies(request.processes)); }
  async exportResult(format: ExportFormat, payload: SearchResponse): Promise<Blob> {
    await delay(200);
    if (format === "markdown") {
      const body = `# Экспорт результата\n\n## Запрос\n${payload.answer_md}\n\n## Факты (${payload.facts.length})\n` +
        payload.facts.map((f, i) => `${i + 1}. ${f.canon} · ${f.metric ?? "—"}: ${f.value_low}${f.value_high !== f.value_low ? `–${f.value_high}` : ""} · ${f.quote}`).join("\n");
      return new Blob([body], { type: "text/markdown;charset=utf-8" });
    }
    if (format === "jsonld") {
      const json = {
        "@context": { "@vocab": "https://schema.org/" },
        "@type": "Dataset",
        name: "Результат поиска",
        description: payload.answer_md,
        hasPart: payload.facts.map((f) => ({
          "@type": "Claim",
          name: `${f.canon}: ${f.metric ?? ""}`,
          value: [f.value_low, f.value_high],
          citation: f.doc_id,
        })),
      };
      return new Blob([JSON.stringify(json, null, 2)], { type: "application/ld+json;charset=utf-8" });
    }
    // pdf — %{payload.answer_md}
    const body = `%PDF-1.4\n% Экспорт результата\n% ${payload.answer_md.replace(/\n/g, " ")}\n%%EOF`;
    return new Blob([body], { type: "application/pdf" });
  }
  async notifySubscribe(user: string, query: string): Promise<NotifySubscription> {
    await delay(120);
    return { user, query, last_seen_iso: new Date().toISOString() };
  }
  async notifyUnsubscribe(): Promise<boolean> { await delay(120); return true; }
  async notifyListSubscriptions(): Promise<NotifySubscription[]> { await delay(120); return []; }
  async notifyCheck(): Promise<NotifyCheckItem[]> { await delay(120); return []; }
  async notifyMarkSeen(): Promise<void> { await delay(120); }
}