import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, GitCompareArrows, ShieldCheck, TriangleAlert } from "lucide-react";
import { api } from "../../api/api-provider";
import type { ContradictionKind } from "../../domain/types";
import { relationLabels } from "../../domain/labels";
import { Badge, ErrorState, LoadingBlock, PageHeader } from "../../components/ui/Primitives";
import s from "../../styles/ui.module.css";

const kindOptions: { value: ContradictionKind | ""; label: string }[] = [
  { value: "", label: "Все виды" },
  { value: "ru_vs_world", label: "Россия vs мир" },
  { value: "method_vs_method", label: "Метод vs метод" },
];

export function QualityPage() {
  const [kind, setKind] = useState<ContradictionKind | "">("");
  const data = useQuery({ queryKey: ["contradictions", kind], queryFn: () => api.fetchContradictions(kind || undefined) });
  return <div><PageHeader eyebrow="ВЕРИФИКАЦИЯ" title="Противоречия" description="Числовые расхождения между источниками. Карточки A/B — через doc_id."/>
    <div className={s.qualitySummary}>
      <div><span className={s.qualityIconRed}><TriangleAlert/></span><strong>{data.data?.length ?? "—"}</strong><small>противоречий</small></div>
      <div><span className={s.qualityIconGreen}><ShieldCheck/></span><strong>{data.data?.filter((c) => c.rel === "VALIDATED_BY").length ?? "—"}</strong><small>подтверждений</small></div>
    </div>
    <div className={s.sourceToolbar}>
      <label>Вид расхождения<select value={kind} onChange={(e) => setKind(e.target.value as ContradictionKind | "")}>{kindOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}</select></label>
    </div>
    {data.isLoading ? <LoadingBlock label="Загружаем противоречия"/> : data.isError ? <ErrorState message={data.error.message}/> : <div className={s.qualityList}>
      {data.data?.map((item, index) => <article className={s.qualityCard} key={`${item.src}-${item.dst}-${index}`}>
        <header><span className={s.qualityIconRed}><GitCompareArrows/></span><div><Badge tone={item.rel === "CONTRADICTS" ? "red" : "green"}>{relationLabels[item.rel]}</Badge><h3>{item.kind ?? "без классификации"}</h3><p>Расхождение между источниками</p></div><Badge tone="amber">{item.src.slice(0, 4)}… ↔ {item.dst.slice(0, 4)}…</Badge></header>
        <footer><p><TriangleAlert/>{item.rel === "CONTRADICTS" ? "Требует эксперта" : "Поддержано несколькими источниками"}</p><button>Открыть карточки A/B <ArrowRight/></button></footer>
      </article>)}
      {data.data?.length === 0 && <p className={s.emptyState}>Противоречий выбранного вида нет.</p>}
    </div>}
  </div>;
}