import { expect, test } from "@playwright/test";

test("catholyte search flow returns numeric facts", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Циркуляция католита" }).click();
  await expect(page.getByText("Результат исследования")).toBeVisible();
  await expect(page.getByText(/20–30 л\/ч/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

// Раздел «Граф знаний» (entity-виз) временно заморожен — эндпоинт entity-поиска
// отсутствует в API.md, а /api/graph/subgraph требует doc_ids. См. app/router.tsx.
// test("catholyte research flow opens graph", async ({ page }) => { ... });

// Раздел «Источники/Импорт» временно заморожен — эндпоинт загрузки документов
// отсутствует в API.md. См. app/router.tsx.
// test("sources import opens as an accessible dialog", async ({ page }) => { ... });