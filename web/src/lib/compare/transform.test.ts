import { describe, expect, it } from "vitest";

import { toSeriesPoints } from "../series/transform";
import { lookbackText, markedIndices, pairwiseText, verdictStatus } from "./transform";

// Engine sign convention (internal/stats/verdict.go): the oriented z_score and
// percent_change are NEGATIVE for regressions and positive for improvements.
// The booleans are authoritative; the client never re-derives them from sign.
const lookback = (over = {}) => ({
  improvement_indicated: false,
  regression_indicated: false,
  z_score: 1.23,
  z_threshold: 5,
  ...over,
});

const pairwise = (over = {}) => ({
  improvement_indicated: false,
  regression_indicated: false,
  percent_change: 1.5,
  percent_threshold: 5,
  ...over,
});

describe("verdictStatus", () => {
  it("maps the lookback verdict onto the series status vocabulary", () => {
    expect(verdictStatus(null)).toBe("insufficient");
    expect(verdictStatus(lookback({ regression_indicated: true, z_score: -6.3 }))).toBe(
      "regressed",
    );
    expect(verdictStatus(lookback({ improvement_indicated: true, z_score: 6.3 }))).toBe(
      "improved",
    );
    expect(verdictStatus(lookback())).toBe("stable");
  });
});

describe("lookbackText", () => {
  it("renders z, threshold, and the indication", () => {
    expect(lookbackText(lookback({ regression_indicated: true, z_score: -6.314 }))).toBe(
      "z -6.31 vs threshold 5 — regression indicated",
    );
    expect(lookbackText(lookback({ improvement_indicated: true, z_score: 6.3 }))).toBe(
      "z 6.30 vs threshold 5 — improvement indicated",
    );
    expect(lookbackText(lookback())).toBe("z 1.23 vs threshold 5 — within threshold");
  });

  it("renders n/a for a null verdict, never a fake zero", () => {
    expect(lookbackText(null)).toBe("n/a");
  });
});

describe("pairwiseText", () => {
  it("renders the signed percent change, threshold, and indication", () => {
    expect(pairwiseText(pairwise({ percent_change: 4.25 }))).toBe(
      "+4.3% vs threshold 5% — within threshold",
    );
    expect(
      pairwiseText(pairwise({ percent_change: 7.1, improvement_indicated: true })),
    ).toBe("+7.1% vs threshold 5% — improvement indicated");
    expect(
      pairwiseText(pairwise({ percent_change: -12.04, regression_indicated: true })),
    ).toBe("-12.0% vs threshold 5% — regression indicated");
  });

  it("never renders a negative zero for a tiny change", () => {
    expect(pairwiseText(pairwise({ percent_change: -0.04 }))).toBe(
      "0.0% vs threshold 5% — within threshold",
    );
    expect(pairwiseText(pairwise({ percent_change: 0.04 }))).toBe(
      "0.0% vs threshold 5% — within threshold",
    );
  });

  it("renders n/a for a null verdict (zero-SVS baseline)", () => {
    expect(pairwiseText(null)).toBe("n/a");
  });
});

describe("markedIndices", () => {
  const points = toSeriesPoints(
    ["r1", "r2", "r3"].map((id, i) => ({
      benchmark_result_id: id,
      commit_hash: `sha-${id}`,
      commit_message: "msg",
      commit_repository: "repo",
      commit_timestamp: `2024-01-0${i + 1}T12:00:00Z`,
      data: null,
      hardware_hash: "hw1",
      mean: 1.1,
      result_timestamp: `2024-01-0${i + 1}T13:00:00Z`,
      single_value_summary: 1.1,
      single_value_summary_type: "min",
      unit: "s",
      run_tags: {},
      info: {},
      change_annotations: {},
      zscorestats: null,
    })),
  );

  it("finds the chart indices of the given result ids in order", () => {
    expect(markedIndices(points, ["r3", "r1"])).toEqual([0, 2]);
  });

  it("skips ids that are not in the membership", () => {
    expect(markedIndices(points, ["r2", "nope"])).toEqual([1]);
  });

  it("marks a point once even when the same id is both baseline and contender", () => {
    expect(markedIndices(points, ["r1", "r1"])).toEqual([0]);
  });

  it("is empty for an empty series", () => {
    expect(markedIndices([], ["r1"])).toEqual([]);
  });
});
