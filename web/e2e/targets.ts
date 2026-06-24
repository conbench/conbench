import { expect, type APIRequestContext } from "@playwright/test";

interface SeriesListItem {
  latest_result_id: string;
}

interface SeriesPage {
  series: SeriesListItem[] | null;
}

export interface ResultTarget {
  resultId: string;
  minimumSamples: number;
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
