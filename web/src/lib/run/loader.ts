import type { createConbenchClient } from "../api/client";
import type { components } from "../api/schema";

type Client = ReturnType<typeof createConbenchClient>;
type ResultItem = components["schemas"]["ResultListItem"];

export interface RunResultRow {
  id: string;
  resultHref: string;
  trendHref: string;
  batchHref: string | null;
  timestamp: string;
  batchId: string | null;
  unit: string | null;
  singleValueSummary: number | null;
  singleValueSummaryType: string;
  historyFingerprint: string;
  hasError: boolean;
}

export interface RunPageViewModel {
  runId: string;
  runReason: string | null;
  runTags: Record<string, unknown>;
  loadedResults: number;
  loadedErrors: number;
  loadedSeries: number;
  loadedBatches: number;
  repository: string;
  commitSha: string | null;
  shortCommit: string | null;
  firstLoadedAt: string | null;
  lastLoadedAt: string | null;
  ciReportHref: string | null;
  rows: RunResultRow[];
  nextCursor: string | null;
}

export const RUN_RESULTS_PAGE_SIZE = 100;

function runPageError(res: { error?: { detail?: string } | undefined }): Error {
  return new Error(res.error?.detail ?? "failed to load run results");
}

export async function loadRunPage(
  client: Client,
  runId: string,
  cursor: string | null = null,
): Promise<RunPageViewModel> {
  const res = await client.GET("/api/benchmark-results", {
    params: {
      query: {
        run_id: runId,
        page_size: RUN_RESULTS_PAGE_SIZE,
        ...(cursor !== null && { cursor }),
      },
    },
  });
  if (res.error || !res.data) {
    throw runPageError(res);
  }
  return toRunPage(runId, res.data.results ?? [], res.data.next_page_cursor);
}

function toRunPage(runId: string, results: ResultItem[], nextCursor: string | null): RunPageViewModel {
  const rows = results.map(toRunResultRow);
  const newest = results[0] ?? null;
  const repository = newest?.commit?.repository ?? "";
  const commitSha = newest?.commit?.hash ?? null;
  const timestamps = results.map((row) => row.timestamp).sort();

  return {
    runId,
    runReason: newest?.run_reason ?? null,
    runTags: newest?.run_tags ?? {},
    loadedResults: results.length,
    loadedErrors: results.filter((row) => row.has_error).length,
    loadedSeries: new Set(results.map((row) => row.history_fingerprint)).size,
    loadedBatches: new Set(results.map((row) => row.batch_id).filter(Boolean)).size,
    repository,
    commitSha,
    shortCommit: commitSha === null ? null : commitSha.slice(0, 8),
    firstLoadedAt: timestamps[0] ?? null,
    lastLoadedAt: timestamps[timestamps.length - 1] ?? null,
    ciReportHref: ciReportHref(repository, commitSha, runId),
    rows,
    nextCursor,
  };
}

function toRunResultRow(result: ResultItem): RunResultRow {
  return {
    id: result.id,
    resultHref: `/results/${encodeURIComponent(result.id)}`,
    trendHref: `/series/${encodeURIComponent(result.history_fingerprint)}`,
    batchHref: result.batch_id === null ? null : `/batches/${encodeURIComponent(result.batch_id)}`,
    timestamp: result.timestamp,
    batchId: result.batch_id ?? null,
    unit: result.unit ?? null,
    singleValueSummary: result.single_value_summary ?? null,
    singleValueSummaryType: result.single_value_summary_type,
    historyFingerprint: result.history_fingerprint,
    hasError: result.has_error,
  };
}

function ciReportHref(repository: string, commitSha: string | null, runId: string): string | null {
  if (repository === "" || commitSha === null || commitSha === "") {
    return null;
  }
  const params = new URLSearchParams({
    repository,
    commit_sha: commitSha,
    run_ids: runId,
    baseline: "fork_point",
  });
  return `/ci/report?${params.toString()}`;
}
