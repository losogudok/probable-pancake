import type { AskRequest, DashboardData, DocumentPage, DocumentSearchRequest, EntitySummary, GraphRequest, ImportedDocument, KnowledgeSubgraph, ParsedQuery, QualityItemGroup, ResearchAnswer, UploadProgress, UploadRequest } from "../domain/types";

export interface KnowledgeApi {
  parseQuery(query: string): Promise<ParsedQuery>;
  ask(request: AskRequest): Promise<ResearchAnswer>;
  searchDocuments(request: DocumentSearchRequest): Promise<DocumentPage>;
  suggestEntities(query: string): Promise<EntitySummary[]>;
  getGraph(request: GraphRequest): Promise<KnowledgeSubgraph>;
  getQuality(): Promise<QualityItemGroup>;
  getDashboard(): Promise<DashboardData>;
  uploadDocuments(request: UploadRequest, onProgress: (event: UploadProgress) => void): Promise<ImportedDocument[]>;
}
