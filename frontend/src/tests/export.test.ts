import { describe, expect, it, vi } from "vitest";
import { catholyteAnswer } from "../mocks/fixtures/scenarios";
import { toMarkdown } from "../features/export/export";

vi.mock("pdfmake/build/pdfmake", () => ({ default: { createPdf: vi.fn(), vfs: {} } }));
vi.mock("pdfmake/build/vfs_fonts", () => ({ default: { vfs: {} } }));

describe("exports", () => {
  it("includes evidence and values in markdown", () => {
    const markdown = toMarkdown({ ...catholyteAnswer, query: "Тестовый запрос" });
    expect(markdown).toContain("20–30");
    expect(markdown).toContain("Обзор технических решений");
  });
});
