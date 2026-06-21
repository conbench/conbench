import { expect, test } from "@playwright/test";

const baseURL = process.env.CONBENCH_E2E_BASE_URL ?? "http://localhost:8099";

test("home uses the stacked recent-runs layout at narrow desktop widths", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto(`${baseURL}/`);

  const table = page.locator("table.runs-table");
  await expect(table).toBeVisible();
  await expect(table).toHaveCSS("display", "block");
  await expect(table.locator("thead")).toHaveCSS("display", "none");
  await expect(table.locator("tbody tr").first().locator('td[data-label="Results"]')).toHaveCSS(
    "text-align",
    "left",
  );
});
