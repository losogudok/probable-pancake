import type { Content, TDocumentDefinitions } from "pdfmake/interfaces";
import type { ResearchAnswer } from "../../domain/types";

const slug = (value: string) => value.toLowerCase().replace(/[^a-zа-яё0-9]+/gi, "-").replace(/^-|-$/g, "").slice(0, 54) || "research";
const fileName = (answer: ResearchAnswer, ext: string) => `${new Date().toISOString().slice(0, 10)}-${slug(answer.query)}.${ext}`;
function download(content: BlobPart, type: string, name: string) { const url = URL.createObjectURL(new Blob([content], { type })); const link = document.createElement("a"); link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url); }

export function toMarkdown(answer: ResearchAnswer) {
  const params = answer.numericParameters.map((p) => `- **${p.label}:** ${p.value} ${p.unit}`).join("\n") || "- Не выделены";
  const sources = answer.sources.map((source, index) => `${index + 1}. ${source.title}${source.year ? ` (${source.year})` : ""}. ${source.filename}${source.page ? `, с. ${source.page}` : ""}.`).join("\n");
  return `# Аналитическая записка\n\n## Вопрос\n${answer.query}\n\n## Вывод\n${answer.summary}\n\n## Числовые параметры\n${params}\n\n## Источники\n${sources}\n`;
}
export function downloadMarkdown(answer: ResearchAnswer) { download(toMarkdown(answer), "text/markdown;charset=utf-8", fileName(answer, "md")); }
export function downloadJsonLd(answer: ResearchAnswer) {
  const json = { "@context": { "@vocab": "https://schema.org/", source: { "@id": "citation" } }, "@type": "Report", identifier: answer.id, headline: answer.query, abstract: answer.summary, dateCreated: new Date().toISOString(), hasPart: answer.findings.map((f) => ({ "@type": "Claim", name: f.title, text: f.text, source: f.sourceIds })), citation: answer.sources.map((s) => ({ "@type": "ScholarlyArticle", identifier: s.id, name: s.title, datePublished: s.year, author: s.authors })) };
  download(JSON.stringify(json, null, 2), "application/ld+json;charset=utf-8", fileName(answer, "jsonld"));
}
export async function downloadPdf(answer: ResearchAnswer) {
  const [{ default: pdfMake }, { default: pdfFonts }] = await Promise.all([
    import("pdfmake/build/pdfmake"), import("pdfmake/build/vfs_fonts"),
  ]);
  const fontModule = pdfFonts as unknown as { vfs?: Record<string, string> };
  (pdfMake as unknown as { vfs: Record<string, string> }).vfs = fontModule.vfs ?? (pdfFonts as unknown as Record<string, string>);
  const content: Content[] = [
    { text: "Научный клубок", style: "brand" }, { text: "Аналитическая записка", style: "title" },
    { text: "Вопрос", style: "heading" }, { text: answer.query }, { text: "Главный вывод", style: "heading" }, { text: answer.summary },
    { text: "Числовые параметры", style: "heading" },
    answer.numericParameters.length ? { table: { headerRows: 1, widths: ["*", "auto", "auto"], body: [["Параметр", "Значение", "Единица"], ...answer.numericParameters.map((p) => [p.label, p.value, p.unit])] }, layout: "lightHorizontalLines" } : { text: "Не выделены", italics: true },
    { text: "Источники", style: "heading", pageBreak: "before" },
    { ol: answer.sources.map((s) => `${s.title}${s.year ? ` (${s.year})` : ""}. ${s.filename}${s.page ? `, с. ${s.page}` : ""}.\n«${s.quote}»`) },
  ];
  const definition: TDocumentDefinitions = { pageSize: "A4", pageMargins: [48, 48, 48, 56], defaultStyle: { font: "Roboto", fontSize: 10, lineHeight: 1.35 }, styles: { brand: { color: "#1d4ed8", bold: true, fontSize: 11 }, title: { fontSize: 22, bold: true, margin: [0, 8, 0, 18] }, heading: { fontSize: 14, bold: true, margin: [0, 16, 0, 7] } }, footer: (page, pages) => ({ text: `${page} / ${pages}`, alignment: "center", color: "#64748b", fontSize: 8 }), content };
  pdfMake.createPdf(definition).download(fileName(answer, "pdf"));
}
