import { describe, expect, it } from "vitest";

import type { components } from "../api/schema";
import {
  formatDate,
  formatSVS,
  sortRows,
  sparklinePoints,
  tagsText,
  toBrowseRows,
  windowStartIso,
  type BrowseRow,
} from "./transform";

type SeriesListItem = components["schemas"]["SeriesListItem"];

function item(over: Partial<SeriesListItem> = {}): SeriesListItem {
  return {
    history_fingerprint: "fp1",
    name: "tpch-q1",
    tags: { name: "tpch-q1", scale: "sf10" },
    context: { compiler: "gcc-13" },
    hardware: { id: "h1", type: "machine", name: "m5", hash: "hw1" },
    repository: "https://github.com/conbench/demo",
    unit: "s",
    less_is_better: true,
    status: "stable",
    latest_result_id: "r9",
    latest_single_value_summary: 1.23456,
    latest_single_value_summary_type: "min",
    latest_commit_sha: "a1b2c3d4e5f6",
    latest_commit_timestamp: "2024-01-07T12:00:00Z",
    latest_result_timestamp: "2024-01-07T13:00:00Z",
    point_count: 8,
    sparkline: [1.0, 1.1, 1.2],
    ...over,
  };
}

describe("toBrowseRows", () => {
  it("maps identity, formats SVS with unit, shortens the sha", () => {
    const [row] = toBrowseRows([item()], "en-US");
    expect(row).toMatchObject({
      fingerprint: "fp1",
      name: "tpch-q1",
      paramsText: "scale=sf10",
      contextText: "compiler=gcc-13",
      hardwareKey: "hw1",
      hardwareName: "m5",
      svsText: "1.235 s",
      pointCount: 8,
      status: "stable",
      commitSha: "a1b2c3d",
      commitDateText: "Jan 7, 2024",
    });
    expect(row!.commitTimestampMs).toBe(Date.parse("2024-01-07T12:00:00Z"));
  });

  it("renders a null SVS / null unit as a dash and bare number", () => {
    expect(toBrowseRows([item({ latest_single_value_summary: null })])[0]!.svsText).toBe("—");
    expect(toBrowseRows([item({ unit: null })])[0]!.svsText).toBe("1.235");
  });
});

describe("formatting", () => {
  it("formatSVS keeps 4 significant digits without trailing zeros", () => {
    expect(formatSVS(1.23456)).toBe("1.235");
    expect(formatSVS(0.0001234567)).toBe("0.0001235");
    expect(formatSVS(1500)).toBe("1500");
  });
  it("formatDate renders a local short date", () => {
    expect(formatDate("2024-01-07T12:00:00Z", "en-US")).toMatch(/Jan 7, 2024|Jan 8, 2024/);
  });
  it("tagsText sorts keys and omits requested ones", () => {
    expect(tagsText({ b: 2, a: "x", name: "n" }, ["name"])).toBe("a=x · b=2");
    expect(tagsText({})).toBe("");
  });
});

describe("windowStartIso", () => {
  const now = new Date("2026-06-09T00:00:00Z");
  it("maps presets to absolute UTC starts", () => {
    expect(windowStartIso("all", now)).toBeNull();
    expect(windowStartIso("30d", now)).toBe("2026-05-10T00:00:00.000Z");
    expect(windowStartIso("3mo", now)).toBe("2026-03-11T00:00:00.000Z");
    expect(windowStartIso("1y", now)).toBe("2025-06-09T00:00:00.000Z");
  });
});

describe("sortRows", () => {
  const rows = toBrowseRows([
    item({ history_fingerprint: "f1", name: "b", latest_single_value_summary: 2, point_count: 1 }),
    item({ history_fingerprint: "f2", name: "a", latest_single_value_summary: null, point_count: 3 }),
    item({ history_fingerprint: "f3", name: "c", latest_single_value_summary: 1, point_count: 2 }),
  ]);
  it("returns server order untouched for null sort", () => {
    expect(sortRows(rows, null).map((r) => r.fingerprint)).toEqual(["f1", "f2", "f3"]);
  });
  it("sorts by name asc and desc", () => {
    expect(sortRows(rows, { key: "name", dir: "asc" }).map((r) => r.name)).toEqual(["a", "b", "c"]);
    expect(sortRows(rows, { key: "name", dir: "desc" }).map((r) => r.name)).toEqual(["c", "b", "a"]);
  });
  it("sorts numbers and keeps a null SVS last in both directions", () => {
    expect(sortRows(rows, { key: "svs", dir: "asc" }).map((r) => r.fingerprint)).toEqual(["f3", "f1", "f2"]);
    expect(sortRows(rows, { key: "svs", dir: "desc" }).map((r) => r.fingerprint)).toEqual(["f1", "f3", "f2"]);
  });
  it("does not mutate its input", () => {
    const before = rows.map((r) => r.fingerprint);
    sortRows(rows, { key: "points", dir: "desc" });
    expect(rows.map((r) => r.fingerprint)).toEqual(before);
  });
});

describe("sparklinePoints", () => {
  it("spans the box and puts larger values higher (smaller y)", () => {
    const pts = sparklinePoints([1, 3, 2], 100, 20, 2);
    const ys = pts.split(" ").map((p) => Number(p.split(",")[1]));
    expect(ys[1]).toBeLessThan(ys[0]!);
    expect(ys[2]).toBeLessThan(ys[0]!);
    expect(ys[1]).toBeLessThan(ys[2]!);
  });
  it("draws a flat series as a midline", () => {
    const ys = sparklinePoints([5, 5, 5], 100, 20, 2).split(" ").map((p) => Number(p.split(",")[1]));
    expect(new Set(ys)).toEqual(new Set([10]));
  });
  it("is empty for no values", () => {
    expect(sparklinePoints([], 100, 20, 2)).toBe("");
  });
});
