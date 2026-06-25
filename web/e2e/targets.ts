import { expect, type APIRequestContext } from "@playwright/test";

interface SeriesListItem {
  latest_result_id: string;
}

interface SeriesPage {
  series: SeriesListItem[] | null;
}

interface RecentRun {
  run_id: string;
  repository: string;
  commit_sha: string | null;
}

interface RecentRunsPage {
  runs: RecentRun[] | null;
}

export interface ResultTarget {
  resultId: string;
  minimumSamples: number;
}

export interface CIReportTarget {
  repository: string;
  commitSHA: string;
  runID: string;
}

export interface CIReportTargets {
  regression: CIReportTarget;
  actionRequired: CIReportTarget;
}

export async function resolveResultTarget(request: APIRequestContext, baseURL: string): Promise<ResultTarget> {
  const submittedResultID = process.env.CONBENCH_E2E_RESULT_ID ?? "";
  if (submittedResultID !== "") {
    return { resultId: submittedResultID, minimumSamples: 6 };
  }

  const response = await request.get(`${baseURL}/api/series?q=demo-benchmark&page_size=1`);
  expect(response.status(), "seeded demo series API must be available").toBe(200);
  const body = (await response.json()) as SeriesPage;
  const latestResultID = body.series?.[0]?.latest_result_id ?? "";
  expect(latestResultID, "seeded demo series must expose a latest result id").not.toBe("");
  return { resultId: latestResultID, minimumSamples: 5 };
}

export async function resolveCIReportTargets(request: APIRequestContext, baseURL: string): Promise<CIReportTargets> {
  const response = await request.get(`${baseURL}/api/runs/recent?page_size=25`);
  expect(response.status(), "seeded recent runs API must be available").toBe(200);
  const body = (await response.json()) as RecentRunsPage;
  return {
    regression: targetFromRun(body.runs, "run-feature-branch-1", "regression CI report"),
    actionRequired: targetFromRun(body.runs, "run-commit-05", "action-required CI report"),
  };
}

function targetFromRun(runs: RecentRun[] | null | undefined, runID: string, description: string): CIReportTarget {
  const run = (runs ?? []).find((candidate) => candidate.run_id === runID);
  expect(run, `seeded ${description} run ${runID} must be available`).toBeDefined();
  expect(run!.repository, `seeded ${description} run must expose repository`).not.toBe("");
  expect(run!.commit_sha, `seeded ${description} run must expose commit sha`).not.toBeNull();
  return { repository: run!.repository, commitSHA: run!.commit_sha!, runID: run!.run_id };
}
