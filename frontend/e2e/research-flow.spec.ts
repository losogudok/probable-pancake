import { expect, test } from "@playwright/test";

test("catholyte research flow remains usable", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Циркуляция католита" }).click();
  await expect(page.getByText("Результат исследования")).toBeVisible();
  await expect(page.getByText(/20–30 л\/ч — документированный/)).toBeVisible();
  await expect(page.getByText(/Скорость циркуляции обычно составляет 20–30 л\/ч/)).toBeVisible();
  await page.getByRole("link", { name: /Открыть граф/ }).click();
  await expect(page.getByRole("heading", { name: "Граф знаний" })).toBeVisible();
  await expect(page.locator(".react-flow__node")).toHaveCount(8);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("sources import opens as an accessible dialog", async ({ page }) => {
  await page.goto("/sources");
  await page.getByRole("button", { name: "Добавить источники" }).click();
  await expect(page.getByRole("dialog", { name: "Добавить источники" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
});
