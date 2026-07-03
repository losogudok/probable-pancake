export type AnalysisMode = "answer" | "literature_review" | "comparison";
export type Geography = "Russia" | "CIS" | "Foreign" | "Global" | "Unknown";
export type SourceType = "scientific_article" | "patent" | "internal_report" | "conference_paper" | "journal_issue" | "review";
export type EntityType = "Material" | "Process" | "Equipment" | "Facility" | "Experiment" | "Publication" | "Expert" | "Parameter" | "Phase" | "Technology";
export type RelationType = "uses_material" | "uses_equipment" | "has_parameter" | "described_in" | "validated_by" | "contradicts" | "performed_by" | "has_result";
export type DemoRole = "researcher" | "analyst" | "project_lead" | "admin" | "external_partner";
export type Sensitivity = "public" | "internal" | "restricted";

export interface FilterToken { id: string; label: string; value: string }
export interface NumericCondition { id: string; parameter: string; operator: string; value: number; valueTo?: number; unit: string }
export interface QueryFilters { geography?: Geography[]; yearFrom?: number; yearTo?: number; trustMin?: number; sourceTypes?: SourceType[] }
export interface ParsedQuery {
  intent: AnalysisMode;
  materials: FilterToken[];
  processes: FilterToken[];
  conditions: NumericCondition[];
  geography: Geography[];
  yearRange?: [number, number];
  language?: "ru" | "en";
}
export interface AskRequest { query: string; mode: AnalysisMode | "auto"; filters: QueryFilters }
export interface ConfidenceBreakdown { overall: number; extraction: number; sourceQuality: number; corroboration: number; label: string }
export interface Finding { id: string; title: string; text: string; sourceIds: string[]; status: "supported" | "conditional" | "insufficient" }
export interface NumericParameter { id: string; label: string; value: string; unit: string; applicability: "matches" | "conditional" | "outside"; sourceIds: string[] }
export interface ComparisonRow { id: string; method: string; geography: string; parameters: string; strengths: string; limitations: string; sourceIds: string[] }
export interface EvidenceSource {
  id: string; title: string; filename: string; authors: string[]; year?: number; geography: Geography;
  sourceType: SourceType; trust: number; quote: string; page?: number; section?: string; chunkId: string;
}
export interface Contradiction { id: string; parameter: string; context: string; values: { value: string; conditions: string; sourceId: string }[]; explanation: string; reviewStatus: "pending" | "reviewed" }
export interface Validation { id: string; statement: string; sourceIds: string[] }
export interface Expert { id: string; name: string; organization: string; expertise: string[]; publicationCount: number }
export interface KnowledgeGap { id: string; material: string; process: string; condition: string; relatedDocuments: number; recommendation: string }
export interface ProcessingMetrics { durationMs: number; documentsScanned: number; graphNodesVisited: number; pipelineVersion: string }
export interface KnowledgeNode { id: string; type: EntityType; label: string; canonical: string; aliases?: string[]; sourceCount: number; confidence?: number }
export interface KnowledgeEdge { id: string; source: string; target: string; type: RelationType; trust?: number }
export interface KnowledgeSubgraph { nodes: KnowledgeNode[]; edges: KnowledgeEdge[] }
export interface ResearchAnswer {
  id: string; query: string; mode: AnalysisMode; summary: string; confidence: ConfidenceBreakdown;
  findings: Finding[]; numericParameters: NumericParameter[]; comparisons: ComparisonRow[];
  sources: EvidenceSource[]; contradictions: Contradiction[]; validations: Validation[];
  experts: Expert[]; gaps: KnowledgeGap[]; graphPreview: KnowledgeSubgraph; processing: ProcessingMetrics;
}
export interface DocumentRecord {
  id: string; title: string; filename: string; authors: string[]; year?: number; geography: Geography;
  sourceType: SourceType; trust: number; language: "ru" | "en"; sensitivity: Sensitivity;
  factCount: number; status: "indexed" | "processing" | "error"; snippet?: string; importedAt?: string;
}
export interface DocumentSearchRequest { query?: string; geography?: Geography; sourceType?: SourceType; trustMin?: number; yearFrom?: number; sort?: "relevance" | "date" | "trust"; page?: number; pageSize?: number }
export interface DocumentPage { items: DocumentRecord[]; total: number; page: number; pageSize: number }
export interface EntitySummary { id: string; label: string; type: EntityType; sourceCount: number }
export interface GraphRequest { entityId: string; depth: 1 | 2 | 3 }
export interface QualityItemGroup { contradictions: Contradiction[]; validations: Validation[]; gaps: KnowledgeGap[] }
export interface DashboardData {
  totals: { documents: number; facts: number; nodes: number; edges: number; experts: number; contradictions: number; gaps: number; confidence: number };
  byYear: { year: number; count: number }[]; byDomain: { name: string; value: number }[];
  byGeography: { name: string; value: number }[]; bySourceType: { name: string; value: number }[];
  coverage: { material: string; process: string; score: number }[]; weakTopics: { topic: string; documents: number }[];
}
export interface UploadRequest { files: File[]; category: SourceType; language: "ru" | "en"; geography: Geography; sensitivity: Sensitivity; signal?: AbortSignal }
export interface UploadProgress { fileName: string; stage: "upload" | "recognition" | "normalization" | "extraction" | "indexing" | "complete"; percent: number }
export type ImportedDocument = DocumentRecord;
export interface ProcessingStage { id: string; label: string }
