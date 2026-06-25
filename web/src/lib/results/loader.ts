import type { createConbenchClient } from "../api/client";
import type { components } from "../api/schema";
import type { ResultListQuery } from "../router";

type Client = ReturnType<typeof createConbenchClient>;
type ResultItem = components["schemas"]["ResultListItem"];

export interface PrimaryTag {
  key: string;
  value: string;
}

export interface ResultsPageOptions {
  query: ResultListQuery;
  cursor: string | null;
}

export interface ResultListRow {
  id: string;
  displayResultId: string;
  resultHref: string;
  runId: string;
  displayRunId: string;
  runHref: string;
  batchId: string | null;
  displayBatchId: string | null;
  batchHref: string | null;
  trendHref: string;
  timestamp: string;
  unit: string | null;
  singleValueSummary: number | null;
  singleValueSummaryType: string;
  historyFingerprint: string;
  benchmarkName: string;
  benchmarkTags: Record<string, unknown>;
  primaryTags: PrimaryTag[];
  runReason: string | null;
  repository: string;
  repositoryLabel: string;
  commitSha: string | null;
  shortCommit: string | null;
  hasError: boolean;
}

export interface ResultsPageViewModel {
  loadedResults: number;
  loadedRuns: number;
  loadedBatches: number;
  loadedErrors: number;
  loadedSeries: number;
  rows: ResultListRow[];
  nextCursor: string | null;
}

export const RESULTS_PAGE_SIZE = 100;

function resultsPageError(res: { error?: { detail?: string } | undefined }): Error {
  return new Error(res.error?.detail ?? "failed to load benchmark results");
}

export async function loadResultsPage(
  client: Client,
  options: ResultsPageOptions,
): Promise<ResultsPageViewModel> {
  const res = await client.GET("/api/benchmark-results", {
    params: {
      query: {
        ...apiFilters(options.query),
        page_size: RESULTS_PAGE_SIZE,
        ...(options.cursor !== null && { cursor: options.cursor }),
      },
    },
  });
  if (res.error || !res.data) {
    throw resultsPageError(res);
  }
  return toResultsPage(res.data.results ?? [], res.data.next_page_cursor);
}

function apiFilters(query: ResultListQuery) {
  return {
    ...(query.runID !== "" && { run_id: query.runID }),
    ...(query.batchID !== "" && { batch_id: query.batchID }),
    ...(query.runReason !== "" && { run_reason: query.runReason }),
    ...(query.earliestTimestamp !== "" && { earliest_timestamp: query.earliestTimestamp }),
    ...(query.latestTimestamp !== "" && { latest_timestamp: query.latestTimestamp }),
  };
}

function toResultsPage(results: ResultItem[], nextCursor: string | null): ResultsPageViewModel {
  const rows = results.map(toResultListRow);
  return {
    loadedResults: rows.length,
    loadedRuns: new Set(rows.map((row) => row.runId)).size,
    loadedBatches: new Set(rows.map((row) => row.batchId).filter(Boolean)).size,
    loadedErrors: rows.filter((row) => row.hasError).length,
    loadedSeries: new Set(rows.map((row) => row.historyFingerprint)).size,
    rows,
    nextCursor,
  };
}

function toResultListRow(result: ResultItem): ResultListRow {
  const commitSha = result.commit?.hash ?? null;
  const batchId = result.batch_id ?? null;
  const benchmarkName = cleanString(result.case_name ?? null) ?? compactIdentifier(result.id, 12, 8);
  const benchmarkTags = result.case_tags ?? {};
  const repository = result.commit?.repository ?? "";
  return {
    id: result.id,
    displayResultId: compactIdentifier(result.id, 12, 8),
    resultHref: `/results/${encodeURIComponent(result.id)}`,
    runId: result.run_id,
    displayRunId: compactIdentifier(result.run_id, 12, 8),
    runHref: `/runs/${encodeURIComponent(result.run_id)}`,
    batchId,
    displayBatchId: batchId === null ? null : compactIdentifier(batchId, 12, 8),
    batchHref: batchId === null ? null : `/batches/${encodeURIComponent(batchId)}`,
    trendHref: `/series/${encodeURIComponent(result.history_fingerprint)}`,
    timestamp: result.timestamp,
    unit: result.unit ?? null,
    singleValueSummary: result.single_value_summary ?? null,
    singleValueSummaryType: result.single_value_summary_type,
    historyFingerprint: result.history_fingerprint,
    benchmarkName,
    benchmarkTags,
    primaryTags: primaryTags(benchmarkTags),
    runReason: result.run_reason ?? null,
    repository,
    repositoryLabel: formatRepositoryLabel(repository),
    commitSha,
    shortCommit: commitSha === null ? null : commitSha.slice(0, 8),
    hasError: result.has_error,
  };
}

const TAG_PRIORITY = ["query_id", "suite", "dataset", "scale_factor", "format", "language", "engine"];

function primaryTags(tags: Record<string, unknown>): PrimaryTag[] {
  return Object.entries(tags)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .sort(([left], [right]) => {
      const leftIndex = TAG_PRIORITY.indexOf(left);
      const rightIndex = TAG_PRIORITY.indexOf(right);
      if (leftIndex >= 0 || rightIndex >= 0) {
        return (leftIndex < 0 ? TAG_PRIORITY.length : leftIndex) - (rightIndex < 0 ? TAG_PRIORITY.length : rightIndex);
      }
      return left.localeCompare(right);
    })
    .slice(0, 4)
    .map(([key, value]) => ({ key, value: String(value) }));
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

function cleanString(value: string | null): string | null {
  const trimmed = value?.trim() ?? "";
  return trimmed === "" ? null : trimmed;
}
