import type { createConbenchClient } from "../api/client";
import type { components } from "../api/schema";

type Client = ReturnType<typeof createConbenchClient>;
type RecentRun = components["schemas"]["RecentRunListItem"];

export interface RecentRunViewModel {
  runId: string;
  displayRunId: string;
  runHref: string;
  runReason: string | null;
  batchCount: number;
  latestBatchId: string | null;
  displayLatestBatchId: string | null;
  latestBatchHref: string | null;
  resultCount: number;
  errorCount: number;
  seriesCount: number;
  latestResultId: string;
  latestResultHref: string;
  repository: string;
  repositoryLabel: string;
  commitSha: string | null;
  shortCommit: string | null;
  firstResultAt: string;
  lastResultAt: string;
  ciReportHref: string | null;
}

export interface RecentRunsViewModel {
  runs: RecentRunViewModel[];
}

export const RECENT_RUNS_PAGE_SIZE = 25;

function recentRunsError(res: { error?: { detail?: string } | undefined }): Error {
  return new Error(res.error?.detail ?? "failed to list recent runs");
}

export async function listRecentRuns(client: Client): Promise<RecentRunsViewModel> {
  const res = await client.GET("/api/runs/recent", {
    params: { query: { page_size: RECENT_RUNS_PAGE_SIZE } },
  });
  if (res.error || !res.data) {
    throw recentRunsError(res);
  }
  return { runs: (res.data.runs ?? []).map(toRecentRunViewModel) };
}

function toRecentRunViewModel(run: RecentRun): RecentRunViewModel {
  const commitSha = run.commit_sha ?? null;
  return {
    runId: run.run_id,
    displayRunId: compactIdentifier(run.run_id, 12, 8),
    runHref: `/runs/${encodeURIComponent(run.run_id)}`,
    runReason: run.run_reason ?? null,
    batchCount: run.batch_count,
    latestBatchId: run.latest_batch_id ?? null,
    displayLatestBatchId: run.latest_batch_id === null
      ? null
      : compactIdentifier(run.latest_batch_id, 12, 6),
    latestBatchHref: run.latest_batch_id === null ? null : `/batches/${encodeURIComponent(run.latest_batch_id)}`,
    resultCount: run.result_count,
    errorCount: run.error_count,
    seriesCount: run.series_count,
    latestResultId: run.latest_result_id,
    latestResultHref: `/results/${encodeURIComponent(run.latest_result_id)}`,
    repository: run.repository,
    repositoryLabel: formatRepositoryLabel(run.repository),
    commitSha,
    shortCommit: commitSha === null ? null : commitSha.slice(0, 8),
    firstResultAt: run.first_result_at,
    lastResultAt: run.last_result_at,
    ciReportHref: ciReportHref(run.repository, commitSha, run.run_id),
  };
}

function compactIdentifier(value: string, head: number, tail: number): string {
  if (value.length <= head + tail + 1) {
    return value;
  }
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

function formatRepositoryLabel(repository: string): string {
  if (repository === "") {
    return "not set";
  }
  let u: URL;
  try {
    u = new URL(repository);
  } catch {
    return repository;
  }
  const parts = u.pathname.split("/").filter(Boolean);
  if ((u.hostname === "github.com" || u.hostname === "www.github.com") && parts.length >= 2) {
    return `${parts[0]}/${parts[1]}`;
  }
  const path = u.pathname === "/" ? "" : u.pathname.replace(/\/$/, "");
  return `${u.hostname}${path}`;
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
