import type { createConbenchClient } from "../api/client";
import type { components } from "../api/schema";
import {
  distinctUnits,
  orderSamplesForChart,
  toSeriesPoints,
  type SeriesPoint,
} from "./transform";

type Client = ReturnType<typeof createConbenchClient>;
type ResultDetail = components["schemas"]["ResultDetail"];
type SeriesListItem = components["schemas"]["SeriesListItem"];
type HistorySample = components["schemas"]["HistorySample"];

export interface SeriesIdentity {
  benchmarkName: string;
  caseTags: Record<string, unknown>;
  context: Record<string, unknown>;
  hardwareName: string;
  hardwareHash: string;
  displayHardwareHash: string;
  repository: string;
  repositoryLabel: string;
  unit: string | null;
  lessIsBetter: boolean | null;
  fingerprint: string;
  displayFingerprint: string;
}

/** TrendSource is the page's entry: a result id (walking-skeleton route) or a
 * fingerprint deep link. Both converge on one view-model. */
export type TrendSource =
  | { kind: "result"; resultId: string }
  | { kind: "fingerprint"; fingerprint: string };

export interface TrendViewModel {
  identity: SeriesIdentity;
  points: SeriesPoint[];
  units: string[];
  unitConsistent: boolean;
}

function identityFromDetail(detail: ResultDetail): SeriesIdentity {
  const tags: Record<string, unknown> = { ...detail.tags };
  const rawName = tags["name"];
  const benchmarkName = typeof rawName === "string" ? rawName : "(unnamed)";
  delete tags["name"];
  return {
    benchmarkName,
    caseTags: tags,
    context: detail.context,
    hardwareName: detail.hardware.name,
    hardwareHash: detail.hardware.hash,
    displayHardwareHash: compactIdentifier(detail.hardware.hash, 12, 8),
    repository: detail.commit_repo_url,
    repositoryLabel: formatRepositoryLabel(detail.commit_repo_url),
    unit: detail.unit,
    lessIsBetter: detail.less_is_better,
    fingerprint: detail.history_fingerprint,
    displayFingerprint: compactIdentifier(detail.history_fingerprint, 12, 8),
  };
}

function identityFromSeriesItem(item: SeriesListItem): SeriesIdentity {
  const tags: Record<string, unknown> = { ...item.tags };
  delete tags["name"];
  return {
    benchmarkName: item.name,
    caseTags: tags,
    context: item.context,
    hardwareName: item.hardware.name,
    hardwareHash: item.hardware.hash,
    displayHardwareHash: compactIdentifier(item.hardware.hash, 12, 8),
    repository: item.repository,
    repositoryLabel: formatRepositoryLabel(item.repository),
    unit: item.unit,
    lessIsBetter: item.less_is_better,
    fingerprint: item.history_fingerprint,
    displayFingerprint: compactIdentifier(item.history_fingerprint, 12, 8),
  };
}

function compactIdentifier(value: string, head: number, tail: number): string {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

function formatRepositoryLabel(repository: string): string {
  if (repository === "") return "repository not set";
  let u: URL;
  try {
    u = new URL(repository);
  } catch {
    return repository;
  }
  const path = u.pathname.replace(/^\/+|\/+$/g, "");
  if (u.hostname === "github.com" || u.hostname === "www.github.com") {
    return path || u.hostname;
  }
  return `${u.hostname}${path === "" ? "" : `/${path}`}`;
}

function assemble(identity: SeriesIdentity, rawSamples: HistorySample[] | null): TrendViewModel {
  const samples = orderSamplesForChart(rawSamples ?? []);
  const units = distinctUnits(samples);
  return {
    identity,
    points: toSeriesPoints(samples),
    units,
    unitConsistent: units.length <= 1,
  };
}

async function loadByResult(client: Client, resultId: string): Promise<TrendViewModel> {
  const [detailRes, historyRes] = await Promise.all([
    client.GET("/api/benchmark-results/{id}", { params: { path: { id: resultId } } }),
    client.GET("/api/history/{benchmark_result_id}", {
      params: { path: { benchmark_result_id: resultId } },
    }),
  ]);
  if (detailRes.error || !detailRes.data) {
    throw new Error(`failed to load benchmark result ${resultId}`);
  }
  if (historyRes.error || !historyRes.data) {
    throw new Error(`failed to load history for benchmark result ${resultId}`);
  }
  return assemble(identityFromDetail(detailRes.data), historyRes.data.samples);
}

async function loadByFingerprint(client: Client, fingerprint: string): Promise<TrendViewModel> {
  const [historyRes, seriesRes] = await Promise.all([
    client.GET("/api/history", { params: { query: { fingerprint } } }),
    client.GET("/api/series", { params: { query: { fingerprint, page_size: 1 } } }),
  ]);
  if (historyRes.error || !historyRes.data) {
    throw new Error(`failed to load history for series ${fingerprint}`);
  }
  if (seriesRes.error || !seriesRes.data) {
    throw new Error(`failed to load series ${fingerprint}`);
  }
  const item = seriesRes.data.series?.[0];
  if (item === undefined) {
    throw new Error(`series ${fingerprint} not found`);
  }
  return assemble(identityFromSeriesItem(item), historyRes.data.samples);
}

/** loadTrend resolves either trend entry to one view-model: identity + ordered,
 * transformed points. Throws on any failure so the page error state owns
 * presentation. */
export async function loadTrend(client: Client, source: TrendSource): Promise<TrendViewModel> {
  return source.kind === "result"
    ? loadByResult(client, source.resultId)
    : loadByFingerprint(client, source.fingerprint);
}
