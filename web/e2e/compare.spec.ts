import { test, expect } from "@playwright/test";

const baseURL = process.env.CONBENCH_E2E_BASE_URL ?? "http://localhost:8099";

test("browse to trend to compare happy path", async ({ page }) => {
  await page.goto(`${baseURL}/series`);
  await page.locator("table.browse-table tbody tr a").first().click();
  await expect(page).toHaveURL(/\/series\//);
  // 2024-dated seed: widen the empty default 3mo window first.
  await page.getByRole("button", { name: /show all/i }).click();
  await expect(page.locator(".chart-wrap canvas")).toBeVisible();

  // Pick baseline and contender from the table (row click selects; the strip
  // offers the pick actions).
  const rows = page.locator("table.detail tbody tr");
  await rows.first().click();
  await page.getByRole("button", { name: "set baseline" }).click();
  await rows.last().click();
  await page.getByRole("button", { name: "set contender" }).click();
  await page.getByRole("region", { name: /trend context/i }).getByRole("link", { name: "Compare" }).click();

  await expect(page).toHaveURL(/\/compare\?baseline=.+&contender=/);
  await expect(page.locator(".badge")).toBeVisible();
  await expect(page.getByText("lookback z")).toBeVisible();
  await expect(page.getByText("pairwise")).toBeVisible();
  await expect(page.locator("table.sides")).toBeVisible();
  await expect(page.locator(".chart-wrap canvas")).toBeVisible();

  // Threshold adjustment is URL-borne; the verdicts recompute server-side.
  const zInput = page.getByLabel(/threshold σ/);
  await zInput.fill("3");
  await zInput.blur();
  await expect(page).toHaveURL(/threshold_z=3/);
  await expect(page.locator(".badge")).toBeVisible();

  // Deep-link reload survives (SPA fallback).
  await page.reload();
  await expect(page.locator(".badge")).toBeVisible();
  await expect(page.locator("table.sides")).toBeVisible();
});
