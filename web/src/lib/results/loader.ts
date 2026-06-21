import type { createConbenchClient } from "../api/client";
import type { components } from "../api/schema";
import type { ResultListQuery } from "../router";

type Client = ReturnType<typeof createConbenchClient>;
type ResultItem = components["schemas"]["ResultListItem"];

export interface ResultsPageOptions {
  query: ResultListQuery;
  cursor: string | null;
}

export interface ResultListRow {
  id: string;
  resultHref: string;
  runId: string;
  runHref: string;
  batchId: string | null;
  batchHref: string | null;
  trendHref: string;
  timestamp: string;
  unit: string | null;
  singleValueSummary: number | null;
  singleValueSummaryType: string;
  historyFingerprint: string;
  runReason: string | null;
  repository: string;
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
  return {
    id: result.id,
    resultHref: `/results/${encodeURIComponent(result.id)}`,
    runId: result.run_id,
    runHref: `/runs/${encodeURIComponent(result.run_id)}`,
    batchId: result.batch_id ?? null,
    batchHref: result.batch_id === null ? null : `/batches/${encodeURIComponent(result.batch_id)}`,
    trendHref: `/series/${encodeURIComponent(result.history_fingerprint)}`,
    timestamp: result.timestamp,
    unit: result.unit ?? null,
    singleValueSummary: result.single_value_summary ?? null,
    singleValueSummaryType: result.single_value_summary_type,
    historyFingerprint: result.history_fingerprint,
    runReason: result.run_reason ?? null,
    repository: result.commit?.repository ?? "",
    commitSha,
    shortCommit: commitSha === null ? null : commitSha.slice(0, 8),
    hasError: result.has_error,
  };
}
