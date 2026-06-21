import { test, expect } from "@playwright/test";
import { resolveResultTarget } from "./targets";

const baseURL = process.env.CONBENCH_E2E_BASE_URL ?? "http://localhost:8099";

interface SeriesIdentity {
  series: { name: string; less_is_better: boolean | null }[] | null;
}

test("trend deep link renders overlays and controls and opens a result", async ({
  page,
  request,
}) => {
  const target = await resolveResultTarget(request, baseURL);

  // Resolve the seeded series' fingerprint from the result's history payload.
  const api = await request.get(`${baseURL}/api/history/${target.resultId}`);
  expect(api.status()).toBe(200);
  const fp = ((await api.json()) as { history_fingerprint: string }).history_fingerprint;
  const seriesAPI = await request.get(`${baseURL}/api/series?fingerprint=${fp}&page_size=1`);
  expect(seriesAPI.status()).toBe(200);
  const series = ((await seriesAPI.json()) as SeriesIdentity).series?.[0];
  expect(series, "series identity must be available").toBeDefined();

  await page.goto(`${baseURL}/series/${fp}?range=all`);
  await expect(page.locator(".chart-wrap canvas")).toBeVisible();
  // Identity header from /api/series?fingerprint=, including orientation.
  await expect(page.getByRole("heading", { name: series!.name })).toBeVisible();
  if (series!.less_is_better !== null) {
    await expect(page.getByText(series!.less_is_better ? /lower is better/ : /higher is better/)).toBeVisible();
  }

  const canvas = page.locator(".chart-wrap canvas");
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + box!.width * 0.15, box!.y + box!.height * 0.45);
  const tip = page.locator(".tip");
  await expect(tip).toBeVisible();
  const hoverPoint = page.locator(".hover-point");
  await expect(hoverPoint).toBeVisible();
  const leftPoint = await hoverPoint.boundingBox();
  expect(leftPoint).not.toBeNull();
  const leftText = await tip.innerText();
  await page.mouse.move(box!.x + box!.width * 0.85, box!.y + box!.height * 0.45);
  await expect.poll(async () => await tip.innerText()).not.toBe(leftText);
  // Require the marker to still exist and to have actually moved: a vanished
  // marker (null box) must not be read as "moved away from the original x".
  await expect
    .poll(async () => {
      const moved = await hoverPoint.boundingBox();
      return moved !== null && moved.x !== leftPoint!.x;
    })
    .toBe(true);

  // Controls re-render the chart and write the URL.
  await page.getByLabel(/band/i).selectOption("5");
  await expect(page).toHaveURL(/sigma=5/);
  await expect(page.locator(".chart-wrap canvas")).toBeVisible();
  await page.getByLabel(/x-axis/i).selectOption("time");
  await expect(page).toHaveURL(/axis=time/);
  await expect(page.locator(".chart-wrap canvas")).toBeVisible();

  // A commit link in the table opens the light result detail.
  await page.locator("table.detail tbody tr a").first().click();
  await expect(page).toHaveURL(/\/results\//);
  await expect(page.getByRole("heading", { name: series!.name })).toBeVisible();
  await expect(page.getByRole("link", { name: /view trend/i })).toBeVisible();

  // Deep-link reload survives (SPA fallback) with controls intact.
  await page.goto(`${baseURL}/series/${fp}?range=all&axis=time&sigma=3`);
  await expect(page.locator(".chart-wrap canvas")).toBeVisible();
  await expect(page.getByLabel(/band/i)).toHaveValue("3");
});
