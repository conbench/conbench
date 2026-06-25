import { expect, test } from "@playwright/test";
import { resolveCIReportTargets } from "./targets";

const baseURL = process.env.CONBENCH_E2E_BASE_URL ?? "http://localhost:8099";

test("ci report renders seeded regression and action-required reports", async ({ page, request }) => {
  const targets = await resolveCIReportTargets(request, baseURL);

  await page.goto(`${baseURL}/ci/report?${reportQuery(targets.regression)}`);
  await expect(page.getByRole("heading", { name: targets.regression.repository })).toBeVisible();
  await expect(page.locator(".report-status.failure")).toHaveText("failure");
  await expect(page.getByText(/lookback regression detected/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: targets.regression.runID })).toBeVisible();
  await expect(page.locator(".row-status.regressed").first()).toHaveText("regressed");
  await expect(page.locator("table.comparisons tbody tr").first()).toContainText("demo-benchmark");

  await page.goto(`${baseURL}/ci/report?${reportQuery(targets.actionRequired)}`);
  await expect(page.getByRole("heading", { name: targets.actionRequired.repository })).toBeVisible();
  await expect(page.locator(".report-status.action_required")).toHaveText("action required");
  await expect(page.getByText(/baseline commit metadata is incomplete/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: targets.actionRequired.runID })).toBeVisible();
  await expect(page.getByText(/contender is already on the default branch/i)).toBeVisible();
});

function reportQuery(target: { repository: string; commitSHA: string; runID: string }): string {
  return new URLSearchParams({
    repository: target.repository,
    commit_sha: target.commitSHA,
    run_ids: target.runID,
    baseline: "fork_point",
  }).toString();
}
