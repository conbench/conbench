import { test, expect } from "@playwright/test";

const baseURL = process.env.CONBENCH_E2E_BASE_URL ?? "http://localhost:8099";

test("browse lists the seeded series, searches, and opens its trend", async ({ page }) => {
  await page.goto(`${baseURL}/series`);

  // The seeded demo series appears as a row with its identity and a sparkline.
  const row = page.locator("table.browse-table tbody tr", { hasText: "demo-benchmark" });
  await expect(row).toBeVisible();
  await expect(row.locator("svg")).toBeVisible();
  await expect(row.locator(".badge")).toBeVisible();

  // The top-bar search narrows server-side via ?q= and survives reload (URL state).
  await page.getByRole("searchbox", { name: /series search query/i }).fill("demo-benchmark");
  await page.getByRole("searchbox", { name: /series search query/i }).press("Enter");
  await expect(page).toHaveURL(/\?q=demo-benchmark/);
  await expect(page.locator("table.browse-table tbody tr")).toHaveCount(1);
  await page.reload();
  await expect(page.locator("table.browse-table tbody tr")).toHaveCount(1);

  // Row click opens the fingerprint trend via SPA navigation. The seeded data is
  // from 2024, so the default 3mo window is empty — the empty-range state with
  // its "show all" action is the expected first render.
  await page.locator("table.browse-table tbody tr a").first().click();
  await expect(page).toHaveURL(/\/series\//);
  await expect(page.getByText(/no points in the last/i)).toBeVisible();
  await page.getByRole("button", { name: /show all/i }).click();
  await expect(page).toHaveURL(/range=all/);
  await expect(page.locator(".chart-wrap canvas")).toBeVisible();

  // A search with no matches shows the empty state, not an error.
  await page.goto(`${baseURL}/series?q=definitely-not-a-benchmark`);
  await expect(page.getByText(/no series match/i)).toBeVisible();
});
