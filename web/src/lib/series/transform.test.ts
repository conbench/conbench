import { describe, expect, it } from "vitest";

import type { components } from "../api/schema";
import {
  distinctUnits,
  effectiveChartMs,
  orderSamplesForChart,
  outlierIndices,
  pointTooltip,
  segmentSpans,
  stepIndices,
  toSeriesPoints,
  toTableRows,
  trendChartData,
  trendYRangeValues,
  windowAnchorDate,
  windowPoints,
} from "./transform";

type HistorySample = components["schemas"]["HistorySample"];
type ZScoreStats = components["schemas"]["ZScoreStats"];

function zs(over: Partial<NonNullable<ZScoreStats>> = {}): ZScoreStats {
  return {
    begins_distribution_change: false,
    is_outlier: false,
    is_step: false,
    residual: 0.1,
    rolling_mean: 1.0,
    rolling_mean_excluding_this_commit: 1.0,
    rolling_stddev: 0.05,
    segment_id: 0,
    ...over,
  };
}

function sample(over: Partial<HistorySample> = {}): HistorySample {
  return {
    benchmark_result_id: "r1",
    commit_hash: "abc1234",
    commit_message: "tune the flux capacitor",
    commit_repository: "https://github.com/conbench/demo",
    commit_timestamp: "2024-01-07T12:00:00Z",
    data: null,
    hardware_hash: "hw1",
    mean: 1.1,
    result_timestamp: "2024-01-07T13:00:00Z",
    single_value_summary: 1.1,
    single_value_summary_type: "min",
    unit: "s",
    zscorestats: zs(),
    ...over,
  };
}

describe("toSeriesPoints zscore stats", () => {
  it("derives z from residual over stddev and carries the engine fields", () => {
    const [p] = toSeriesPoints([sample({ zscorestats: zs({ residual: 0.2, rolling_stddev: 0.05 }) })]);
    expect(p!.stats.z).toBeCloseTo(4.0);
    expect(p!.stats.rollingMean).toBe(1.0);
    expect(p!.stats.rollingStddev).toBe(0.05);
    expect(p!.stats.segmentId).toBe(0);
    expect(p!.chartMs).toBe(Date.parse("2024-01-07T12:00:00Z"));
  });

  it("nulls z when the engine gives no stats, a null stddev, or a zero stddev", () => {
    expect(toSeriesPoints([sample({ zscorestats: null })])[0]!.stats.z).toBeNull();
    expect(
      toSeriesPoints([sample({ zscorestats: zs({ rolling_stddev: null }) })])[0]!.stats.z,
    ).toBeNull();
    expect(
      toSeriesPoints([sample({ zscorestats: zs({ rolling_stddev: 0 }) })])[0]!.stats.z,
    ).toBeNull();
    expect(
      toSeriesPoints([sample({ zscorestats: zs({ residual: null }) })])[0]!.stats.z,
    ).toBeNull();
  });

  it("preserves raw measurement repetitions for chart overlays", () => {
    const withMeasurements = {
      ...sample({ single_value_summary: 4.4 }),
      data: [1.1, 4.4, 3.3],
    } as HistorySample & { data: number[] };
    const [p] = toSeriesPoints([withMeasurements]);
    expect((p as { measurements?: number[] }).measurements).toEqual([1.1, 4.4, 3.3]);
  });

  it("falls back to the result timestamp for chartMs when commit time is null", () => {
    const [p] = toSeriesPoints([sample({ commit_timestamp: null })]);
    expect(p!.chartMs).toBe(Date.parse("2024-01-07T13:00:00Z"));
  });
});

describe("windowPoints", () => {
  const points = toSeriesPoints([
    sample({
      benchmark_result_id: "recent-run",
      commit_timestamp: "2022-03-01T00:00:00Z",
      result_timestamp: "2026-06-01T00:00:00Z",
    }),
    sample({
      benchmark_result_id: "older-run",
      commit_timestamp: "2022-02-01T00:00:00Z",
      result_timestamp: "2026-04-15T00:00:00Z",
    }),
    sample({
      benchmark_result_id: "ancient-run",
      commit_timestamp: "2022-01-01T00:00:00Z",
      result_timestamp: "2025-01-07T12:00:00Z",
    }),
  ]);
  const anchor = new Date("2026-06-01T00:00:00Z");

  it("anchors trend windows at the newest result by default", () => {
    expect(windowAnchorDate(points, new Date("2026-06-11T00:00:00Z")).toISOString()).toBe(
      "2026-06-01T00:00:00.000Z",
    );
    expect(windowAnchorDate([], new Date("2026-06-11T00:00:00Z")).toISOString()).toBe(
      "2026-06-11T00:00:00.000Z",
    );
  });

  it("keeps everything for all and filters by benchmark result activity", () => {
    expect(windowPoints(points, "all", anchor)).toHaveLength(3);
    expect(windowPoints(points, "30d", anchor).map((p) => p.resultId)).toEqual(["recent-run"]);
    expect(windowPoints(points, "1y", anchor).map((p) => p.resultId)).toEqual([
      "recent-run",
      "older-run",
    ]);
  });
});

describe("trendChartData", () => {
  const points = toSeriesPoints([
    sample({ commit_timestamp: "2024-01-07T12:00:00Z", single_value_summary: 1.0 }),
    sample({
      commit_timestamp: "2024-01-08T12:00:00Z",
      single_value_summary: 2.0,
      zscorestats: zs({ rolling_mean: 1.5, rolling_stddev: 0.5 }),
    }),
    sample({ commit_timestamp: "2024-01-09T12:00:00Z", single_value_summary: 3.0, zscorestats: null }),
  ]);

  it("uses indices in commit mode and unix seconds in time mode", () => {
    const [xsCommit] = trendChartData(points, "commit", 2);
    expect(xsCommit).toEqual([0, 1, 2]);
    const [xsTime] = trendChartData(points, "time", 2);
    expect(xsTime).toEqual([
      Date.parse("2024-01-07T12:00:00Z") / 1000,
      Date.parse("2024-01-08T12:00:00Z") / 1000,
      Date.parse("2024-01-09T12:00:00Z") / 1000,
    ]);
  });

  it("builds mean and sigma-scaled band rows with null gaps", () => {
    const [, svs, mean, hi, lo] = trendChartData(points, "commit", 2);
    expect(svs).toEqual([1.0, 2.0, 3.0]);
    expect(mean).toEqual([1.0, 1.5, null]);
    expect(hi).toEqual([1.1, 2.5, null]);
    expect(lo).toEqual([0.9, 0.5, null]);
  });

  it("includes rolling means in the y range even when stddev is unavailable", () => {
    const values = trendYRangeValues(
      toSeriesPoints([
        sample({
          single_value_summary: 10.0,
          zscorestats: zs({ rolling_mean: 100.0, rolling_stddev: null }),
        }),
      ]),
      2,
    );
    expect(values).toEqual([10.0, 100.0]);
  });

  it("includes raw repetitions in the y range", () => {
    const values = trendYRangeValues(
      toSeriesPoints([
        {
          ...sample({
            single_value_summary: 10.0,
            zscorestats: zs({ rolling_mean: 11.0, rolling_stddev: 1.0 }),
          }),
          data: [5.0, 10.0, 20.0],
        } as HistorySample & { data: number[] },
      ]),
      2,
    );
    expect(values).toEqual([10.0, 5.0, 10.0, 20.0, 11.0, 13.0, 9.0]);
  });
});

describe("flag and segment geometry", () => {
  const points = toSeriesPoints([
    sample({ zscorestats: zs({ segment_id: 0 }) }),
    sample({ zscorestats: zs({ segment_id: 0, is_outlier: true }) }),
    sample({
      zscorestats: zs({ segment_id: 1, is_step: true, begins_distribution_change: true }),
    }),
    sample({ zscorestats: null }),
    sample({ zscorestats: zs({ segment_id: 1, is_step: true }) }),
  ]);

  it("collects outlier and step-marker indices (is_step or begins_distribution_change)", () => {
    expect(outlierIndices(points)).toEqual([1]);
    expect(stepIndices(points)).toEqual([2, 4]);
  });

  it("builds contiguous segment spans, breaking on stat-less points", () => {
    expect(segmentSpans(points)).toEqual([
      { startIndex: 0, endIndex: 1, segmentId: 0 },
      { startIndex: 2, endIndex: 2, segmentId: 1 },
      { startIndex: 4, endIndex: 4, segmentId: 1 },
    ]);
  });
});

describe("toTableRows", () => {
  it("fills z and flags from the engine stats", () => {
    const points = toSeriesPoints([
      sample({ zscorestats: zs({ residual: 0.25, rolling_stddev: 0.05 }) }),
      sample({ zscorestats: zs({ is_step: true, is_outlier: true }) }),
      sample({ zscorestats: null }),
    ]);
    const rows = toTableRows(points);
    expect(rows[0]).toMatchObject({ commitHash: "abc1234", svs: 1.1, flags: "" });
    expect(rows[0]!.z).toBeCloseTo(5.0);
    expect(rows[1]!.flags).toBe("step · outlier");
    expect(rows[2]!.z).toBeNull();
  });

  it("flags begins-only distribution changes as step, matching the chart markers", () => {
    const points = toSeriesPoints([
      sample({ zscorestats: zs({ begins_distribution_change: true }) }),
    ]);
    expect(toTableRows(points)[0]!.flags).toBe("step");
  });

  it("rebases index positionally for a windowed subset", () => {
    const points = toSeriesPoints([
      sample({ benchmark_result_id: "r1" }),
      sample({ benchmark_result_id: "r2" }),
      sample({ benchmark_result_id: "r3" }),
    ]);
    const rows = toTableRows(points.slice(1));
    expect(rows.map((r) => r.index)).toEqual([0, 1]);
    expect(rows[0]!.resultId).toBe("r2");
  });
});

describe("pointTooltip", () => {
  it("keeps the keystone title format and adds engine lines", () => {
    const [p] = toSeriesPoints([
      sample({ zscorestats: zs({ residual: 0.2, rolling_stddev: 0.05, is_step: true }) }),
    ]);
    const tip = pointTooltip(p!, "en-US");
    expect(tip.title).toBe("abc1234 · 1.1 s");
    expect(tip.lines).toContain("z 4.00");
    expect(tip.lines).toContain("mean 1 · sd 0.05");
    expect(tip.lines).toContain("step");
    expect(tip.lines.some((l) => l.includes("Jan 7, 2024"))).toBe(true);
    expect(tip.lines).toContain("tune the flux capacitor");
  });

  it("omits unavailable lines instead of rendering nulls", () => {
    const [p] = toSeriesPoints([sample({ zscorestats: null, unit: null, commit_message: "" })]);
    const tip = pointTooltip(p!, "en-US");
    expect(tip.title).toBe("abc1234 · 1.1");
    expect(tip.lines.some((l) => l.startsWith("z "))).toBe(false);
    expect(tip.lines.some((l) => l.startsWith("mean "))).toBe(false);
  });
});

describe("effectiveChartMs", () => {
  it("uses commit time when present, else result time", () => {
    expect(effectiveChartMs(sample({ commit_timestamp: "2024-01-01T00:00:00Z" }))).toBe(
      Date.parse("2024-01-01T00:00:00Z"),
    );
    expect(
      effectiveChartMs(sample({ commit_timestamp: null, result_timestamp: "2024-02-02T00:00:00Z" })),
    ).toBe(Date.parse("2024-02-02T00:00:00Z"));
  });
});

describe("orderSamplesForChart", () => {
  it("sorts samples ascending by effective chart time", () => {
    const ordered = orderSamplesForChart([
      sample({ commit_hash: "late", commit_timestamp: "2024-01-03T00:00:00Z" }),
      sample({ commit_hash: "early", commit_timestamp: "2024-01-01T00:00:00Z" }),
    ]);
    expect(ordered.map((s) => s.commit_hash)).toEqual(["early", "late"]);
  });

  it("places a null-commit sample by its result time, keeping chart x monotonic", () => {
    const ordered = orderSamplesForChart([
      sample({ commit_hash: "c2", commit_timestamp: "2024-01-02T00:00:00Z" }),
      sample({ commit_hash: "nullc", commit_timestamp: null, result_timestamp: "2024-01-01T00:00:00Z" }),
      sample({ commit_hash: "c3", commit_timestamp: "2024-01-03T00:00:00Z" }),
    ]);
    expect(ordered.map((s) => s.commit_hash)).toEqual(["nullc", "c2", "c3"]);
    const chartMs = toSeriesPoints(ordered).map((p) => p.chartMs);
    expect(chartMs).toEqual([...chartMs].sort((a, b) => a - b));
  });
});

describe("distinctUnits", () => {
  it("returns the sorted set of non-null units", () => {
    expect(distinctUnits([sample({ unit: "s" }), sample({ unit: "ms" }), sample({ unit: "s" })])).toEqual(["ms", "s"]);
  });

  it("ignores null units", () => {
    expect(distinctUnits([sample({ unit: null }), sample({ unit: "s" })])).toEqual(["s"]);
  });
});
