import type { createConbenchClient } from "../api/client";
import type { components, operations } from "../api/schema";
import type { CIReportQuery } from "../router";

type Client = ReturnType<typeof createConbenchClient>;
export type CIReport = components["schemas"]["CIReport"];
type Query = NonNullable<operations["get-ci-report"]["parameters"]["query"]>;

function apiQuery(query: CIReportQuery): Query {
  const out: Query = {};
  if (query.repository !== "") out.repository = query.repository;
  if (query.commit !== "") out.commit_sha = query.commit;
  if (query.runIDs !== "") out.run_ids = query.runIDs;
  if (query.baselineRunIDs !== "") out.baseline_run_ids = query.baselineRunIDs;
  if (query.baseline !== "") out.baseline = query.baseline;
  if (query.threshold !== "") out.threshold = Number(query.threshold);
  if (query.thresholdZ !== "") out.threshold_z = Number(query.thresholdZ);
  return out;
}

export function hasCIReportSelector(query: CIReportQuery): boolean {
  return (query.repository !== "" && query.commit !== "") || query.runIDs !== "";
}

export async function loadCIReport(client: Client, query: CIReportQuery): Promise<CIReport> {
  const res = await client.GET("/api/ci/report", { params: { query: apiQuery(query) } });
  if (res.error || !res.data) {
    throw new Error(res.error?.detail ?? "failed to load CI report");
  }
  return res.data;
}
