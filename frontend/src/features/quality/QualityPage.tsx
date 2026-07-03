import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, CircleHelp, FlaskConical, GitCompareArrows, ShieldCheck, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../../api/api-provider";
import { Badge, ErrorState, LoadingBlock, PageHeader } from "../../components/ui/Primitives";
import s from "../../styles/ui.module.css";

type Tab = "contradictions" | "validations" | "gaps";
export function QualityPage() {
  const [tab, setTab] = useState<Tab>("contradictions"); const data = useQuery({ queryKey: ["quality"], queryFn: api.getQuality.bind(api) });
  return <div><PageHeader eyebrow="ВЕРИФИКАЦИЯ" title="Качество знаний" description="Проверяйте расхождения, подтверждения и недостающие исследования."/>
    <div className={s.qualitySummary}><div><span className={s.qualityIconRed}><TriangleAlert/></span><strong>{data.data?.contradictions.length ?? "—"}</strong><small>требуют проверки</small></div><div><span className={s.qualityIconGreen}><ShieldCheck/></span><strong>{data.data?.validations.length ?? "—"}</strong><small>подтверждены</small></div><div><span className={s.qualityIconAmber}><CircleHelp/></span><strong>{data.data?.gaps.length ?? "—"}</strong><small>пробелов</small></div></div>
    <div className={s.qualityTabs}>{(["contradictions","validations","gaps"] as const).map((item) => <button key={item} className={tab === item ? s.qualityTabActive : ""} onClick={() => setTab(item)}>{item === "contradictions" ? "Противоречия" : item === "validations" ? "Подтверждения" : "Пробелы"}<span>{data.data?.[item].length ?? 0}</span></button>)}</div>
    {data.isLoading ? <LoadingBlock/> : data.isError ? <ErrorState message={data.error.message}/> : <div className={s.qualityList}>
      {tab === "contradictions" && data.data?.contradictions.map((item) => <article className={s.qualityCard} key={item.id}><header><span className={s.qualityIconRed}><GitCompareArrows/></span><div><Badge tone="red">Требует внимания</Badge><h3>{item.parameter}</h3><p>{item.context}</p></div><Badge tone={item.reviewStatus === "reviewed" ? "green" : "amber"}>{item.reviewStatus === "reviewed" ? "Проверено" : "Ожидает эксперта"}</Badge></header><div className={s.valueComparison}>{item.values.map((value, index) => <div key={value.sourceId}><small>Источник {index + 1}</small><strong>{value.value}</strong><span>{value.conditions}</span></div>)}</div><footer><p><TriangleAlert/>{item.explanation}</p><button>Открыть источники <ArrowRight/></button></footer></article>)}
      {tab === "validations" && data.data?.validations.map((item) => <article className={`${s.qualityCard} ${s.validationCard}`} key={item.id}><header><span className={s.qualityIconGreen}><CheckCircle2/></span><div><Badge tone="green">Подтверждено</Badge><h3>{item.statement}</h3><p>{item.sourceIds.length} независимых источника поддерживают вывод</p></div></header><footer><span>Источники: {item.sourceIds.join(", ")}</span><button>Показать доказательства <ArrowRight/></button></footer></article>)}
      {tab === "gaps" && data.data?.gaps.map((item) => <article className={`${s.qualityCard} ${s.gapCard}`} key={item.id}><header><span className={s.qualityIconAmber}><FlaskConical/></span><div><Badge tone="amber">Пробел знаний</Badge><h3>{item.material} × {item.process}</h3><p>{item.condition}</p></div></header><div className={s.gapRecommendation}><b>Рекомендуемый следующий шаг</b><p>{item.recommendation}</p></div><footer><span>Связанных документов: {item.relatedDocuments}</span><Link to={`/?gap=${encodeURIComponent(item.material + " " + item.process)}`}>Создать запрос <ArrowRight/></Link></footer></article>)}
    </div>}
  </div>;
}
