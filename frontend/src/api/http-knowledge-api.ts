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
  FilterOptions,
  LiteratureReviewRequest,
  LiteratureReviewResponse,
  NotifyCheckItem,
  NotifySubscription,
  RiskZones,
  SearchRequest,
  SearchResponse,
  SubgraphRequest,
  SubgraphResponse,
} from "../domain/types";

const base = import.meta.env.VITE_API_BASE_URL ?? "";

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!response.ok) throw new Error(`API ${response.status}: ${response.statusText}`);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function blobRequest(path: string, init: RequestInit): Promise<Blob> {
  const response = await fetch(`${base}${path}`, init);
  if (!response.ok) throw new Error(`API ${response.status}: ${response.statusText}`);
  return response.blob();
}

/**
 * HTTP-адаптер — точное зеркало API.md.
 * Роль передаётся в теле `/api/search` (поле `role`), см. §0.
 */
export class HttpKnowledgeApi implements KnowledgeApi {
  search(request: SearchRequest): Promise<SearchResponse> {
    return jsonRequest("/api/search", { method: "POST", body: JSON.stringify(request) });
  }
  getFilterOptions(): Promise<FilterOptions> {
    return jsonRequest("/api/filters/options");
  }
  literatureReview(request: LiteratureReviewRequest): Promise<LiteratureReviewResponse> {
    return jsonRequest("/api/literature-review", { method: "POST", body: JSON.stringify(request) });
  }
  graphSubgraph(request: SubgraphRequest): Promise<SubgraphResponse> {
    return jsonRequest("/api/graph/subgraph", { method: "POST", body: JSON.stringify(request) });
  }
  fetchContradictions(kind?: ContradictionKind): Promise<ContradictionItem[]> {
    const qs = kind ? `?kind=${encodeURIComponent(kind)}` : "";
    return jsonRequest(`/api/contradictions${qs}`);
  }
  dashboardSummary(): Promise<DashboardSummary> { return jsonRequest("/api/dashboard/summary"); }
  dashboardCoverageDomain(): Promise<CoverageDomain[]> { return jsonRequest("/api/dashboard/coverage/domain"); }
  dashboardCoverageYear(): Promise<CoverageYear[]> { return jsonRequest("/api/dashboard/coverage/year"); }
  dashboardCoverageGeo(): Promise<CoverageGeo[]> { return jsonRequest("/api/dashboard/coverage/geo"); }
  dashboardRisks(): Promise<RiskZones> { return jsonRequest("/api/dashboard/risks"); }
  dashboardActivity(limit = 50): Promise<DashboardActivity[]> { return jsonRequest(`/api/dashboard/activity?limit=${limit}`); }
  dashboardExperts(limit = 50): Promise<DashboardExpert[]> { return jsonRequest(`/api/dashboard/experts?limit=${limit}`); }
  dashboardCompare(request: CompareRequest): Promise<CompareResponse> {
    return jsonRequest("/api/dashboard/compare", { method: "POST", body: JSON.stringify(request) });
  }
  exportResult(format: ExportFormat, payload: SearchResponse): Promise<Blob> {
    return blobRequest(`/api/export/${format}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  }
  notifySubscribe(user: string, query: string): Promise<NotifySubscription> {
    return jsonRequest("/api/notify/subscribe", { method: "POST", body: JSON.stringify({ user, query }) });
  }
  notifyUnsubscribe(user: string, query: string): Promise<boolean> {
    return jsonRequest("/api/notify/unsubscribe", { method: "POST", body: JSON.stringify({ user, query }) });
  }
  notifyListSubscriptions(user?: string): Promise<NotifySubscription[]> {
    const qs = user ? `?user=${encodeURIComponent(user)}` : "";
    return jsonRequest(`/api/notify/subscriptions${qs}`);
  }
  notifyCheck(user: string): Promise<NotifyCheckItem[]> {
    return jsonRequest(`/api/notify/check?user=${encodeURIComponent(user)}`);
  }
  notifyMarkSeen(user: string, query: string): Promise<void> {
    return jsonRequest("/api/notify/mark-seen", { method: "POST", body: JSON.stringify({ user, query }) });
  }
}