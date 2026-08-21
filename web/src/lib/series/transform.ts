import type { components } from "../api/schema";
import { formatDate, formatSVS, windowStartIso } from "../browse/transform";
import { formatMeasurement } from "../format";
import type { BrowseWindow, TrendAxis } from "../router";

type HistorySample = components["schemas"]["HistorySample"];
type ZScoreStats = components["schemas"]["ZScoreStats"];

/** PointStats is the per-point display math derived from the engine's
 * zscorestats. The client only divides and scales — segment/step detection and
 * regression verdicts are the frozen server engine's job. */
export interface PointStats {
  z: number | null;
  rollingMean: number | null;
  rollingStddev: number | null;
  isOutlier: boolean;
  isStep: boolean;
  beginsChange: boolean;
  segmentId: number | null;
}

export interface SeriesPoint {
  resultId: string;
  commitHash: string;
  commitMessage: string;
  commitTimestampMs: number | null;
  resultTimestampMs: number;
  /** chartMs is the plotted instant: commit time, else result (run) time. */
  chartMs: number;
  measurements: number[];
  svs: number;
  unit: string | null;
  runTags: Record<string, unknown>;
  info: Record<string, unknown>;
  changeAnnotations: Record<string, unknown>;
  stats: PointStats;
}

function toMs(value: string | null): number | null {
  return value === null ? null : Date.parse(value);
}

function toPointStats(zsRaw: ZScoreStats): PointStats {
  if (zsRaw === null) {
    return {
      z: null,
      rollingMean: null,
      rollingStddev: null,
      isOutlier: false,
      isStep: false,
      beginsChange: false,
      segmentId: null,
    };
  }
  const z =
    zsRaw.residual !== null && zsRaw.rolling_stddev !== null && zsRaw.rolling_stddev !== 0
      ? zsRaw.residual / zsRaw.rolling_stddev
      : null;
  return {
    z,
    rollingMean: zsRaw.rolling_mean,
    rollingStddev: zsRaw.rolling_stddev,
    isOutlier: zsRaw.is_outlier,
    isStep: zsRaw.is_step,
    beginsChange: zsRaw.begins_distribution_change,
    segmentId: zsRaw.segment_id,
  };
}

function sampleMeasurements(sample: HistorySample): number[] {
  const data = (sample as HistorySample & { data?: number[] | null }).data;
  return Array.isArray(data) ? data.filter(Number.isFinite) : [];
}

export function toSeriesPoints(samples: HistorySample[]): SeriesPoint[] {
  return samples.map((s) => ({
    resultId: s.benchmark_result_id,
    commitHash: s.commit_hash,
    commitMessage: s.commit_message,
    commitTimestampMs: toMs(s.commit_timestamp),
    resultTimestampMs: Date.parse(s.result_timestamp),
    chartMs: Date.parse(s.commit_timestamp ?? s.result_timestamp),
    measurements: sampleMeasurements(s),
    svs: s.single_value_summary,
    unit: s.unit,
    runTags: s.run_tags,
    info: s.info,
    changeAnnotations: s.change_annotations,
    stats: toPointStats(s.zscorestats),
  }));
}

export interface TableRow {
  index: number;
  resultId: string;
  commitHash: string;
  commitMessage: string;
  svs: number;
  unit: string | null;
  z: number | null;
  flags: string;
}

/** flagsText renders the engine's point flags for compact display. "step"
 * covers is_step and begins_distribution_change so the table and tooltip
 * flags match the chart's step markers (stepIndices uses the same rule). */
export function flagsText(stats: PointStats): string {
  const flags: string[] = [];
  if (stats.isStep || stats.beginsChange) flags.push("step");
  if (stats.isOutlier) flags.push("outlier");
  return flags.join(" · ");
}

/** toTableRows assigns index positionally within the GIVEN array: the page
 * passes the windowed points, so a row click selects within the same array the
 * chart renders — a full-series index would pick the wrong point after range
 * filtering. */
export function toTableRows(points: SeriesPoint[]): TableRow[] {
  return points.map((p, index) => ({
    index,
    resultId: p.resultId,
    commitHash: p.commitHash,
    commitMessage: p.commitMessage,
    svs: p.svs,
    unit: p.unit,
    z: p.stats.z,
    flags: flagsText(p.stats),
  }));
}

/** windowAnchorDate anchors a trend range at the newest result in that series,
 * falling back to caller-provided now only for empty data. Trend pages are often
 * opened on historical production series; anchoring to wall-clock today makes
 * those pages appear empty even when the series has useful history. */
export function windowAnchorDate(points: SeriesPoint[], now: Date): Date {
  const latest = Math.max(Number.NEGATIVE_INFINITY, ...points.map((p) => p.resultTimestampMs));
  return Number.isFinite(latest) ? new Date(latest) : now;
}

/** windowPoints filters to the rolling benchmark-activity window ending at
 * anchor; "all" keeps everything. The x-axis can use commit order/time, but
 * range membership is about when benchmark results were produced. */
export function windowPoints(points: SeriesPoint[], range: BrowseWindow, anchor: Date): SeriesPoint[] {
  const startIso = windowStartIso(range, anchor);
  if (startIso === null) {
    return points;
  }
  const startMs = Date.parse(startIso);
  return points.filter((p) => p.resultTimestampMs >= startMs);
}

export type TrendChartData = [
  number[],
  (number | null)[],
  (number | null)[],
  (number | null)[],
  (number | null)[],
];

/** trendChartData builds the uPlot-aligned rows [x, svs, mean, hi, lo]: x is the
 * point index in commit mode or unix seconds in time mode; hi/lo are
 * rolling_mean ± sigma · rolling_stddev with null gaps wherever the engine has
 * no stats (series start, outliers, fresh segments) — the band re-centers per
 * segment because the underlying rolling stats do. */
export function trendChartData(
  points: SeriesPoint[],
  axis: TrendAxis,
  sigma: number,
): TrendChartData {
  const xs = points.map((p, i) => (axis === "time" ? p.chartMs / 1000 : i));
  const svs = points.map((p): number | null => p.svs);
  const mean = points.map((p) => p.stats.rollingMean);
  const hi = points.map((p) =>
    p.stats.rollingMean !== null && p.stats.rollingStddev !== null
      ? p.stats.rollingMean + sigma * p.stats.rollingStddev
      : null,
  );
  const lo = points.map((p) =>
    p.stats.rollingMean !== null && p.stats.rollingStddev !== null
      ? p.stats.rollingMean - sigma * p.stats.rollingStddev
      : null,
  );
  return [xs, svs, mean, hi, lo];
}

export function trendYRangeValues(points: SeriesPoint[], sigma: number): number[] {
  return points.flatMap((p) => {
    const values = [p.svs, ...p.measurements];
    if (p.stats.rollingMean !== null) {
      values.push(p.stats.rollingMean);
      if (p.stats.rollingStddev !== null) {
        values.push(p.stats.rollingMean + sigma * p.stats.rollingStddev);
        values.push(p.stats.rollingMean - sigma * p.stats.rollingStddev);
      }
    }
    return values;
  });
}

export function outlierIndices(points: SeriesPoint[]): number[] {
  return points.flatMap((p, i) => (p.stats.isOutlier ? [i] : []));
}

/** stepIndices marks distribution-change boundaries on the chart: points the
 * engine flags is_step or begins_distribution_change (the spec treats both as
 * trend step markers). */
export function stepIndices(points: SeriesPoint[]): number[] {
  return points.flatMap((p, i) => (p.stats.isStep || p.stats.beginsChange ? [i] : []));
}

export interface SegmentSpan {
  startIndex: number;
  endIndex: number;
  segmentId: number;
}

/** segmentSpans groups contiguous runs of the same segment_id for shading;
 * stat-less points (null zscorestats) break a run. */
export function segmentSpans(points: SeriesPoint[]): SegmentSpan[] {
  const spans: SegmentSpan[] = [];
  for (let i = 0; i < points.length; i++) {
    const id = points[i]!.stats.segmentId;
    if (id === null) {
      continue;
    }
    const last = spans[spans.length - 1];
    if (last !== undefined && last.segmentId === id && last.endIndex === i - 1) {
      last.endIndex = i;
    } else {
      spans.push({ startIndex: i, endIndex: i, segmentId: id });
    }
  }
  return spans;
}

export interface TrendTooltip {
  title: string;
  lines: string[];
  metadata: string[];
}

const metadataDisplayLimit = 6;

function metadataValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function boundaryMetadata(p: SeriesPoint): string[] {
  if (!p.stats.beginsChange) return [];
  const entries = [
    ...Object.entries(p.runTags).map(([key, value]) => `run: ${key}=${metadataValue(value)}`),
    ...Object.entries(p.info).map(([key, value]) => `info: ${key}=${metadataValue(value)}`),
  ].sort();
  if (entries.length <= metadataDisplayLimit) return entries;
  return [
    ...entries.slice(0, metadataDisplayLimit),
    `… +${entries.length - metadataDisplayLimit} more`,
  ];
}

/** pointTooltip is the hover view-model. The title keeps the walking-skeleton
 * `sha · value unit` shape (the keystone e2e asserts it); lines add the engine
 * stats, omitting whatever is unavailable rather than printing nulls. */
export function pointTooltip(p: SeriesPoint, locale?: string): TrendTooltip {
  const lines: string[] = [];
  if (p.stats.z !== null) {
    lines.push(`z ${p.stats.z.toFixed(2)}`);
  }
  if (p.stats.rollingMean !== null && p.stats.rollingStddev !== null) {
    lines.push(`mean ${formatSVS(p.stats.rollingMean)} · sd ${formatSVS(p.stats.rollingStddev)}`);
  }
  lines.push(formatDate(new Date(p.chartMs).toISOString(), locale));
  const flags = flagsText(p.stats);
  if (flags !== "") {
    lines.push(flags);
  }
  if (p.commitMessage !== "") {
    lines.push(p.commitMessage.length > 80 ? `${p.commitMessage.slice(0, 79)}…` : p.commitMessage);
  }
  return {
    title: `${p.commitHash} · ${formatMeasurement(p.svs, p.unit)}`,
    lines,
    metadata: boundaryMetadata(p),
  };
}

/** effectiveChartMs is the timestamp a sample is plotted at: commit time when
 * present, else the result (run) time. */
export function effectiveChartMs(sample: HistorySample): number {
  return Date.parse(sample.commit_timestamp ?? sample.result_timestamp);
}

/** orderSamplesForChart sorts samples ascending by effectiveChartMs so the
 * derived chart and table share one monotonic, index-aligned ordering even
 * when some samples lack a commit timestamp. */
export function orderSamplesForChart(samples: HistorySample[]): HistorySample[] {
  return [...samples].sort((a, b) => effectiveChartMs(a) - effectiveChartMs(b));
}

/** distinctUnits returns the sorted set of non-null units across samples. A
 * series with more than one is unit-inconsistent (history_fingerprint excludes
 * unit) and must be surfaced as data-integrity, not a clean SVS line. */
export function distinctUnits(samples: HistorySample[]): string[] {
  const seen = new Set<string>();
  for (const s of samples) {
    if (s.unit !== null) {
      seen.add(s.unit);
    }
  }
  return [...seen].sort();
}
