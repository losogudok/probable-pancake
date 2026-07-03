import type { KnowledgeApi } from "./knowledge-api";
import type { AskRequest, DashboardData, DocumentPage, DocumentSearchRequest, EntitySummary, GraphRequest, ImportedDocument, KnowledgeSubgraph, ParsedQuery, QualityItemGroup, ResearchAnswer, UploadProgress, UploadRequest } from "../domain/types";

const base = import.meta.env.VITE_API_BASE_URL ?? "";
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!response.ok) throw new Error(`API ${response.status}: ${response.statusText}`);
  return response.json() as Promise<T>;
}

export class HttpKnowledgeApi implements KnowledgeApi {
  parseQuery(_query: string): Promise<ParsedQuery> { throw new Error("HTTP parseQuery contract is not implemented yet"); }
  ask(value: AskRequest): Promise<ResearchAnswer> { return request("/api/ask", { method: "POST", body: JSON.stringify(value) }); }
  searchDocuments(value: DocumentSearchRequest): Promise<DocumentPage> { const params = new URLSearchParams(Object.entries(value).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])); return request(`/api/documents?${params}`); }
  async suggestEntities(query: string): Promise<EntitySummary[]> { const data = await request<{ entities: EntitySummary[] }>(`/api/entities?name=${encodeURIComponent(query)}&limit=8`); return data.entities; }
  getGraph(value: GraphRequest): Promise<KnowledgeSubgraph> { return request(`/api/graph/${encodeURIComponent(value.entityId)}?depth=${value.depth}&limit=80`); }
  async getQuality(): Promise<QualityItemGroup> { const [c, g] = await Promise.all([request<{ contradictions: QualityItemGroup["contradictions"] }>("/api/contradictions"), request<{ gaps: QualityItemGroup["gaps"] }>("/api/gaps")]); return { contradictions: c.contradictions, validations: [], gaps: g.gaps }; }
  getDashboard(): Promise<DashboardData> { return request("/api/dashboard"); }
  uploadDocuments(_value: UploadRequest, _onProgress: (event: UploadProgress) => void): Promise<ImportedDocument[]> { throw new Error("HTTP upload contract is not implemented yet"); }
}
