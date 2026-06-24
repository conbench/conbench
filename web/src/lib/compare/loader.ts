import type { createConbenchClient } from "../api/client";
import type { components } from "../api/schema";
import type { SeriesStatus } from "../browse/transform";
import { loadResult, type ResultViewModel } from "../result/loader";
import type { CompareQuery } from "../router";
import { orderSamplesForChart, toSeriesPoints, type SeriesPoint } from "../series/transform";
import { markedIndices, verdictStatus } from "./transform";

type Client = ReturnType<typeof createConbenchClient>;
type CompareResult = components["schemas"]["CompareResult"];
type LookbackAnalysis = components["schemas"]["LookbackAnalysis"];
type PairwiseAnalysis = components["schemas"]["PairwiseAnalysis"];

/** NotComparableError carries the endpoint's 422 reason (different series,
 * errored result, unit mismatch) so the page can render it inline as product
 * feedback, distinct from a load failure. */
export class NotComparableError extends Error {}

export interface CompareViewModel {
  status: SeriesStatus;
  lookback: LookbackAnalysis;
  pairwise: PairwiseAnalysis;
  unit: string;
  lessIsBetter: boolean;
  baseline: ResultViewModel;
  contender: ResultViewModel;
  points: SeriesPoint[];
  marked: number[];
}

async function fetchVerdicts(client: Client, query: CompareQuery): Promise<CompareResult> {
  const res = await client.GET("/api/compare/benchmark-results", {
    params: {
      query: {
        baseline_result_id: query.baseline,
        contender_result_id: query.contender,
        ...(query.threshold !== null ? { threshold: query.threshold } : {}),
        ...(query.thresholdZ !== null ? { threshold_z: query.thresholdZ } : {}),
      },
    },
  });
  if (res.error || !res.data) {
    if (res.response.status === 422) {
      throw new NotComparableError(res.error?.detail ?? "results are not comparable");
    }
    throw new Error(`failed to compare ${query.baseline} vs ${query.contender}`);
  }
  return res.data;
}

async function fetchPoints(client: Client, resultId: string): Promise<SeriesPoint[]> {
  const res = await client.GET("/api/history/{benchmark_result_id}", {
    params: { path: { benchmark_result_id: resultId } },
  });
  if (res.error || !res.data) {
    throw new Error(`failed to load history for benchmark result ${resultId}`);
  }
  return toSeriesPoints(orderSamplesForChart(res.data.samples ?? []));
}

/** loadCompare resolves the verdicts first — the endpoint's 422 throws
 * NotComparableError before anything else loads — then both sides' identities
 * (via loadResult, the same shaping the result page uses) and the series
 * membership for the mini-trend in parallel. Throws a plain Error for other
 * failures; the page owns presentation. */
export async function loadCompare(client: Client, query: CompareQuery): Promise<CompareViewModel> {
  const verdicts = await fetchVerdicts(client, query);
  const [baseline, contender, points] = await Promise.all([
    loadResult(client, query.baseline),
    loadResult(client, query.contender),
    fetchPoints(client, query.baseline),
  ]);
  return {
    status: verdictStatus(verdicts.analysis.lookback_z_score),
    lookback: verdicts.analysis.lookback_z_score,
    pairwise: verdicts.analysis.pairwise,
    unit: verdicts.unit,
    lessIsBetter: verdicts.less_is_better,
    baseline,
    contender,
    points,
    marked: markedIndices(points, [query.baseline, query.contender]),
  };
}
