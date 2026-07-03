// API-контракт «Научный клубок» — см. ../API.md. Реальные формы возвратов бэка.

/** Роли (RBAC). Передаются в теле запроса. */
export type Role = "researcher" | "analyst" | "project_lead" | "admin" | "external_partner";
/** Совместимый алиас для старых импортов UI. */
export type DemoRole = Role;

/** Чувствительность факта/документа — используется моком для отсечения `external_partner`. */
export type Sensitivity = "public" | "internal" | "secret";

/** 8 онтологических типов узлов + служебные для графа-виз. */
export type EntityType =
  | "Material" | "Process" | "Equipment" | "Property" | "Experiment"
  | "Publication" | "Expert" | "Facility"
  | "Document" | "Parameter" | "Phase" | "Condition" | "Domain" | "Claim";

/** Типы рёбер графа (см. API.md §0). */
export type RelationType =
  | "USES_MATERIAL" | "OPERATES_AT_CONDITION" | "PRODUCES_OUTPUT" | "DESCRIBED_IN"
  | "VALIDATED_BY" | "CONTRADICTS" | "AUTHORED_BY" | "IN_DOMAIN"
  | "SHOWED" | "MEASURES" | "HAS_PARAM";

/** Канон единиц (см. API.md §1 таблица unit → отображение). */
export type Unit = "pct" | "mg_L" | "g_t" | "degC" | "pH" | "A_m2" | "t_day" | "m3_h";

/** Уровень достоверности словом. `>=0.8`→высокая, `>=0.5`→средняя, иначе→низкая. */
export type ConfidenceLevel = "высокая" | "средняя" | "низкая";
export function confidenceLabel(value: number): ConfidenceLevel {
  if (value >= 0.8) return "высокая";
  if (value >= 0.5) return "средняя";
  return "низкая";
}

/** === Filters — тело запроса поиска, все поля опциональны === */
export interface Filters {
  /** список годов из multiselect → диапазон [min,max]; ИЛИ [] (нет фильтра) */
  year?: [number, number] | [];
  /** нормализованные: "RU" | "WORLD" | конкретная страна */
  geo?: string[];
  /** подстрока по canon сущности */
  material?: string[];
  /** подстрока по canon сущности */
  process?: string[];
  /** уровни-слова (UI-хинт) */
  confidence?: ConfidenceLevel[];
  /** число 0..1 — реальный порог отсечения */
  min_confidence?: number;
}

/** === /api/search === */
export type SearchIntent = "numeric" | "search" | "expert" | "listing";

export interface Expert {
  name: string;
  doc_ids: string[];
  domains: string[];
}

export interface Fact {
  canon: string;
  metric: string | null;
  value_low: number;
  value_high: number;
  unit: Unit | null;
  phase: string | null;
  quote: string;
  doc_id: string;
  year: number | null;
  source: string | null;
  track: string | null;
  ref?: string | null;
  confidence?: number;
  extracted_at?: string | null;
  /** не из API.md — мок использует для отсечения `external_partner` */
  sensitivity?: Sensitivity;
}

export interface DocHit {
  doc_id: string;
  source: string;
}

export interface Recommendations {
  similar_cases: DocHit[];
  adjacent_topics: DocHit[];
  experts: Expert[];
}

export interface SearchResponse {
  intent: SearchIntent;
  answer_md: string;
  facts: Fact[];
  docs: DocHit[];
  experts: Expert[];
  recommendations: Recommendations;
  hidden_count: number;
  filters_applied: string | null;
}

export interface SearchRequest {
  query: string;
  role: Role;
  filters: Filters;
}

/** === GET /api/filters/options === */
export interface FilterOptions {
  years: number[];
  geos: string[];
  materials: string[];
  processes: string[];
  confidence_levels: ConfidenceLevel[];
}

/** === POST /api/literature-review === */
export interface LiteratureReviewRequest {
  query: string;
  filters?: Filters;
}
export interface LiteratureReviewResponse {
  markdown: string;
}

/** === POST /api/graph/subgraph === */
export interface GraphNodeRef {
  id: string;
  label: string;
  type: EntityType;
}
export interface GraphEdgeRef {
  src: string;
  dst: string;
  type: RelationType;
}
export interface SubgraphResponse {
  nodes: GraphNodeRef[];
  edges: GraphEdgeRef[];
}
export interface SubgraphRequest {
  doc_ids: string[];
  limit: number;
}

/** === GET /api/contradictions?kind= === */
export type ContradictionKind = "ru_vs_world" | "method_vs_method";
export interface ContradictionItem {
  rel: "CONTRADICTS" | "VALIDATED_BY";
  kind?: string | null;
  src: string;
  dst: string;
  sources?: unknown | null;
}

/** === Дашборд руководителя === */
export interface DashboardSummary {
  docs: number;
  facts: number;
  experts: number;
  domains: number;
  contradictions: number;
  ru: number;
  world: number;
  geo_unknown: number;
  ru_share: number;
  world_share: number;
  docs_with_facts: number;
  fact_coverage: number;
}

export interface CoverageDomain {
  domain: string;
  documents: number;
  facts: number;
  experts: number;
}
export interface CoverageYear {
  year: number;
  documents: number;
  facts: number;
}
export interface CoverageGeo {
  geo: string;
  documents: number;
  facts: number;
}
export interface RiskEntity {
  entity: string;
  type: string;
  sources: number;
}
export interface RiskZones {
  low_sources: RiskEntity[];
  contradictions: ContradictionItem[];
  only_ru: RiskEntity[];
  only_world: RiskEntity[];
}
export interface DashboardActivity {
  doc_id: string;
  year: number | null;
  geo: string;
  facts: number;
  experts: number;
  last_extracted: string;
}
export interface DashboardExpert {
  expert: string;
  documents: number;
  domains: number;
  domain_list: string[];
}

/** === POST /api/dashboard/compare === */
export interface CompareRequest {
  processes: string[];
}
export interface CompareAxisStat {
  min: number;
  max: number;
  unit: Unit;
  unit_ru: string;
  samples: number;
}
export interface CompareRow {
  process: string;
  [axis: string]: CompareAxisStat | boolean | null | unknown;
}
export interface CompareResponse {
  axes: string[];
  meta: { unavailable: string[] };
  rows: CompareRow[];
}

/** === POST /api/export/{format} — тело: объект ответа /api/search целиком === */
export type ExportFormat = "markdown" | "jsonld" | "pdf";

/** === Уведомления/подписки (API.md §8) — контракт сохранён, UI отсутствует === */
export interface NotifySubscription {
  user: string;
  query: string;
  last_seen_iso: string;
}
export interface NotifyCheckItem {
  query: string;
  new_count: number;
  sample: { doc_id: string; canon: string; metric: string; quote: string; when: string }[];
}

/** === Аудит (API.md §9) — контракт сохранён, UI отсутствует === */
export type AuditEvent = "query" | "view" | "export" | "edit" | "subscribe";
export interface AuditEntry {
  ts: string;
  role: Role;
  event: AuditEvent;
  payload: Record<string, unknown>;
}