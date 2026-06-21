export interface LeafRoute {
  name: "series-leaf";
  resultId: string;
  query: TrendQuery;
}

export interface TrendRoute {
  name: "trend";
  fingerprint: string;
  query: TrendQuery;
}

export interface ResultRoute {
  name: "result";
  resultId: string;
}

export interface ResultListQuery {
  runID: string;
  batchID: string;
  runReason: string;
  earliestTimestamp: string;
  latestTimestamp: string;
}

export interface ResultListRoute {
  name: "results-list";
  query: ResultListQuery;
}

export interface RunRoute {
  name: "run";
  runId: string;
}

export interface BatchRoute {
  name: "batch";
  batchId: string;
}

export interface NotFoundRoute {
  name: "not-found";
}

export interface HomeRoute {
  name: "home";
}

export interface AccountRoute {
  name: "account";
}

export type CIReportBaseline = "" | "fork_point" | "parent" | "latest_default";

export interface CIReportQuery {
  repository: string;
  commit: string;
  runIDs: string;
  baselineRunIDs: string;
  baseline: CIReportBaseline;
  threshold: string;
  thresholdZ: string;
}

export interface CIReportRoute {
  name: "ci-report";
  query: CIReportQuery;
}

export type BrowseWindow = "all" | "30d" | "3mo" | "1y";

export interface BrowseQuery {
  q: string;
  hardware: string;
  repository: string;
  window: BrowseWindow;
}

export interface BrowseRoute {
  name: "browse";
  query: BrowseQuery;
}

export type Route =
  | HomeRoute
  | AccountRoute
  | BrowseRoute
  | LeafRoute
  | TrendRoute
  | RunRoute
  | BatchRoute
  | ResultListRoute
  | ResultRoute
  | CompareRoute
  | CIReportRoute
  | NotFoundRoute;

export type TrendAxis = "commit" | "time";
export type TrendSigma = 1 | 2 | 3 | 5;

export interface TrendQuery {
  axis: TrendAxis;
  range: BrowseWindow;
  sigma: TrendSigma;
}

export const DEFAULT_TREND_QUERY: TrendQuery = { axis: "commit", range: "3mo", sigma: 2 };

const TREND_AXES: readonly TrendAxis[] = ["commit", "time"];
const TREND_SIGMAS: readonly TrendSigma[] = [1, 2, 3, 5];

/** parseTrendQuery is total: absent params and unknown values fall back to the
 * spec defaults (commit-order axis, 3mo range, 2 sigma band). The range presets
 * reuse BrowseWindow — one rolling-window vocabulary across browse and trend. */
export function parseTrendQuery(search: string): TrendQuery {
  const params = new URLSearchParams(search);
  const axis = params.get("axis");
  const range = params.get("range");
  const sigma = Number(params.get("sigma"));
  return {
    axis: TREND_AXES.includes(axis as TrendAxis) ? (axis as TrendAxis) : "commit",
    range: BROWSE_WINDOWS.includes(range as BrowseWindow) ? (range as BrowseWindow) : "3mo",
    sigma: TREND_SIGMAS.includes(sigma as TrendSigma) ? (sigma as TrendSigma) : 2,
  };
}

/** formatTrendQuery renders the canonical search string, omitting defaults so a
 * pristine trend URL stays bare and shared links carry only changed controls. */
export function formatTrendQuery(query: TrendQuery): string {
  const params = new URLSearchParams();
  if (query.axis !== "commit") params.set("axis", query.axis);
  if (query.range !== "3mo") params.set("range", query.range);
  if (query.sigma !== 2) params.set("sigma", String(query.sigma));
  const s = params.toString();
  return s === "" ? "" : `?${s}`;
}

export interface CompareQuery {
  baseline: string;
  contender: string;
  threshold: number | null;
  thresholdZ: number | null;
}

export interface CompareRoute {
  name: "compare";
  query: CompareQuery;
}

/** parseCompareQuery is total: missing ids become "" (the page renders a
 * pick-two explainer, not an error) and thresholds become null, meaning "use
 * the server defaults" (5% / 5 sigma). Only finite positive numbers survive,
 * so junk never reaches the API. */
export function parseCompareQuery(search: string): CompareQuery {
  const params = new URLSearchParams(search);
  return {
    baseline: params.get("baseline") ?? "",
    contender: params.get("contender") ?? "",
    threshold: positiveOrNull(params.get("threshold")),
    thresholdZ: positiveOrNull(params.get("threshold_z")),
  };
}

const CI_BASELINES: readonly CIReportBaseline[] = ["fork_point", "parent", "latest_default"];

export function parseCIReportQuery(search: string): CIReportQuery {
  const params = new URLSearchParams(search);
  const baseline = params.get("baseline") ?? "";
  return {
    repository: params.get("repository") ?? "",
    commit: params.get("commit_sha") ?? params.get("commit") ?? "",
    runIDs: params.get("run_ids") ?? "",
    baselineRunIDs: params.get("baseline_run_ids") ?? "",
    baseline: CI_BASELINES.includes(baseline as CIReportBaseline) ? (baseline as CIReportBaseline) : "",
    threshold: params.get("threshold") ?? "",
    thresholdZ: params.get("threshold_z") ?? "",
  };
}

function positiveOrNull(raw: string | null): number | null {
  if (raw === null) {
    return null;
  }
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : null;
}

/** formatCompareQuery renders the canonical search string, omitting empty ids
 * and null thresholds so default-threshold links stay minimal. */
export function formatCompareQuery(query: CompareQuery): string {
  const params = new URLSearchParams();
  if (query.baseline !== "") params.set("baseline", query.baseline);
  if (query.contender !== "") params.set("contender", query.contender);
  if (query.threshold !== null) params.set("threshold", String(query.threshold));
  if (query.thresholdZ !== null) params.set("threshold_z", String(query.thresholdZ));
  const s = params.toString();
  return s === "" ? "" : `?${s}`;
}

export const DEFAULT_BROWSE_QUERY: BrowseQuery = { q: "", hardware: "", repository: "", window: "all" };
export const DEFAULT_RESULT_LIST_QUERY: ResultListQuery = {
  runID: "",
  batchID: "",
  runReason: "",
  earliestTimestamp: "",
  latestTimestamp: "",
};

const BROWSE_WINDOWS: readonly BrowseWindow[] = ["all", "30d", "3mo", "1y"];

/** parseBrowseQuery is total: absent params and unknown window values fall back
 * to the defaults, so a hand-edited URL can never produce an invalid route. */
export function parseBrowseQuery(search: string): BrowseQuery {
  const params = new URLSearchParams(search);
  const window = params.get("window");
  return {
    q: params.get("q") ?? "",
    hardware: params.get("hardware") ?? "",
    repository: params.get("repository") ?? "",
    window: BROWSE_WINDOWS.includes(window as BrowseWindow) ? (window as BrowseWindow) : "all",
  };
}

/** formatBrowseQuery renders the canonical search string, omitting defaults so
 * the home URL stays bare and shared links carry only the active filters. */
export function formatBrowseQuery(query: BrowseQuery): string {
  const params = new URLSearchParams();
  if (query.q !== "") params.set("q", query.q);
  if (query.hardware !== "") params.set("hardware", query.hardware);
  if (query.repository !== "") params.set("repository", query.repository);
  if (query.window !== "all") params.set("window", query.window);
  const s = params.toString();
  return s === "" ? "" : `?${s}`;
}

export function parseResultListQuery(search: string): ResultListQuery {
  const params = new URLSearchParams(search);
  return {
    runID: params.get("run_id") ?? "",
    batchID: params.get("batch_id") ?? "",
    runReason: params.get("run_reason") ?? "",
    earliestTimestamp: params.get("earliest_timestamp") ?? "",
    latestTimestamp: params.get("latest_timestamp") ?? "",
  };
}

export function formatResultListQuery(query: ResultListQuery): string {
  const params = new URLSearchParams();
  if (query.runID !== "") params.set("run_id", query.runID);
  if (query.batchID !== "") params.set("batch_id", query.batchID);
  if (query.runReason !== "") params.set("run_reason", query.runReason);
  if (query.earliestTimestamp !== "") params.set("earliest_timestamp", query.earliestTimestamp);
  if (query.latestTimestamp !== "") params.set("latest_timestamp", query.latestTimestamp);
  const s = params.toString();
  return s === "" ? "" : `?${s}`;
}

/** NAVIGATE_EVENT notifies the shell that navigate() pushed an SPA history
 * entry; the shell re-resolves the route exactly as it does on popstate. */
export const NAVIGATE_EVENT = "conbench:navigate";

export function navigate(url: string): void {
  history.pushState(null, "", url);
  window.dispatchEvent(new CustomEvent(NAVIGATE_EVENT));
}

/** interceptNavClick reports whether an anchor click should become an in-app
 * navigation: unmodified primary-button clicks only. Middle-click and
 * Cmd/Ctrl/Shift/Alt-click fall through to the browser's native new-tab /
 * new-window semantics. */
export function interceptNavClick(e: MouseEvent): boolean {
  return e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
}

// Result-entry leaf aliases. Their two-segment paths can never collide with the
// single-segment fingerprint trend route ([^/]+ cannot span "by-result/<id>"),
// so the by-result alias is preserved by shape, not by match order.
const LEAF_PATTERNS: RegExp[] = [
  /^\/benchmarks\/history\/([^/]+)\/?$/,
  /^\/series\/by-result\/([^/]+)\/?$/,
];

const TREND_PATTERN = /^\/series\/([^/]+)\/?$/;
const RUN_PATTERN = /^\/runs\/([^/]+)\/?$/;
const BATCH_PATTERN = /^\/batches\/([^/]+)\/?$/;
const RESULT_PATTERN = /^\/results\/([^/]+)\/?$/;
const RESULT_ALIAS_PATTERN = /^\/benchmark-results\/([^/]+)\/?$/;

/** decodePathSegment decodes a captured id, returning null for a malformed
 * percent-encoding so matchRoute stays total (never throws) — callers feed it
 * raw window.location.pathname, which can carry a bad %-sequence. */
function decodePathSegment(raw: string): string | null {
  try {
    return decodeURIComponent(raw);
  } catch {
    return null;
  }
}

export function matchRoute(pathname: string, search = ""): Route {
  if (pathname === "/" || pathname === "") {
    return { name: "home" };
  }
  if (pathname === "/series" || pathname === "/series/") {
    return { name: "browse", query: parseBrowseQuery(search) };
  }
  if (pathname === "/results" || pathname === "/results/") {
    return { name: "results-list", query: parseResultListQuery(search) };
  }
  if (pathname === "/compare" || pathname === "/compare/") {
    return { name: "compare", query: parseCompareQuery(search) };
  }
  if (pathname === "/account" || pathname === "/account/") {
    return { name: "account" };
  }
  if (pathname === "/ci/report" || pathname === "/ci/report/") {
    return { name: "ci-report", query: parseCIReportQuery(search) };
  }
  const run = RUN_PATTERN.exec(pathname);
  if (run) {
    const runId = decodePathSegment(run[1]!);
    return runId === null ? { name: "not-found" } : { name: "run", runId };
  }
  const batch = BATCH_PATTERN.exec(pathname);
  if (batch) {
    const batchId = decodePathSegment(batch[1]!);
    return batchId === null ? { name: "not-found" } : { name: "batch", batchId };
  }
  for (const pattern of LEAF_PATTERNS) {
    const match = pattern.exec(pathname);
    if (match) {
      const resultId = decodePathSegment(match[1]!);
      return resultId === null
        ? { name: "not-found" }
        : { name: "series-leaf", resultId, query: parseTrendQuery(search) };
    }
  }
  const trend = TREND_PATTERN.exec(pathname);
  if (trend) {
    const fingerprint = decodePathSegment(trend[1]!);
    return fingerprint === null
      ? { name: "not-found" }
      : { name: "trend", fingerprint, query: parseTrendQuery(search) };
  }
  const result = RESULT_PATTERN.exec(pathname) ?? RESULT_ALIAS_PATTERN.exec(pathname);
  if (result) {
    const resultId = decodePathSegment(result[1]!);
    return resultId === null ? { name: "not-found" } : { name: "result", resultId };
  }
  return { name: "not-found" };
}
