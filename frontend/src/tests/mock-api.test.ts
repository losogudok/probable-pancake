import { describe, expect, it } from "vitest";
import { MockKnowledgeApi } from "../api/mock-knowledge-api";

describe("MockKnowledgeApi", () => {
  it("recognizes catholyte query and returns sourced flow range", async () => {
    const api = new MockKnowledgeApi();
    const answer = await api.ask({ query: "Какая скорость циркуляции католита при электроэкстракции никеля?", mode: "auto", filters: {} });
    expect(answer.summary).toContain("20–30 л/ч");
    expect(answer.sources[0].chunkId).toBe("e7fb17923275db5b_0009");
  });

  it("does not invent a deep answer for an unknown query", async () => {
    const api = new MockKnowledgeApi();
    const answer = await api.ask({ query: "Неизвестная новая технология XZ-42", mode: "auto", filters: {} });
    expect(answer.summary).toContain("Недостаточно структурированных данных");
  });

  it("emits all upload stages", async () => {
    const api = new MockKnowledgeApi(); const stages: string[] = [];
    const file = new File(["demo"], "report.pdf", { type: "application/pdf" });
    await api.uploadDocuments({ files: [file], category: "review", language: "ru", geography: "Global", sensitivity: "internal" }, (event) => stages.push(event.stage));
    expect(stages).toEqual(["upload", "recognition", "normalization", "extraction", "indexing", "complete"]);
  });
});
