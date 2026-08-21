import { describe, expect, it } from "vitest";

import type { SeriesPoint } from "../series/transform";
import { defaultPair, toCommitChoices } from "./benchmark-picker";

function point(over: Partial<SeriesPoint>): SeriesPoint {
  return {
    resultId: "r",
    commitHash: "abcdef1234567890",
    commitMessage: "msg",
    commitTimestampMs: Date.parse("2024-01-01T00:00:00Z"),
    resultTimestampMs: Date.parse("2024-01-01T00:00:00Z"),
    chartMs: Date.parse("2024-01-01T00:00:00Z"),
    measurements: [],
    svs: 1,
    unit: "s",
    runTags: {},
    info: {},
    changeAnnotations: {},
    stats: {
      z: null,
      rollingMean: null,
      rollingStddev: null,
      isOutlier: false,
      isStep: false,
      beginsChange: false,
      segmentId: null,
    },
    ...over,
  };
}

describe("toCommitChoices", () => {
  it("orders newest first and formats commit, date, and svs", () => {
    const points = [
      point({ resultId: "old", commitHash: "1111111aaaa", svs: 1, chartMs: Date.parse("2024-01-01T00:00:00Z"), commitTimestampMs: Date.parse("2024-01-01T00:00:00Z") }),
      point({ resultId: "new", commitHash: "2222222bbbb", svs: 1.45, chartMs: Date.parse("2024-01-06T00:00:00Z"), commitTimestampMs: Date.parse("2024-01-06T00:00:00Z") }),
    ];
    const choices = toCommitChoices(points, "s", "en-US");
    expect(choices.map((c) => c.resultId)).toEqual(["new", "old"]);
    expect(choices[0]!.shortCommit).toBe("2222222");
    expect(choices[0]!.svsText).toBe("1.45 s");
    expect(choices[0]!.dateText).toContain("2024");
  });

  it("renders placeholders for missing commit hash and timestamp", () => {
    const choices = toCommitChoices([point({ commitHash: "", commitTimestampMs: null })], null);
    expect(choices[0]!.shortCommit).toBe("—");
    expect(choices[0]!.dateText).toBe("—");
    expect(choices[0]!.svsText).toBe("1");
  });
});

describe("defaultPair", () => {
  it("pairs the latest commit as contender against the previous as baseline", () => {
    const choices = toCommitChoices(
      [
        point({ resultId: "old", commitHash: "c1", chartMs: Date.parse("2024-01-01T00:00:00Z") }),
        point({ resultId: "mid", commitHash: "c2", chartMs: Date.parse("2024-01-03T00:00:00Z") }),
        point({ resultId: "new", commitHash: "c3", chartMs: Date.parse("2024-01-06T00:00:00Z") }),
      ],
      "s",
    );
    expect(defaultPair(choices)).toEqual({ contenderId: "new", baselineId: "mid" });
  });

  it("skips reruns on the latest commit to compare two distinct commits", () => {
    const choices = toCommitChoices(
      [
        point({ resultId: "prev", commitHash: "c1", chartMs: Date.parse("2024-01-01T00:00:00Z") }),
        point({ resultId: "rerun", commitHash: "c2", chartMs: Date.parse("2024-01-06T00:00:00Z") }),
        point({ resultId: "latest", commitHash: "c2", chartMs: Date.parse("2024-01-07T00:00:00Z") }),
      ],
      "s",
    );
    expect(defaultPair(choices)).toEqual({ contenderId: "latest", baselineId: "prev" });
  });

  it("returns null when no distinct earlier commit exists", () => {
    const sameCommit = toCommitChoices(
      [
        point({ resultId: "a", commitHash: "c1", chartMs: Date.parse("2024-01-06T00:00:00Z") }),
        point({ resultId: "b", commitHash: "c1", chartMs: Date.parse("2024-01-07T00:00:00Z") }),
      ],
      "s",
    );
    expect(defaultPair(sameCommit)).toBeNull();
    expect(defaultPair(toCommitChoices([point({})], "s"))).toBeNull();
    expect(defaultPair([])).toBeNull();
  });
});
