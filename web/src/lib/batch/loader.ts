import type { createConbenchClient } from "../api/client";
import type { components } from "../api/schema";

type Client = ReturnType<typeof createConbenchClient>;
type ResultItem = components["schemas"]["ResultListItem"];

export interface PrimaryTag {
  key: string;
  value: string;
}

export interface BatchResultRow {
  id: string;
  displayResultId: string;
  resultHref: string;
  trendHref: string;
  runId: string;
  displayRunId: string;
  runHref: string;
  timestamp: string;
  unit: string | null;
  singleValueSummary: number | null;
  singleValueSummaryType: string;
  historyFingerprint: string;
  benchmarkName: string;
  benchmarkTags: Record<string, unknown>;
  primaryTags: PrimaryTag[];
  hasError: boolean;
}

export interface BatchRunGroup {
  runId: string;
  displayRunId: string;
  runHref: string;
  runReason: string | null;
  runTags: Record<string, unknown>;
  resultCount: number;
  errorCount: number;
  seriesCount: number;
  historyFingerprints: string[];
  repository: string;
  commitSha: string | null;
  shortCommit: string | null;
  firstLoadedAt: string;
  lastLoadedAt: string;
  ciReportHref: string | null;
}

export interface BatchPageViewModel {
  batchId: string;
  loadedResults: number;
  loadedRuns: number;
  loadedErrors: number;
  loadedSeries: number;
  repository: string;
  commitSha: string | null;
  shortCommit: string | null;
  firstLoadedAt: string | null;
  lastLoadedAt: string | null;
  runGroups: BatchRunGroup[];
  rows: BatchResultRow[];
  nextCursor: string | null;
}

export const BATCH_RESULTS_PAGE_SIZE = 100;

function batchPageError(res: { error?: { detail?: string } | undefined }): Error {
  return new Error(res.error?.detail ?? "failed to load batch results");
}

export async function loadBatchPage(
  client: Client,
  batchId: string,
  cursor: string | null = null,
): Promise<BatchPageViewModel> {
  const res = await client.GET("/api/benchmark-results", {
    params: {
      query: {
        batch_id: batchId,
        page_size: BATCH_RESULTS_PAGE_SIZE,
        ...(cursor !== null && { cursor }),
      },
    },
  });
  if (res.error || !res.data) {
    throw batchPageError(res);
  }
  return toBatchPage(batchId, res.data.results ?? [], res.data.next_page_cursor);
}

function toBatchPage(batchId: string, results: ResultItem[], nextCursor: string | null): BatchPageViewModel {
  const rows = results.map(toBatchResultRow);
  const newest = results[0] ?? null;
  const repository = newest?.commit?.repository ?? "";
  const commitSha = newest?.commit?.hash ?? null;
  const timestamps = results.map((row) => row.timestamp).sort();
  const runGroups = groupRuns(results);

  return {
    batchId,
    loadedResults: results.length,
    loadedRuns: runGroups.length,
    loadedErrors: results.filter((row) => row.has_error).length,
    loadedSeries: new Set(results.map((row) => row.history_fingerprint)).size,
    repository,
    commitSha,
    shortCommit: commitSha === null ? null : commitSha.slice(0, 8),
    firstLoadedAt: timestamps[0] ?? null,
    lastLoadedAt: timestamps[timestamps.length - 1] ?? null,
    runGroups,
    rows,
    nextCursor,
  };
}

function toBatchResultRow(result: ResultItem): BatchResultRow {
  const benchmarkName = cleanString(result.case_name ?? null) ?? compactIdentifier(result.id, 12, 8);
  const benchmarkTags = result.case_tags ?? {};
  return {
    id: result.id,
    displayResultId: compactIdentifier(result.id, 12, 8),
    resultHref: `/results/${encodeURIComponent(result.id)}`,
    trendHref: `/series/${encodeURIComponent(result.history_fingerprint)}`,
    runId: result.run_id,
    displayRunId: compactIdentifier(result.run_id, 12, 8),
    runHref: `/runs/${encodeURIComponent(result.run_id)}`,
    timestamp: result.timestamp,
    unit: result.unit ?? null,
    singleValueSummary: result.single_value_summary ?? null,
    singleValueSummaryType: result.single_value_summary_type,
    historyFingerprint: result.history_fingerprint,
    benchmarkName,
    benchmarkTags,
    primaryTags: primaryTags(benchmarkTags),
    hasError: result.has_error,
  };
}

function groupRuns(results: ResultItem[]): BatchRunGroup[] {
  const groups = new Map<string, { results: ResultItem[] }>();
  for (const result of results) {
    const group = groups.get(result.run_id);
    if (group === undefined) {
      groups.set(result.run_id, { results: [result] });
    } else {
      group.results.push(result);
    }
  }
  return Array.from(groups.entries()).map(([runId, group]) => toBatchRunGroup(runId, group.results));
}

function toBatchRunGroup(runId: string, results: ResultItem[]): BatchRunGroup {
  const first = results[0]!;
  const timestamps = results.map((row) => row.timestamp).sort();
  const repository = first.commit?.repository ?? "";
  const commitSha = first.commit?.hash ?? null;
  const historyFingerprints = Array.from(new Set(results.map((row) => row.history_fingerprint)));
  return {
    runId,
    displayRunId: compactIdentifier(runId, 12, 8),
    runHref: `/runs/${encodeURIComponent(runId)}`,
    runReason: first.run_reason ?? null,
    runTags: first.run_tags ?? {},
    resultCount: results.length,
    errorCount: results.filter((row) => row.has_error).length,
    seriesCount: historyFingerprints.length,
    historyFingerprints,
    repository,
    commitSha,
    shortCommit: commitSha === null ? null : commitSha.slice(0, 8),
    firstLoadedAt: timestamps[0]!,
    lastLoadedAt: timestamps[timestamps.length - 1]!,
    ciReportHref: ciReportHref(repository, commitSha, runId),
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

function cleanString(value: string | null): string | null {
  const trimmed = value?.trim() ?? "";
  return trimmed === "" ? null : trimmed;
}
