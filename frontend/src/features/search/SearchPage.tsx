import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, BookOpen, ChevronDown, ChevronUp, Download, FileJson, FileText, Filter, Lightbulb, RotateCcw, ShieldOff, Sparkles, TriangleAlert, Users } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { api, isMockMode } from "../../api/api-provider";
import { confidenceLabel, type ConfidenceLevel, type SearchResponse } from "../../domain/types";
import { confidenceLabels, geoOptions, intentLabels, unitLabels } from "../../domain/labels";
import { useSession } from "../../app/session-context";
import { Badge } from "../../components/ui/Primitives";
import { downloadExport } from "../export/export";
import { buildFilters, type LocalFilters } from "./filters";
import s from "../../styles/ui.module.css";

const examples = [
  { label: "Циркуляция католита", query: "Какая скорость циркуляции католита при электроэкстракции никеля?" },
  { label: "Обессоливание воды", query: "Какое обессоливание воды применять при сульфатах и хлоридах 200–300 мг/л и сухом остатке 1930 мг/л?" },
  { label: "Au, Ag и МПГ", query: "Распределение Au, Ag и МПГ между штейном и шлаком в плавке" },
  { label: "Шахтные воды", query: "Закачка шахтных вод в глубокие горизонты: российская практика" },
];

type Mode = "search" | "literature_review";

function formatValue(fact: { value_low: number; value_high: number; unit: keyof typeof unitLabels | null }) {
  const range = fact.value_high !== fact.value_low ? `${fact.value_low}–${fact.value_high}` : `${fact.value_low}`;
  const unit = fact.unit ? ` ${unitLabels[fact.unit]}` : "";
  return `${range}${unit}`;
}

export function SearchPage() {
  const { role, history, refreshHistory } = useSession();
  const [query, setQuery] = useState(""); const [mode, setMode] = useState<Mode>("search");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<LocalFilters>({ geo: [], material: [], process: [], confidence: [], minConfidence: 0 });
  const [answer, setAnswer] = useState<SearchResponse | null>(null);
  const [literature, setLiterature] = useState<{ markdown: string } | null>(null);

  const options = useQuery({ queryKey: ["filter-options"], queryFn: () => api.getFilterOptions() });

  const search = useMutation<SearchResponse, Error, { query: string; filters: LocalFilters; role: typeof role }>({
    mutationFn: (req) => api.search({ query: req.query, role: req.role, filters: buildFilters(req.filters) }),
    onSuccess: (result) => { setAnswer(result); setLiterature(null); refreshHistory(); },
  });
  const review = useMutation<{ markdown: string }, Error, { query: string }>({
    mutationFn: (req) => api.literatureReview({ query: req.query }),
    onSuccess: (result) => { setLiterature(result); setAnswer(null); refreshHistory(); },
  });

  const pending = search.isPending || review.isPending;

  function submit(nextQuery = query) {
    if (!nextQuery.trim()) return;
    setQuery(nextQuery);
    if (mode === "literature_review") { setAnswer(null); review.mutate({ query: nextQuery }); }
    else { setLiterature(null); search.mutate({ query: nextQuery, filters, role }); }
  }

  return <div className={s.searchPage}>
    <section className={`${s.hero} ${answer || literature ? s.heroCompact : ""}`}>
      <div className={s.heroIntro}>{isMockMode && <Badge tone="blue"><Sparkles size={13}/> Автономное демо</Badge>}<h1>Знания R&D — в одном ответе</h1><p>Задайте вопрос о материалах, процессах и условиях. Система найдёт связи, проверит числа и покажет доказательства.</p></div>
      <div className={s.queryCard}>
        <div className={s.modeTabs} aria-label="Режим анализа">{(["search", "literature_review"] as const).map((item) => <button key={item} className={mode === item ? s.modeActive : ""} onClick={() => setMode(item)}>{item === "search" ? "Поиск" : "Литобзор"}</button>)}</div>
        <div className={s.queryInputWrap}><textarea value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(event) => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") submit(); }} placeholder="Например: сравните способы циркуляции католита при электроэкстракции никеля…" rows={answer || literature ? 2 : 3}/><button className={s.primaryButton} disabled={!query.trim() || pending} onClick={() => submit()}>{pending ? "Анализируем" : "Исследовать"}<ArrowRight size={18}/></button></div>
        <div className={s.queryFooter}><button className={s.textButton} onClick={() => setFiltersOpen((v) => !v)}><Filter size={16}/>Фильтры{filtersOpen ? <ChevronUp size={15}/> : <ChevronDown size={15}/>}</button><span>Ctrl + Enter</span></div>
        {filtersOpen && mode === "search" && (
          <div className={s.filterPanel}>
            <label>География
              <select multiple value={filters.geo} onChange={(e) => setFilters((f) => ({ ...f, geo: Array.from(e.target.selectedOptions).map((o) => o.value) }))}>
                {geoOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                {(options.data?.geos ?? []).filter((g) => !geoOptions.some((o) => o.value === g)).map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </label>
            <label>Материал (через запятую)<input value={filters.material.join(", ")} onChange={(e) => setFilters((f) => ({ ...f, material: e.target.value.split(",").map((m) => m.trim()).filter(Boolean) }))} placeholder="никель, медь"/></label>
            <label>Процесс (через запятую)<input value={filters.process.join(", ")} onChange={(e) => setFilters((f) => ({ ...f, process: e.target.value.split(",").map((p) => p.trim()).filter(Boolean) }))} placeholder="электроэкстракция"/></label>
            <label>Достоверность
              <select multiple value={filters.confidence} onChange={(e) => setFilters((f) => ({ ...f, confidence: Array.from(e.target.selectedOptions).map((o) => o.value) as ConfidenceLevel[] }))}>
                {options.data?.confidence_levels.map((lvl) => <option key={lvl} value={lvl}>{confidenceLabels[lvl]}</option>)}
              </select>
            </label>
            <label>Порог достоверности (0–1)<input type="range" min={0} max={1} step={0.1} value={filters.minConfidence} onChange={(e) => setFilters((f) => ({ ...f, minConfidence: Number(e.target.value) }))}/><span>{filters.minConfidence.toFixed(1)}</span></label>
          </div>
        )}
      </div>
      {!answer && !literature && !pending && <><div className={s.exampleRow}>{examples.map((example) => <button key={example.label} onClick={() => { setQuery(example.query); submit(example.query); }}><span>{example.label}</span><ArrowRight size={15}/></button>)}</div>{history.length > 0 && (<div className={s.history}><Lightbulb size={16}/><span>Недавние:</span>{history.slice(0, 3).map((item) => <button key={item} onClick={() => setQuery(item)}>{item}</button>)}</div>)}</>}
    </section>

    {pending && <section className={s.processing} aria-live="polite"><div className={s.processingOrb}><Sparkles/></div><div><h2>{mode === "search" ? "Ищем факты в корпусе" : "Готовим литобзор"}</h2><p>Сопоставляем запрос с документами и графом знаний</p></div></section>}
    {(search.isError || review.isError) && <div className={s.errorBanner}><TriangleAlert/>Ошибка: {search.error?.message ?? review.error?.message}<button onClick={() => submit()}><RotateCcw size={16}/>Повторить</button></div>}
    {answer && <AnswerView answer={answer} onExport={(fmt) => downloadExport(fmt, answer)} />}
    {literature && <LiteratureView markdown={literature.markdown} />}
  </div>;
}

function AnswerView({ answer, onExport }: { answer: SearchResponse; onExport: (fmt: "markdown" | "jsonld" | "pdf") => void }) {
  return <article className={s.answerView}>
    <header className={s.answerHeader}>
      <div><div className={s.eyebrow}><Badge tone="blue">{intentLabels[answer.intent]}</Badge></div><h2>Результат исследования</h2><div className={s.answerMeta}><span><BookOpen/> {answer.facts.length} фактов</span><span><FileText/> {answer.docs.length} источника</span></div></div>
      <div className={s.exportGroup}><button onClick={() => onExport("markdown")} title="Markdown"><FileText/>MD</button><button onClick={() => onExport("jsonld")} title="JSON-LD"><FileJson/>JSON-LD</button><button onClick={() => onExport("pdf")} title="PDF"><Download/>PDF</button></div>
    </header>
    {answer.hidden_count > 0 && <div className={s.errorBanner}><ShieldOff/>По вашему уровню доступа скрыто {answer.hidden_count} {answer.hidden_count === 1 ? "факт" : "фактов"}</div>}
    <div className={s.answerGrid}><div className={s.answerMain}>
      <section className={`${s.panel} ${s.summaryPanel}`}><div className={s.panelIcon}><Lightbulb/></div><div><h3>Ответ</h3><ReactMarkdown>{answer.answer_md}</ReactMarkdown></div></section>
      {answer.facts.length > 0 && (
        <section className={s.panel}><SectionTitle icon={<FileText/>} title={`Факты · ${answer.facts.length}`} subtitle="Карточки результата поиска"/><div className={s.comparisonTable}><div className={s.tableHead}><span>Сущность</span><span>Параметр</span><span>Значение</span><span>Фаза</span><span>Источник</span><span>Достоверность</span></div>{answer.facts.map((fact, i) => <div className={s.tableRow} key={`${fact.doc_id}-${i}`}><span data-label="Сущность"><b>{fact.canon}</b></span><span data-label="Параметр">{fact.metric ?? "—"}</span><span data-label="Значение"><b>{formatValue(fact)}</b></span><span data-label="Фаза">{fact.phase ?? "—"}</span><span data-label="Источник"><small title={fact.quote}>{fact.doc_id.slice(0, 4)}…{fact.year ?? "—"}</small></span><span data-label="Достоверность"><Badge tone={toneForConfidence(fact.confidence)}>{fact.confidence != null ? confidenceLabel(fact.confidence) : "средняя"}</Badge></span></div>)}</div></section>
      )}
      {answer.experts.length > 0 && (
        <section className={s.panel}><SectionTitle icon={<Users/>} title="Эксперты" subtitle="Носители компетенций по теме"/><div className={s.expertGrid}>{answer.experts.map((expert) => <div key={expert.name} className={s.expertCard}><span>{expert.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}</span><div><b>{expert.name}</b><small>{expert.domains.join(" · ")}</small><p>{expert.doc_ids.length} док.</p></div></div>)}</div></section>
      )}
      {(answer.recommendations.similar_cases.length > 0 || answer.recommendations.adjacent_topics.length > 0) && (
        <section className={s.panel}><SectionTitle icon={<Lightbulb/>} title="Смежные темы" subtitle="Граф-соседи процессов и материалов"/><div className={s.tokenList}>{[...answer.recommendations.similar_cases, ...answer.recommendations.adjacent_topics].map((hit, i) => <button key={`${hit.doc_id}-${i}`} className={s.token}>{hit.source}</button>)}</div></section>
      )}
    </div></div>
  </article>;
}

function LiteratureView({ markdown }: { markdown: string }) {
  return <article className={s.answerView}><header className={s.answerHeader}><div><div className={s.eyebrow}><Badge tone="blue">Литературный обзор</Badge></div><h2>Литобзор</h2></div></header><div className={s.answerGrid}><div className={s.answerMain}><section className={`${s.panel} ${s.summaryPanel}`}><div className={s.panelIcon}><BookOpen/></div><div><h3>Обзор</h3><ReactMarkdown>{markdown}</ReactMarkdown></div></section></div></div></article>;
}

function toneForConfidence(value?: number): "green" | "amber" | "red" {
  if (value == null) return "amber";
  if (value >= 0.8) return "green";
  if (value >= 0.5) return "amber";
  return "red";
}
function SectionTitle({ icon, title, subtitle }: { icon: React.ReactNode; title: string; subtitle: string }) { return <div className={s.sectionTitle}><span>{icon}</span><div><h3>{title}</h3><p>{subtitle}</p></div></div>; }