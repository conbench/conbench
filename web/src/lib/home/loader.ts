import type { createConbenchClient } from "../api/client";
import type { components } from "../api/schema";

type Client = ReturnType<typeof createConbenchClient>;
type RecentRun = components["schemas"]["RecentRunListItem"];
type RecentRunCommit = NonNullable<RecentRun["commit"]> & {
  message?: string | null;
  author_name?: string | null;
  author_login?: string | null;
  author_avatar?: string | null;
};

export interface RecentRunViewModel {
  runId: string;
  displayRunId: string;
  primaryLabel: string;
  secondaryLabel: string;
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
  commitMessage: string | null;
  commitHref: string | null;
  authorLabel: string;
  authorLogin: string | null;
  authorAvatar: string | null;
  firstResultAt: string;
  lastResultAt: string;
  ciReportHref: string | null;
  attention: RecentRunAttentionViewModel | null;
}

export interface RecentRunAttentionViewModel {
  status: "failure" | "action_required";
  statusReason: string;
  reportHref: string;
  summaryText: string;
  regressions: number;
  benchmarkErrors: number;
  missingBaseline: number;
  notComparable: number;
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
    params: { query: { page_size: RECENT_RUNS_PAGE_SIZE, include_attention: true } },
  });
  if (res.error || !res.data) {
    throw recentRunsError(res);
  }
  return { runs: (res.data.runs ?? []).map(toRecentRunViewModel) };
}

function toRecentRunViewModel(run: RecentRun): RecentRunViewModel {
  const commitSha = run.commit_sha ?? null;
  const shortCommit = commitSha === null ? null : commitSha.slice(0, 8);
  const displayRunId = compactIdentifier(run.run_id, 12, 8);
  const commit = (run.commit ?? null) as RecentRunCommit | null;
  const commitMessage = cleanString(commit?.message ?? null);
  const authorLogin = cleanString(commit?.author_login ?? null);
  const authorName = cleanString(commit?.author_name ?? null);
  return {
    runId: run.run_id,
    displayRunId,
    primaryLabel: commitMessage ?? shortCommit ?? displayRunId,
    secondaryLabel: `run ${displayRunId}`,
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
    shortCommit,
    commitMessage,
    commitHref: commitHref(run.repository, commitSha),
    authorLabel: authorName ?? authorLogin ?? "unknown author",
    authorLogin,
    authorAvatar: usableHTTPURL(commit?.author_avatar ?? null),
    firstResultAt: run.first_result_at,
    lastResultAt: run.last_result_at,
    ciReportHref: ciReportHref(run.repository, commitSha, run.run_id),
    attention: toRecentRunAttentionViewModel(run.attention ?? null),
  };
}

function toRecentRunAttentionViewModel(
  attention: NonNullable<RecentRun["attention"]> | null,
): RecentRunAttentionViewModel | null {
  if (attention === null || attention.status === "success" || attention.status === "skipped") {
    return null;
  }
  return {
    status: attention.status,
    statusReason: attention.status_reason,
    reportHref: attention.report_url,
    summaryText: attentionSummaryText(attention.summary),
    regressions: attention.summary.regressions,
    benchmarkErrors: attention.summary.benchmark_errors,
    missingBaseline: attention.summary.missing_baseline,
    notComparable: attention.summary.not_comparable,
  };
}

function attentionSummaryText(summary: NonNullable<RecentRun["attention"]>["summary"]): string {
  if (summary.regressions > 0) {
    return plural(summary.regressions, "regression");
  }
  if (summary.benchmark_errors > 0) {
    return plural(summary.benchmark_errors, "benchmark error");
  }
  if (summary.missing_baseline > 0) {
    return plural(summary.missing_baseline, "missing baseline", "missing baselines");
  }
  if (summary.not_comparable > 0) {
    return plural(summary.not_comparable, "not comparable row");
  }
  return "action required";
}

function plural(n: number, word: string, pluralWord = `${word}s`): string {
  return `${n.toLocaleString()} ${n === 1 ? word : pluralWord}`;
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
