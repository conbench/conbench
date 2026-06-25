import type { createConbenchClient } from "../api/client";
import type { components } from "../api/schema";

type Client = ReturnType<typeof createConbenchClient>;
type ResultItem = components["schemas"]["ResultListItem"] & {
  case_name?: string | null;
  case_tags?: Record<string, unknown> | null;
  commit?: (NonNullable<components["schemas"]["ResultListItem"]["commit"]> & {
    message?: string | null;
    author_name?: string | null;
    author_login?: string | null;
    author_avatar?: string | null;
  }) | null;
};

export interface RunResultRow {
  id: string;
  displayResultId: string;
  resultHref: string;
  trendHref: string;
  batchHref: string | null;
  timestamp: string;
  batchId: string | null;
  displayBatchId: string | null;
  unit: string | null;
  singleValueSummary: number | null;
  singleValueSummaryType: string;
  historyFingerprint: string;
  benchmarkName: string;
  benchmarkTags: Record<string, unknown>;
  hasError: boolean;
}

export interface RunPageViewModel {
  runId: string;
  displayRunId: string;
  primaryLabel: string;
  secondaryLabel: string;
  runReason: string | null;
  runTags: Record<string, unknown>;
  loadedResults: number;
  loadedErrors: number;
  loadedSeries: number;
  loadedBatches: number;
  repository: string;
  repositoryLabel: string;
  commitSha: string | null;
  shortCommit: string | null;
  commitMessage: string | null;
  commitHref: string | null;
  authorLabel: string;
  authorLogin: string | null;
  authorAvatar: string | null;
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
  const shortCommit = commitSha === null ? null : commitSha.slice(0, 8);
  const commitMessage = cleanString(newest?.commit?.message ?? null);
  const authorLogin = cleanString(newest?.commit?.author_login ?? null);
  const authorName = cleanString(newest?.commit?.author_name ?? null);
  const displayRunId = compactIdentifier(runId, 12, 8);
  const timestamps = results.map((row) => row.timestamp).sort();

  return {
    runId,
    displayRunId,
    primaryLabel: commitMessage ?? shortCommit ?? displayRunId,
    secondaryLabel: `run ${displayRunId}`,
    runReason: newest?.run_reason ?? null,
    runTags: newest?.run_tags ?? {},
    loadedResults: results.length,
    loadedErrors: results.filter((row) => row.has_error).length,
    loadedSeries: new Set(results.map((row) => row.history_fingerprint)).size,
    loadedBatches: new Set(results.map((row) => row.batch_id).filter(Boolean)).size,
    repository,
    repositoryLabel: formatRepositoryLabel(repository),
    commitSha,
    shortCommit,
    commitMessage,
    commitHref: commitHref(repository, commitSha),
    authorLabel: authorName ?? authorLogin ?? "unknown author",
    authorLogin,
    authorAvatar: usableHTTPURL(newest?.commit?.author_avatar ?? null),
    firstLoadedAt: timestamps[0] ?? null,
    lastLoadedAt: timestamps[timestamps.length - 1] ?? null,
    ciReportHref: ciReportHref(repository, commitSha, runId),
    rows,
    nextCursor,
  };
}

function toRunResultRow(result: ResultItem): RunResultRow {
  const batchId = result.batch_id ?? null;
  const benchmarkName = cleanString(result.case_name ?? null) ?? compactIdentifier(result.id, 12, 8);
  return {
    id: result.id,
    displayResultId: compactIdentifier(result.id, 12, 8),
    resultHref: `/results/${encodeURIComponent(result.id)}`,
    trendHref: `/series/${encodeURIComponent(result.history_fingerprint)}`,
    batchHref: batchId === null ? null : `/batches/${encodeURIComponent(batchId)}`,
    timestamp: result.timestamp,
    batchId,
    displayBatchId: batchId === null ? null : compactIdentifier(batchId, 12, 8),
    unit: result.unit ?? null,
    singleValueSummary: result.single_value_summary ?? null,
    singleValueSummaryType: result.single_value_summary_type,
    historyFingerprint: result.history_fingerprint,
    benchmarkName,
    benchmarkTags: result.case_tags ?? {},
    hasError: result.has_error,
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

function commitHref(repository: string, commitSha: string | null): string | null {
  if (commitSha === null || commitSha === "") {
    return null;
  }
  let u: URL;
  try {
    u = new URL(repository);
  } catch {
    return null;
  }
  if (u.hostname !== "github.com" && u.hostname !== "www.github.com") {
    return null;
  }
  const parts = u.pathname.split("/").filter(Boolean);
  if (parts.length < 2) {
    return null;
  }
  return `https://github.com/${parts[0]}/${parts[1]}/commit/${encodeURIComponent(commitSha)}`;
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

function cleanString(value: string | null): string | null {
  const trimmed = value?.trim() ?? "";
  return trimmed === "" ? null : trimmed;
}

function usableHTTPURL(value: string | null): string | null {
  const cleaned = cleanString(value);
  if (cleaned === null) {
    return null;
  }
  let u: URL;
  try {
    u = new URL(cleaned);
  } catch {
    return null;
  }
  return u.protocol === "https:" || u.protocol === "http:" ? cleaned : null;
}
