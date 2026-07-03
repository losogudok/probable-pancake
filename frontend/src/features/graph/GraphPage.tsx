// @ts-nocheck
// Заморожено: раздел временно убран из маршрутов (ждёт соответствующих эндпоинтов API.md §2/§нет).
// См. app/router.tsx. Сохранён для повторного подключения в будущих версиях API.
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Background, Controls, MarkerType, MiniMap, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { ArrowRight, BookOpen, GitFork, Search, X } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../../api/api-provider";
import { entityLabels } from "../../domain/labels";
import type { EntityType, KnowledgeNode } from "../../domain/types";
import { Badge, ErrorState, LoadingBlock, PageHeader } from "../../components/ui/Primitives";
import s from "../../styles/ui.module.css";

const colors: Record<EntityType, string> = { Process: "#2563eb", Material: "#d97706", Equipment: "#059669", Facility: "#64748b", Experiment: "#7c3aed", Publication: "#9333ea", Expert: "#ea580c", Parameter: "#dc2626", Phase: "#0891b2", Technology: "#4f46e5" };

export function GraphPage() {
  const [term, setTerm] = useState("электроэкстракция"); const [rootId, setRootId] = useState("process-ew"); const [depth, setDepth] = useState<1|2|3>(2); const [selected, setSelected] = useState<KnowledgeNode | null>(null);
  const suggestions = useQuery({ queryKey: ["entities", term], queryFn: () => api.suggestEntities(term), enabled: term.length > 1 });
  const graph = useQuery({ queryKey: ["graph", rootId, depth], queryFn: () => api.getGraph({ entityId: rootId, depth }) });
  const flow = useMemo(() => layout(graph.data?.nodes ?? [], graph.data?.edges ?? [], rootId), [graph.data, rootId]);
  return <div>
    <PageHeader eyebrow="КАРТА СВЯЗЕЙ" title="Граф знаний" description="Исследуйте локальную окрестность сущности без шума полного графа." />
    <div className={s.graphToolbar}><div className={s.entitySearch}><Search/><input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Материал, процесс, оборудование…"/>{suggestions.data && term && <div className={s.suggestions}>{suggestions.data.map((item) => <button key={item.id} onClick={() => { setRootId(item.id); setTerm(item.label); setSelected(null); }}><span style={{ background: colors[item.type] }}/><b>{item.label}</b><small>{entityLabels[item.type]} · {item.sourceCount} источников</small></button>)}</div>}</div><div className={s.depthControl}><span>Глубина</span>{([1,2,3] as const).map((value) => <button key={value} className={depth === value ? s.depthActive : ""} onClick={() => setDepth(value)}>{value}</button>)}</div><div className={s.graphLegend}>{(["Process","Material","Equipment","Parameter"] as EntityType[]).map((type) => <span key={type}><i style={{ background: colors[type] }}/>{entityLabels[type]}</span>)}</div></div>
    <section className={s.graphWorkspace}>{graph.isLoading ? <LoadingBlock label="Строим окрестность сущности"/> : graph.isError ? <ErrorState message={graph.error.message}/> : <div className={s.flowCanvas}><ReactFlow nodes={flow.nodes} edges={flow.edges} onNodeClick={(_, node) => setSelected(graph.data?.nodes.find((item) => item.id === node.id) ?? null)} fitView minZoom={0.35} maxZoom={1.8} proOptions={{ hideAttribution: true }}><Background gap={22} color="#d9dee7"/><Controls/><MiniMap className={s.miniMap} nodeColor={(node) => String(node.style?.background ?? "#94a3b8")} pannable zoomable/></ReactFlow></div>}
      {selected && <aside className={s.nodePanel}><button className={s.closeButton} onClick={() => setSelected(null)} aria-label="Закрыть"><X/></button><span className={s.nodeType} style={{ color: colors[selected.type] }}>{entityLabels[selected.type]}</span><h2>{selected.label}</h2><p className={s.canonical}>{selected.canonical}</p>{selected.aliases?.length ? <div className={s.aliasList}>{selected.aliases.map((alias) => <Badge key={alias}>{alias}</Badge>)}</div> : null}<div className={s.nodeStats}><div><strong>{selected.sourceCount}</strong><span>источников</span></div><div><strong>{selected.confidence ?? "—"}%</strong><span>уверенность</span></div></div><h3>Связи</h3><div className={s.nodeRelations}>{graph.data?.edges.filter((edge) => edge.source === selected.id || edge.target === selected.id).map((edge) => <span key={edge.id}><GitFork/>{edge.type}</span>)}</div><button className={s.secondaryButton} onClick={() => { setRootId(selected.id); setSelected(null); }}>Раскрыть связи <GitFork/></button><Link className={s.primaryLink} to={`/?entity=${encodeURIComponent(selected.canonical)}`}>Искать по сущности <ArrowRight/></Link><div className={s.nodeNote}><BookOpen/>Показаны связи с доказательствами из корпуса</div></aside>}
    </section>
  </div>;
}

function layout(nodes: KnowledgeNode[], edges: { id: string; source: string; target: string; type: string }[], rootId: string): { nodes: Node[]; edges: Edge[] } {
  const root = nodes.findIndex((node) => node.id === rootId); const ordered = root > 0 ? [nodes[root], ...nodes.filter((_, index) => index !== root)] : nodes;
  const flowNodes = ordered.map((node, index) => { const level = index === 0 ? 0 : index <= 6 ? 1 : 2; const levelItems = level === 1 ? Math.min(6, ordered.length - 1) : Math.max(1, ordered.length - 7); const local = level === 1 ? index - 1 : index - 7; const angle = (local / levelItems) * Math.PI * 2 - Math.PI / 2; const radius = level === 0 ? 0 : level === 1 ? 230 : 390; return { id: node.id, position: { x: 420 + Math.cos(angle) * radius, y: 280 + Math.sin(angle) * radius }, data: { label: node.label }, style: { background: colors[node.type], color: "white", border: "3px solid white", boxShadow: "0 4px 18px #1f293733", borderRadius: 12, width: index === 0 ? 180 : 150, padding: 12, fontWeight: 700, fontSize: 13 } }; });
  const flowEdges = edges.map((edge) => ({ id: edge.id, source: edge.source, target: edge.target, label: edge.type, labelStyle: { fill: "#64748b", fontSize: 9 }, style: { stroke: "#94a3b8", strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: "#94a3b8" } }));
  return { nodes: flowNodes, edges: flowEdges };
}
