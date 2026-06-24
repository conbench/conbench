import { Buffer } from "node:buffer";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const baseURL = process.env.CONBENCH_PROD_CLONE_BROWSER_BASE_URL;
if (!baseURL) {
  console.error("CONBENCH_PROD_CLONE_BROWSER_BASE_URL is required");
  process.exit(2);
}
const base = requireLocalBaseURL(baseURL);

const exactQ = process.env.CONBENCH_PROBE_EXACT_Q ?? "BM_ReadBinaryColumn";
const broadQ = process.env.CONBENCH_PROBE_BROAD_Q ?? "tpch";
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(scriptDir, "..", "..");
const outDir = path.join(root, "var", "prod-clone-browser");
const samplesPath = path.join(root, "var", "prod-clone-compat", "samples.json");
const apiTimeoutMs = 30_000;

await mkdir(outDir, { recursive: true });

function requireLocalBaseURL(raw) {
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    console.error("CONBENCH_PROD_CLONE_BROWSER_BASE_URL must be a valid URL");
    process.exit(2);
  }
  if (!["http:", "https:"].includes(parsed.protocol)) {
    console.error("CONBENCH_PROD_CLONE_BROWSER_BASE_URL must use http or https");
    process.exit(2);
  }

  const hostname = parsed.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (!["127.0.0.1", "::1", "localhost"].includes(hostname)) {
    console.error(
      "CONBENCH_PROD_CLONE_BROWSER_BASE_URL must use a local origin: 127.0.0.1, ::1, or localhost",
    );
    process.exit(2);
  }

  return parsed;
}

async function maybeSamples() {
  let text;
  try {
    text = await readFile(samplesPath, "utf8");
  } catch (err) {
    if (err?.code === "ENOENT") {
      return { samples: {}, sampleError: null };
    }
    return { samples: {}, sampleError: `samples.json could not be read: ${err?.code ?? "unknown error"}` };
  }
  try {
    return { samples: JSON.parse(text), sampleError: null };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { samples: {}, sampleError: `samples.json could not be parsed: ${preview(message, 200)}` };
  }
}

function roundDuration(started) {
  return Math.round((performance.now() - started) * 100) / 100;
}

function redactText(text) {
  let redacted = text
    .replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, "<uuid>")
    .replace(/\b[0-9a-f]{12,40}\b/gi, "<hex>")
    .replace(/https?:\/\/[^\s"')]+/gi, "<url>");
  for (const term of [exactQ, broadQ]) {
    if (term !== "") {
      redacted = redacted.split(term).join("<q>");
      redacted = redacted.split(encodeURIComponent(term)).join("<q>");
    }
  }
  return redacted;
}

function preview(text, length) {
  return redactText(text).replace(/\s+/g, " ").trim().slice(0, length);
}

function routeShape(route) {
  const u = new URL(route, "http://probe.local");
  if (u.pathname === "/api/series") {
    return shapeParams(u, "/api/series", new Set(["page_size"]));
  }
  if (u.pathname === "/") {
    return shapeParams(u, "/", new Set(["window"]));
  }
  if (u.pathname === "/api/ci/report") {
    return "/api/ci/report?repository=<redacted>&commit_sha=<redacted>&run_ids=<redacted>";
  }
  if (u.pathname === "/ci/report") {
    return "/ci/report?repository=<redacted>&commit_sha=<redacted>&run_ids=<redacted>";
  }
  if (u.pathname === "/compare") {
    return "/compare?baseline=<redacted>&contender=<redacted>";
  }
  if (u.pathname === "/benchmarks/history/<redacted>") {
    return "/benchmarks/history/<redacted>";
  }
  if (u.pathname.startsWith("/benchmarks/history/")) {
    return "/benchmarks/history/<redacted>";
  }
  if (u.pathname.startsWith("/series/")) {
    return "/series/<redacted>";
  }
  return route;
}

function shapeParams(u, pathname, publicParams) {
  if (u.search === "") {
    return pathname;
  }
  const shaped = new URLSearchParams();
  for (const [key, value] of u.searchParams) {
    if (publicParams.has(key)) {
      shaped.append(key, value);
    } else if (key === "q") {
      shaped.append(key, "<redacted>");
    } else {
      shaped.append(key, "<redacted>");
    }
  }
  const query = shaped.toString().replaceAll("%3Credacted%3E", "<redacted>");
  return query === "" ? pathname : `${pathname}?${query}`;
}

function requestPathFromURL(rawURL) {
  try {
    const u = new URL(rawURL);
    return `${u.pathname}${u.search}`;
  } catch {
    return routeShape(rawURL);
  }
}

async function timedFetch(route) {
  const started = performance.now();
  const target = new URL(route, base);
  const pathOnly = `${target.pathname}${target.search}`;
  if (target.origin !== base.origin) {
    return {
      path: pathOnly,
      summary_path: routeShape(pathOnly),
      status: 0,
      duration_ms: roundDuration(started),
      body_bytes: 0,
      error: "non-local API target blocked",
    };
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), apiTimeoutMs);
  try {
    const res = await fetch(target, { redirect: "manual", signal: controller.signal });
    if (res.status >= 300 && res.status < 400) {
      return {
        path: pathOnly,
        summary_path: routeShape(pathOnly),
        status: res.status,
        duration_ms: roundDuration(started),
        body_bytes: 0,
        error: "redirect blocked",
        body_preview: preview(res.headers.get("location") ?? "", 200),
      };
    }
    const text = await res.text();
    return {
      path: pathOnly,
      summary_path: routeShape(pathOnly),
      status: res.status,
      duration_ms: roundDuration(started),
      body_bytes: Buffer.byteLength(text),
      body_preview: preview(text, 200),
    };
  } catch (err) {
    return {
      path: pathOnly,
      summary_path: routeShape(pathOnly),
      status: 0,
      duration_ms: roundDuration(started),
      body_bytes: 0,
      error: err?.name === "AbortError"
        ? `timeout after ${apiTimeoutMs}ms`
        : err instanceof Error ? err.message : String(err),
    };
  } finally {
    clearTimeout(timeout);
  }
}

function ciReportAPIPath(ci) {
  const q = new URLSearchParams({
    repository: ci.repository,
    commit_sha: ci.commit_sha,
    run_ids: ci.run_ids.join(","),
  });
  return `/api/ci/report?${q}`;
}

function ciReportPagePath(ci) {
  const q = new URLSearchParams({
    repository: ci.repository,
    commit_sha: ci.commit_sha,
    run_ids: ci.run_ids.join(","),
  });
  return `/ci/report?${q}`;
}

function hasCIReportSample(ci) {
  return ci.repository && ci.commit_sha && Array.isArray(ci.run_ids) && ci.run_ids.length > 0;
}

const { samples, sampleError } = await maybeSamples();
const categories = samples.categories ?? {};
const recent = categories.recent_result ?? categories.history_member ?? {};
const ci = samples.ci_report ?? {};
const compare = samples.compare ?? {};

const api = [
  await timedFetch("/api/series?page_size=5"),
  await timedFetch("/api/series?page_size=10"),
  await timedFetch("/api/series?page_size=50"),
  await timedFetch(`/api/series?page_size=10&q=${encodeURIComponent(exactQ)}`),
  await timedFetch(`/api/series?page_size=10&q=${encodeURIComponent(broadQ)}`),
];
if (hasCIReportSample(ci)) {
  api.push(await timedFetch(ciReportAPIPath(ci)));
}

const browserEvents = [];
const pages = [];
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await page.route("**/*", async (route) => {
    const requestURL = new URL(route.request().url());
    if (requestURL.origin !== base.origin) {
      await route.abort();
      return;
    }
    await route.continue();
  });

  page.on("console", (msg) => {
    if (["error", "warning"].includes(msg.type())) {
      browserEvents.push({ type: "console", level: msg.type(), text: preview(msg.text(), 300) });
    }
  });
  page.on("pageerror", (err) => {
    browserEvents.push({ type: "pageerror", text: preview(err.message, 300) });
  });
  page.on("requestfailed", (req) => {
    browserEvents.push({
      type: "requestfailed",
      path: routeShape(requestPathFromURL(req.url())),
      failure: preview(req.failure()?.errorText ?? "", 200),
    });
  });

  pages.push(
    await probePage(page, "mobile-browse", "/"),
    await probePage(page, "mobile-search-exact", `/?q=${encodeURIComponent(exactQ)}`),
    await probePage(page, "mobile-search-broad", `/?q=${encodeURIComponent(broadQ)}`),
  );
  if (recent.result_id) {
    pages.push(await probePage(page, "mobile-trend", `/benchmarks/history/${encodeURIComponent(recent.result_id)}?range=all`));
  } else if (recent.history_fingerprint) {
    pages.push(await probePage(page, "mobile-trend", `/series/${encodeURIComponent(recent.history_fingerprint)}?range=all`));
  }
  if (compare.baseline_result_id && compare.contender_result_id) {
    const q = new URLSearchParams({
      baseline: compare.baseline_result_id,
      contender: compare.contender_result_id,
    });
    pages.push(await probePage(page, "mobile-compare", `/compare?${q}`));
  }
  if (hasCIReportSample(ci)) {
    pages.push(await probePage(page, "mobile-ci-report", ciReportPagePath(ci)));
  }
} finally {
  await browser.close();
}

async function probePage(page, name, route) {
  const started = performance.now();
  const target = new URL(route, base);
  let navigationError = "";
  let status = null;
  try {
    const response = await page.goto(target.toString(), { waitUntil: "domcontentloaded", timeout: 60000 });
    status = response?.status() ?? null;
    const finalURL = new URL(page.url());
    if (finalURL.origin !== base.origin) {
      navigationError = "non-local navigation blocked";
    }
    await page
      .waitForFunction(() => !document.body.innerText.includes("Loading"), undefined, { timeout: 60000 })
      .catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 60000 }).catch(() => {});
  } catch (err) {
    navigationError = err instanceof Error ? err.message : String(err);
  }

  const layout = await page.evaluate(() => ({
    bodyTextPreview: document.body.innerText.slice(0, 500),
    failureText: /Failed to load|Internal Server Error/.test(document.body.innerText),
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    scrollHeight: document.documentElement.scrollHeight,
    links: document.querySelectorAll("a").length,
    tables: document.querySelectorAll("table").length,
  }));

  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true });

  return {
    name,
    route_shape: routeShape(route),
    status,
    duration_ms: roundDuration(started),
    ...layout,
    bodyTextPreview: preview(layout.bodyTextPreview, 500),
    failureText: layout.failureText || navigationError !== "" || (status !== null && status >= 400),
    navigation_error: navigationError === "" ? undefined : preview(navigationError, 300),
  };
}

const report = {
  generated_at: new Date().toISOString(),
  sample_error: sampleError ?? undefined,
  api,
  browserEvents,
  pages,
};
await writeFile(path.join(outDir, "probe-report.json"), `${JSON.stringify(report, null, 2)}\n`);

console.log(
  JSON.stringify(
    {
      api: api.map(({ summary_path, status, duration_ms, body_bytes }) => ({
        path: summary_path,
        status,
        duration_ms,
        body_bytes,
      })),
      pages: pages.map(({ name, route_shape, status, duration_ms, clientWidth, scrollWidth, scrollHeight, links, tables, failureText }) => ({
        name,
        route: route_shape,
        status,
        duration_ms,
        width: clientWidth,
        scrollWidth,
        height: scrollHeight,
        links,
        tables,
        failureText,
      })),
      sampleError,
      browserEvents,
    },
    null,
    2,
  ),
);
