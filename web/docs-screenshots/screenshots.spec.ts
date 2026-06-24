import { expect, type APIRequestContext, type Locator, type Page, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { readFileSync } from "node:fs";
import path from "node:path";

const outDir = process.env.CONBENCH_DOCS_SCREENSHOT_OUT_DIR ?? path.resolve("../docs/site/assets/screenshots");
const internalOrigin = new URL(process.env.CONBENCH_DOCS_SCREENSHOT_BASE_URL ?? "http://127.0.0.1:18180").origin;
const publicOrigin = new URL(process.env.CONBENCH_DOCS_SCREENSHOT_PUBLIC_BASE_URL ?? internalOrigin).origin;
const screenshotManifest = JSON.parse(
  readFileSync(new URL("./screenshots.json", import.meta.url), "utf-8"),
) as ScreenshotManifest;

interface SeriesListItem {
  history_fingerprint: string;
  latest_result_id: string;
}

interface SeriesPage {
  series: SeriesListItem[] | null;
}

interface HistorySample {
  benchmark_result_id: string;
}

interface HistorySeries {
  samples: HistorySample[] | null;
}

interface RecentRun {
  run_id: string;
  repository: string;
  commit_sha: string | null;
  latest_batch_id: string | null;
}

interface RecentRunsPage {
  runs: RecentRun[] | null;
}

interface DemoTargets {
  fingerprint: string;
  latestResultID: string;
  baselineResultID: string;
  contenderResultID: string;
  runID: string;
  batchID: string;
  repository: string;
  commitSHA: string;
}

interface ScreenshotManifest {
  viewports: Record<string, { width: number; height: number }>;
  screenshots: Array<{
    id: string;
    title: string;
    path: string;
    purpose: string;
  }>;
}

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    const style = document.createElement("style");
    style.textContent = `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        scroll-behavior: auto !important;
      }
    `;
    document.documentElement.appendChild(style);
  });
});

test("capture documentation screenshots from the seeded dashboard", async ({ page, request }, testInfo) => {
  await mkdir(outDir, { recursive: true });
  const targets = await discoverTargets(request);
  const suffix = testInfo.project.name === "mobile" ? "mobile" : "desktop";
  const captured = new Set<string>();

  if (suffix === "desktop") {
    await gotoReady(page, "/", /recent runs/i);
    await expect(page.locator(".runs-table tbody tr").first()).toBeVisible();
    await expectNoDocumentOverflow(page);
    await screenshot(page, "home", suffix, captured);

    await gotoReady(page, "/series?q=demo-benchmark", /benchmark series/i);
    await expect(page.locator("table.browse-table tbody tr").first()).toBeVisible();
    await expectNoDocumentOverflow(page);
    await screenshot(page, "series", suffix, captured);

    await gotoTrend(page, targets.fingerprint);
    await screenshot(page, "trend", suffix, captured);

    await gotoReady(page, `/results/${encodeURIComponent(targets.latestResultID)}`, /demo-benchmark/i);
    await expect(page.getByRole("link", { name: /view trend/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /mark distribution change/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /delete result/i })).toHaveCount(0);
    await expectNoDocumentOverflow(page);
    await screenshot(page, "result", suffix, captured);

    await gotoResults(page, targets.runID);
    await screenshot(page, "results", suffix, captured);

    await gotoRun(page, targets.runID);
    await screenshot(page, "run", suffix, captured);

    await gotoBatch(page, targets.batchID);
    await screenshot(page, "batch", suffix, captured);

    await gotoCompare(page, targets.baselineResultID, targets.contenderResultID);
    await screenshot(page, "compare", suffix, captured);

    await gotoCIReport(page, targets);
    await screenshot(page, "ci-report", suffix, captured);

    await gotoAccount(page);
    await screenshot(page, "account", suffix, captured);
  } else {
    await gotoReady(page, "/", /recent runs/i);
    await expect(page.locator(".runs-table tbody tr").first()).toBeVisible();
    await expectPrimaryNavLinksInViewport(page);
    await expectNoDocumentOverflow(page);
    await expectStackedTableBadgesIntrinsic(page.locator(".runs-table [data-label=\"Errors\"] .status-badge"));
    await screenshot(page, "home", suffix, captured);

    await gotoReady(page, "/series?q=demo-benchmark", /benchmark series/i);
    await expect(page.locator("table.browse-table tbody tr").first()).toBeVisible();
    await expectPrimaryNavLinksInViewport(page);
    await expectNoDocumentOverflow(page);
    await screenshot(page, "series", suffix, captured);

    await gotoTrend(page, targets.fingerprint);
    await expectPrimaryNavLinksInViewport(page);
    await screenshot(page, "trend", suffix, captured);

    await gotoReady(page, `/results/${encodeURIComponent(targets.latestResultID)}`, /demo-benchmark/i);
    await expect(page.getByRole("link", { name: /view trend/i })).toBeVisible();
    await expectPrimaryNavLinksInViewport(page);
    await expectNoDocumentOverflow(page);
    await expectDefinitionListRows(page.locator('[aria-label="Result measurement"] .compact-dl'));
    await screenshot(page, "result", suffix, captured);

    await gotoResults(page, targets.runID);
    await expectPrimaryNavLinksInViewport(page);
    await screenshot(page, "results", suffix, captured);

    await gotoRun(page, targets.runID);
    await expectPrimaryNavLinksInViewport(page);
    await screenshot(page, "run", suffix, captured);

    await gotoBatch(page, targets.batchID);
    await expectPrimaryNavLinksInViewport(page);
    await screenshot(page, "batch", suffix, captured);

    await gotoCompare(page, targets.baselineResultID, targets.contenderResultID);
    await expectPrimaryNavLinksInViewport(page);
    await screenshot(page, "compare", suffix, captured);

    await gotoCIReport(page, targets);
    await expectPrimaryNavLinksInViewport(page);
    await screenshot(page, "ci-report", suffix, captured);

    await gotoAccount(page);
    await expectPrimaryNavLinksInViewport(page);
    await screenshot(page, "account", suffix, captured);
  }

  expect([...captured].sort(), `${suffix} capture must match screenshot manifest`).toEqual(
    expectedFilenamesForViewport(suffix),
  );
});

function expectedFilenamesForViewport(viewport: string): string[] {
  expect(screenshotManifest.viewports[viewport], `screenshot manifest must define viewport ${viewport}`).toBeTruthy();
  return screenshotManifest.screenshots.map((item) => filenameFor(item.id, viewport)).sort();
}

function filenameFor(id: string, viewport: string): string {
  expect(
    screenshotManifest.screenshots.some((item) => item.id === id),
    `unknown screenshot id ${id}`,
  ).toBe(true);
  return `dashboard-${id}-${viewport}.png`;
}

async function discoverTargets(request: APIRequestContext): Promise<DemoTargets> {
  const seriesPage = await getJSON<SeriesPage>(request, "/api/series?q=demo-benchmark&page_size=1");
  const series = seriesPage.series?.[0];
  expect(series, "seeded demo-benchmark series must exist").toBeTruthy();

  const history = await getJSON<HistorySeries>(
    request,
    `/api/history?fingerprint=${encodeURIComponent(series!.history_fingerprint)}`,
  );
  const samples = history.samples ?? [];
  expect(samples.length, "seeded series must have at least two history samples").toBeGreaterThanOrEqual(2);

  const recentRuns = await getJSON<RecentRunsPage>(request, "/api/runs/recent?page_size=25");
  const ciRun = (recentRuns.runs ?? []).find((run) =>
    run.run_id === "run-commit-05" && run.commit_sha !== null && run.latest_batch_id !== null,
  );
  expect(ciRun, "seeded run-commit-05 must be available for CI report screenshots").toBeTruthy();

  return {
    fingerprint: series!.history_fingerprint,
    latestResultID: series!.latest_result_id,
    baselineResultID: samples[0]!.benchmark_result_id,
    contenderResultID: samples[samples.length - 1]!.benchmark_result_id,
    runID: ciRun!.run_id,
    batchID: ciRun!.latest_batch_id!,
    repository: ciRun!.repository,
    commitSHA: ciRun!.commit_sha!,
  };
}

async function getJSON<T>(request: APIRequestContext, url: string): Promise<T> {
  const response = await request.get(url);
  expect(response.ok(), `${url} must return 2xx`).toBe(true);
  return (await response.json()) as T;
}

async function gotoReady(page: Page, url: string, heading: RegExp) {
  await page.goto(url);
  await expect(page.getByRole("heading", { name: heading })).toBeVisible();
}

async function gotoTrend(page: Page, fingerprint: string) {
  await gotoReady(page, `/series/${encodeURIComponent(fingerprint)}?range=all`, /demo-benchmark/i);
  await expectPaintedCanvas(page.locator(".chart-wrap canvas").first());
  await expect(page.locator("table.detail tbody tr").first()).toBeVisible();
  await expectNoDocumentOverflow(page);
}

async function gotoCompare(page: Page, baseline: string, contender: string) {
  const params = new URLSearchParams({ baseline, contender });
  await page.goto(`/compare?${params.toString()}`);
  await expect(page.getByRole("heading", { name: /compare/i })).toBeVisible();
  await expect(page.getByText(/lookback z/i)).toBeVisible();
  await expectPaintedCanvas(page.locator(".chart-wrap canvas").first());
  await expectNoDocumentOverflow(page);
}

async function gotoResults(page: Page, runID: string) {
  const params = new URLSearchParams({ run_id: runID });
  await gotoReady(page, `/results?${params.toString()}`, /benchmark results/i);
  await expect(page.locator(".results-table tbody tr").first()).toBeVisible();
  await expect(page.getByRole("link", { name: runID })).toBeVisible();
  await expectNoDocumentOverflow(page);
}

async function gotoRun(page: Page, runID: string) {
  await gotoReady(page, `/runs/${encodeURIComponent(runID)}`, /run/i);
  await expect(page.locator(".run-results-table tbody tr").first()).toBeVisible();
  await expect(page.getByRole("link", { name: `Open CI report for run ${runID}` })).toBeVisible();
  await expectNoDocumentOverflow(page);
}

async function gotoBatch(page: Page, batchID: string) {
  await gotoReady(page, `/batches/${encodeURIComponent(batchID)}`, /batch/i);
  await expect(page.locator(".batch-runs-table tbody tr").first()).toBeVisible();
  await expect(page.locator(".batch-results-table tbody tr").first()).toBeVisible();
  await expectNoDocumentOverflow(page);
}

async function gotoCIReport(page: Page, targets: DemoTargets) {
  const params = new URLSearchParams({
    repository: targets.repository,
    commit_sha: targets.commitSHA,
    run_ids: targets.runID,
    baseline: "fork_point",
  });
  await page.goto(`/ci/report?${params.toString()}`);
  await expect(page.getByRole("heading", { name: targets.repository })).toBeVisible();
  await expect(page.getByText(targets.runID)).toBeVisible();
  await expectNoDocumentOverflow(page);
}

async function gotoAccount(page: Page) {
  await gotoReady(page, "/account", /account/i);
  await expect(page.getByRole("heading", { name: /signed out/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /sign in/i })).toBeVisible();
  await expectNoDocumentOverflow(page);
}

async function expectPaintedCanvas(canvas: Locator) {
  await expect(canvas).toBeVisible();
  await expect
    .poll(async () =>
      canvas.evaluate((el) => {
        const c = el as HTMLCanvasElement;
        const ctx = c.getContext("2d");
        if (ctx === null || c.width === 0 || c.height === 0) {
          return false;
        }
        const data = ctx.getImageData(0, 0, c.width, c.height).data;
        for (let i = 0; i < data.length; i += 64) {
          if (data[i + 3] !== 0 && (data[i] !== 255 || data[i + 1] !== 255 || data[i + 2] !== 255)) {
            return true;
          }
        }
        return false;
      }),
    )
    .toBe(true);
}

async function expectNoDocumentOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

async function expectPrimaryNavLinksInViewport(page: Page) {
  const offscreen = await page
    .getByRole("navigation", { name: "Primary navigation" })
    .getByRole("link")
    .evaluateAll((links) => {
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      return links
        .map((link) => {
          const rect = link.getBoundingClientRect();
          const label = link.textContent?.trim() ?? "";
          return {
            label,
            left: rect.left,
            right: rect.right,
            top: rect.top,
            bottom: rect.bottom,
            visible:
              rect.width > 0 &&
              rect.height > 0 &&
              rect.left >= -1 &&
              rect.top >= -1 &&
              rect.right <= vw + 1 &&
              rect.bottom <= vh + 1,
          };
        })
        .filter((item) => !item.visible);
    });
  expect(offscreen, "primary nav links must be visible in mobile documentation screenshots").toEqual([]);
}

async function expectDefinitionListRows(list: Locator) {
  const stacked = await list.evaluate((node) => {
    const terms = Array.from(node.querySelectorAll("dt"));
    return terms
      .map((term) => {
        const value = term.nextElementSibling;
        if (value === null || value.tagName.toLowerCase() !== "dd") {
          return null;
        }
        const termRect = term.getBoundingClientRect();
        const valueRect = value.getBoundingClientRect();
        return {
          label: term.textContent?.trim() ?? "",
          termTop: termRect.top,
          valueTop: valueRect.top,
          sameRow: Math.abs(termRect.top - valueRect.top) <= 3,
        };
      })
      .filter((row) => row !== null && !row.sameRow);
  });
  expect(stacked, "definition-list labels and values should remain paired in rows at mobile width").toEqual([]);
}

async function expectStackedTableBadgesIntrinsic(badges: Locator) {
  const stretched = await badges.evaluateAll((nodes) =>
    nodes
      .map((node) => {
        const badge = node as HTMLElement;
        const cell = badge.closest("td");
        if (cell === null) {
          return null;
        }
        const badgeRect = badge.getBoundingClientRect();
        const cellRect = cell.getBoundingClientRect();
        return {
          label: badge.textContent?.trim() ?? "",
          badgeWidth: badgeRect.width,
          cellWidth: cellRect.width,
          stretched: badgeRect.width > Math.min(96, cellRect.width * 0.45),
        };
      })
      .filter((row) => row !== null && row.stretched),
  );
  expect(stretched, "mobile stacked-table badges should keep intrinsic width").toEqual([]);
}

async function screenshot(page: Page, id: string, viewport: string, captured: Set<string>) {
  const filename = filenameFor(id, viewport);
  await normalizeVolatileDemoIdentifiers(page);
  await normalizeInternalOrigin(page);
  await expectNoVolatileDemoIdentifiers(page);
  await expectNoInternalScreenshotOrigin(page);
  await page.screenshot({
    path: path.join(outDir, filename),
    fullPage: false,
    animations: "disabled",
    caret: "hide",
  });
  captured.add(filename);
}

async function normalizeInternalOrigin(page: Page) {
  if (internalOrigin === publicOrigin) {
    return;
  }
  await page.evaluate(
    ({ internal, publicURL }) => {
      const replaceInternal = (value: string) => value.split(internal).join(publicURL);
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          if (node.parentElement?.closest("script, style") !== null) {
            return NodeFilter.FILTER_REJECT;
          }
          return node.nodeValue?.includes(internal) === true
            ? NodeFilter.FILTER_ACCEPT
            : NodeFilter.FILTER_REJECT;
        },
      });
      const textNodes: Text[] = [];
      while (walker.nextNode()) {
        textNodes.push(walker.currentNode as Text);
      }
      for (const node of textNodes) {
        node.nodeValue = replaceInternal(node.nodeValue ?? "");
      }
      for (const input of document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("input, textarea")) {
        if (input.value.includes(internal)) {
          input.value = replaceInternal(input.value);
        }
      }
    },
    { internal: internalOrigin, publicURL: publicOrigin },
  );
}

async function normalizeVolatileDemoIdentifiers(page: Page) {
  await page.evaluate(() => {
    const rawHexID = /\b[0-9a-f]{32}\b/g;
    const hasRawHexID = /\b[0-9a-f]{32}\b/;
    const replacements = new Map<string, string>();
    const replacementFor = (value: string) => {
      const existing = replacements.get(value);
      if (existing !== undefined) {
        return existing;
      }
      const next = `demo-id-${String(replacements.size + 1).padStart(2, "0")}`;
      replacements.set(value, next);
      return next;
    };
    const normalize = (value: string) => value.replace(rawHexID, replacementFor);

    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (node.parentElement?.closest("script, style") !== null) {
          return NodeFilter.FILTER_REJECT;
        }
        return hasRawHexID.test(node.nodeValue ?? "") ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });
    const textNodes: Text[] = [];
    while (walker.nextNode()) {
      textNodes.push(walker.currentNode as Text);
    }
    for (const node of textNodes) {
      node.nodeValue = normalize(node.nodeValue ?? "");
    }
    for (const input of document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("input, textarea")) {
      if (hasRawHexID.test(input.value)) {
        input.value = normalize(input.value);
      }
    }
  });
}

async function expectNoVolatileDemoIdentifiers(page: Page) {
  const rawIDs = await page.evaluate(() => {
    const matches = document.body.innerText.match(/\b[0-9a-f]{32}\b/g) ?? [];
    return [...new Set(matches)].sort();
  });
  expect(rawIDs, "documentation screenshots must not expose run-specific generated hex identifiers").toEqual([]);
}

async function expectNoInternalScreenshotOrigin(page: Page) {
  if (internalOrigin === publicOrigin) {
    return;
  }
  const matches = await page.evaluate((origin) => {
    const leaked: string[] = [];
    if (document.body.innerText.includes(origin)) {
      leaked.push("body text");
    }
    for (const input of document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("input, textarea")) {
      if (input.value.includes(origin)) {
        leaked.push(`${input.tagName.toLowerCase()} value`);
      }
    }
    return leaked;
  }, internalOrigin);
  expect(matches, "documentation screenshots must not expose the internal screenshot server origin").toEqual([]);
}
