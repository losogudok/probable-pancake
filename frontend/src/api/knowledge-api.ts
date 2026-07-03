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
  FilterOptions,
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

/**
 * API-контракт «Научный клубок» — точное зеркало `API.md`.
 * Методы, не покрытые UI (notify/audit/curation), опущены до появления соответствующих страниц.
 */
export interface KnowledgeApi {
  // === §1 Поиск ===
  search(request: SearchRequest): Promise<SearchResponse>;
  getFilterOptions(): Promise<FilterOptions>;
  literatureReview(request: LiteratureReviewRequest): Promise<LiteratureReviewResponse>;

  // === §2 Граф ===
  graphSubgraph(request: SubgraphRequest): Promise<SubgraphResponse>;

  // === §4 Противоречия ===
  fetchContradictions(kind?: ContradictionKind): Promise<ContradictionItem[]>;

  // === §5 Дашборд руководителя ===
  dashboardSummary(): Promise<DashboardSummary>;
  dashboardCoverageDomain(): Promise<CoverageDomain[]>;
  dashboardCoverageYear(): Promise<CoverageYear[]>;
  dashboardCoverageGeo(): Promise<CoverageGeo[]>;
  dashboardRisks(): Promise<RiskZones>;
  dashboardActivity(limit?: number): Promise<DashboardActivity[]>;
  dashboardExperts(limit?: number): Promise<DashboardExpert[]>;
  dashboardCompare(request: CompareRequest): Promise<CompareResponse>;

  // === §6 Экспорт результата ===
  exportResult(format: ExportFormat, payload: SearchResponse): Promise<Blob>;

  // === §8 Уведомления/подписки (контракт сохранён — UI отсутствует) ===
  notifySubscribe(user: string, query: string): Promise<NotifySubscription>;
  notifyUnsubscribe(user: string, query: string): Promise<boolean>;
  notifyListSubscriptions(user?: string): Promise<NotifySubscription[]>;
  notifyCheck(user: string): Promise<NotifyCheckItem[]>;
  notifyMarkSeen(user: string, query: string): Promise<void>;
}

/** Текущая роль сессии, передаваемая в тело `/api/search`. */
export interface RoleProvider {
  role: Role;
}