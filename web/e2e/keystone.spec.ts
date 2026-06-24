import { test, expect } from "@playwright/test";
import { resolveResultTarget } from "./targets";

const baseURL = process.env.CONBENCH_E2E_BASE_URL ?? "http://localhost:8099";

test("result renders the seeded series", async ({ page, request }) => {
  const target = await resolveResultTarget(request, baseURL);

  // API precheck: scripts/e2e.sh submits a fixture that joins the seeded series
  // (>= 6 samples). Direct Playwright runs against a seeded dev server use the
  // latest seeded result (>= 5 samples).
  const api = await request.get(`${baseURL}/api/history/${target.resultId}`);
  expect(api.status()).toBe(200);
  const series = (await api.json()) as { samples: unknown[] };
  expect(series.samples.length).toBeGreaterThanOrEqual(target.minimumSamples);

  // Load the leaf for the selected result. The seed and fixture are dated
  // January 2024; the trend default range is 3mo, so pin ?range=all to render
  // the full seeded series rather than the empty-range state.
  await page.goto(`${baseURL}/benchmarks/history/${target.resultId}?range=all`);
  const canvas = page.locator(".chart-wrap canvas");
  await expect(canvas).toBeVisible();

  // Deterministic mouse move over the chart canvas -> uPlot selects the nearest
  // point and shows the tooltip with a real seeded value.
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  const tip = page.locator(".tip");
  await expect(tip).toBeVisible();
  // Exact component format: `commit · svs unit`, e.g. "commit-03 · 1.1 s".
  await expect(tip).toHaveText(/commit-\d+ · [\d.]+ s/);

  // Data proxy for rendered points: table rows. Keep the assertion tied to the
  // target source so the standalone browser suite and scripts/e2e.sh both prove
  // the expected cardinality.
  expect(await page.locator("table.detail tbody tr").count()).toBeGreaterThanOrEqual(target.minimumSamples);

  // Deep-link reload survives (exercises the server's index.html SPA fallback).
  await page.reload();
  await expect(page.locator(".chart-wrap canvas")).toBeVisible();
  expect(await page.locator("table.detail tbody tr").count()).toBeGreaterThanOrEqual(target.minimumSamples);
});
