import type { components } from "../api/schema";
import type { SeriesStatus } from "../browse/transform";
import type { SeriesPoint } from "../series/transform";

type LookbackAnalysis = components["schemas"]["LookbackAnalysis"];
type PairwiseAnalysis = components["schemas"]["PairwiseAnalysis"];

/** verdictStatus maps the engine's lookback verdict onto the series status
 * vocabulary the badge renders, mirroring /api/series semantics: the lookback
 * z is the canonical regression call, and a null verdict is "insufficient"
 * (no baseline window), never "stable". The client maps booleans the engine
 * computed; it never derives a verdict. */
export function verdictStatus(lookback: LookbackAnalysis): SeriesStatus {
  if (lookback === null) {
    return "insufficient";
  }
  if (lookback.regression_indicated) {
    return "regressed";
  }
  if (lookback.improvement_indicated) {
    return "improved";
  }
  return "stable";
}

function indication(improvement: boolean, regression: boolean): string {
  if (regression) {
    return "regression indicated";
  }
  if (improvement) {
    return "improvement indicated";
  }
  return "within threshold";
}

/** lookbackText renders the lookback-z verdict line; null renders "n/a"
 * (no baseline commit / empty window), never a fake 0. */
export function lookbackText(lookback: LookbackAnalysis): string {
  if (lookback === null) {
    return "n/a";
  }
  const ind = indication(lookback.improvement_indicated, lookback.regression_indicated);
  return `z ${lookback.z_score.toFixed(2)} vs threshold ${lookback.z_threshold} — ${ind}`;
}

/** pairwiseText renders the pairwise percent verdict line; null renders "n/a"
 * (zero-SVS baseline), never a fake 0. */
export function pairwiseText(pairwise: PairwiseAnalysis): string {
  if (pairwise === null) {
    return "n/a";
  }
  // Round before deriving the sign so a tiny negative change (the engine does
  // not guard -0) renders "0.0%", never "-0.0%".
  const rounded = Number(pairwise.percent_change.toFixed(1));
  const display = Object.is(rounded, -0) ? 0 : rounded;
  const signed = `${display > 0 ? "+" : ""}${display.toFixed(1)}%`;
  const ind = indication(pairwise.improvement_indicated, pairwise.regression_indicated);
  return `${signed} vs threshold ${pairwise.percent_threshold}% — ${ind}`;
}

/** markedIndices finds the chart indices of the given result ids within the
 * series points. Ids outside the default-branch membership are simply not
 * marked — the verdicts and the side table never depend on the chart. */
export function markedIndices(points: SeriesPoint[], resultIds: string[]): number[] {
  const wanted = new Set(resultIds);
  return points.flatMap((p, i) => (wanted.has(p.resultId) ? [i] : []));
}
