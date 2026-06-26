import { describe, expect, it } from "vitest";

import {
  DEFAULT_TREND_QUERY,
  formatBrowseQuery,
  formatCompareQuery,
  formatHomeQuery,
  formatResultListQuery,
  formatTrendQuery,
  interceptNavClick,
  matchRoute,
  parseBrowseQuery,
  parseCIReportQuery,
  parseCompareQuery,
  parseHomeQuery,
  parseResultListQuery,
  parseTrendQuery,
} from "./router";

describe("matchRoute", () => {
  it("matches the Phase-1 canonical result-entry route", () => {
    expect(matchRoute("/benchmarks/history/abc123")).toEqual({
      name: "series-leaf",
      resultId: "abc123",
      query: DEFAULT_TREND_QUERY,
    });
  });

  it("matches the by-result alias and tolerates a trailing slash", () => {
    expect(matchRoute("/series/by-result/abc123/")).toEqual({
      name: "series-leaf",
      resultId: "abc123",
      query: DEFAULT_TREND_QUERY,
    });
  });

  it("decodes a URL-encoded result id", () => {
    expect(matchRoute("/series/by-result/a%2Fb")).toEqual({
      name: "series-leaf",
      resultId: "a/b",
      query: DEFAULT_TREND_QUERY,
    });
  });

  it("returns not-found for an unknown path", () => {
    expect(matchRoute("/projects/arrow")).toEqual({ name: "not-found" });
  });

  it("returns not-found for a malformed percent-encoded id", () => {
    expect(matchRoute("/series/by-result/%E0%A4")).toEqual({ name: "not-found" });
  });
});

describe("browse route", () => {
  it("matches / as the recent-runs home", () => {
    expect(matchRoute("/")).toEqual({
      name: "home",
      query: { repository: "" },
    });
  });

  it("parses and formats the home repository selector", () => {
    const query = { repository: "https://github.com/apache/arrow-go" };
    expect(matchRoute("/", "?repository=https%3A%2F%2Fgithub.com%2Fapache%2Farrow-go")).toEqual({
      name: "home",
      query,
    });
    expect(parseHomeQuery(formatHomeQuery(query))).toEqual(query);
    expect(formatHomeQuery({ repository: "" })).toBe("");
  });

  it("matches /series as browse with default query", () => {
    expect(matchRoute("/series")).toEqual({
      name: "browse",
      query: { q: "", hardware: "", repository: "", window: "all" },
    });
  });

  it("parses filters from the search string", () => {
    expect(matchRoute("/series", "?q=tpch&hardware=m5&repository=https%3A%2F%2Fgithub.com%2Fo%2Fr&window=3mo")).toEqual({
      name: "browse",
      query: { q: "tpch", hardware: "m5", repository: "https://github.com/o/r", window: "3mo" },
    });
  });

  it("is total over junk search strings", () => {
    expect(parseBrowseQuery("?window=bogus&unknown=x")).toEqual({
      q: "", hardware: "", repository: "", window: "all",
    });
  });

  it("formats the canonical search string omitting defaults", () => {
    expect(formatBrowseQuery({ q: "", hardware: "", repository: "", window: "all" })).toBe("");
    expect(formatBrowseQuery({ q: "tpch", hardware: "", repository: "", window: "30d" })).toBe("?q=tpch&window=30d");
  });

  it("round-trips parse(format(q))", () => {
    const q = { q: "a b", hardware: "m5", repository: "https://github.com/o/r", window: "1y" as const };
    expect(parseBrowseQuery(formatBrowseQuery(q))).toEqual(q);
  });
});

describe("account route", () => {
  it("matches /account", () => {
    expect(matchRoute("/account")).toEqual({ name: "account" });
    expect(matchRoute("/account/")).toEqual({ name: "account" });
  });
});

describe("trend route", () => {
  it("matches /series/:fingerprint with default controls", () => {
    expect(matchRoute("/series/abc123")).toEqual({
      name: "trend",
      fingerprint: "abc123",
      query: { axis: "commit", range: "3mo", sigma: 2 },
    });
  });

  it("parses controls from the search string", () => {
    expect(matchRoute("/series/abc123", "?axis=time&range=all&sigma=5")).toEqual({
      name: "trend",
      fingerprint: "abc123",
      query: { axis: "time", range: "all", sigma: 5 },
    });
  });

  it("still matches /series/by-result/:id as a result-entry leaf", () => {
    expect(matchRoute("/series/by-result/r1")).toEqual({
      name: "series-leaf",
      resultId: "r1",
      query: DEFAULT_TREND_QUERY,
    });
  });

  it("is total over junk control values", () => {
    expect(parseTrendQuery("?axis=bogus&range=2026&sigma=4")).toEqual({
      axis: "commit",
      range: "3mo",
      sigma: 2,
    });
  });

  it("formats the canonical search string omitting defaults", () => {
    expect(formatTrendQuery({ axis: "commit", range: "3mo", sigma: 2 })).toBe("");
    expect(formatTrendQuery({ axis: "time", range: "all", sigma: 3 })).toBe(
      "?axis=time&range=all&sigma=3",
    );
  });

  it("round-trips parse(format(q))", () => {
    const q = { axis: "time", range: "30d", sigma: 1 } as const;
    expect(parseTrendQuery(formatTrendQuery(q))).toEqual(q);
  });
});

describe("result route", () => {
  it("matches /results as the result list", () => {
    expect(matchRoute("/results")).toEqual({
      name: "results-list",
      query: {
        runID: "",
        batchID: "",
        runReason: "",
        earliestTimestamp: "",
        latestTimestamp: "",
      },
    });
  });

  it("parses and formats result list filters", () => {
    const q = {
      runID: "run-a",
      batchID: "batch-a",
      runReason: "nightly",
      earliestTimestamp: "2026-01-01T00:00:00Z",
      latestTimestamp: "2026-01-02T00:00:00Z",
    };
    expect(parseResultListQuery(formatResultListQuery(q))).toEqual(q);
    expect(
      matchRoute(
        "/results",
        "?run_id=run-a&batch_id=batch-a&run_reason=nightly&earliest_timestamp=2026-01-01T00%3A00%3A00Z&latest_timestamp=2026-01-02T00%3A00%3A00Z",
      ),
    ).toEqual({ name: "results-list", query: q });
  });

  it("matches /results/:id", () => {
    expect(matchRoute("/results/r42")).toEqual({ name: "result", resultId: "r42" });
  });

  it("matches the benchmark-results alias", () => {
    expect(matchRoute("/benchmark-results/r42")).toEqual({ name: "result", resultId: "r42" });
  });

  it("decodes an encoded result id", () => {
    expect(matchRoute("/results/a%2Fb")).toEqual({ name: "result", resultId: "a/b" });
  });
});

describe("run route", () => {
  it("matches /runs/:runId", () => {
    expect(matchRoute("/runs/run-42")).toEqual({ name: "run", runId: "run-42" });
  });

  it("decodes an encoded run id", () => {
    expect(matchRoute("/runs/a%2Fb")).toEqual({ name: "run", runId: "a/b" });
  });
});

describe("batch route", () => {
  it("matches /batches/:batchId", () => {
    expect(matchRoute("/batches/batch-42")).toEqual({ name: "batch", batchId: "batch-42" });
  });

  it("decodes an encoded batch id", () => {
    expect(matchRoute("/batches/a%2Fb")).toEqual({ name: "batch", batchId: "a/b" });
  });
});

describe("ci report route", () => {
  it("matches /ci/report and parses selectors", () => {
    expect(
      matchRoute(
        "/ci/report",
        "?repository=https%3A%2F%2Fgithub.com%2Fo%2Fr&commit_sha=abc&run_ids=r1,r2&baseline_run_ids=b1,b2&baseline=parent&threshold=2&threshold_z=3",
      ),
    ).toEqual({
      name: "ci-report",
      query: {
        repository: "https://github.com/o/r",
        commit: "abc",
        runIDs: "r1,r2",
        baselineRunIDs: "b1,b2",
        baseline: "parent",
        threshold: "2",
        thresholdZ: "3",
      },
    });
  });

  it("is total over junk baseline values", () => {
    expect(parseCIReportQuery("?baseline=bad")).toEqual({
      repository: "",
      commit: "",
      runIDs: "",
      baselineRunIDs: "",
      baseline: "",
      threshold: "",
      thresholdZ: "",
    });
  });
});

describe("compare route", () => {
  it("matches /compare with both ids and default thresholds", () => {
    expect(matchRoute("/compare", "?baseline=b1&contender=c1")).toEqual({
      name: "compare",
      query: { baseline: "b1", contender: "c1", threshold: null, thresholdZ: null },
    });
  });

  it("parses explicit thresholds", () => {
    expect(parseCompareQuery("?baseline=b1&contender=c1&threshold=2.5&threshold_z=3")).toEqual({
      baseline: "b1",
      contender: "c1",
      threshold: 2.5,
      thresholdZ: 3,
    });
  });

  it("is total: junk and non-positive thresholds fall back to null", () => {
    expect(parseCompareQuery("?threshold=abc&threshold_z=-1")).toEqual({
      baseline: "",
      contender: "",
      threshold: null,
      thresholdZ: null,
    });
  });

  it("matches a trailing slash and ignores unrelated paths", () => {
    expect(matchRoute("/compare/", "")).toEqual({
      name: "compare",
      query: { baseline: "", contender: "", threshold: null, thresholdZ: null },
    });
    expect(matchRoute("/compare/extra")).toEqual({ name: "not-found" });
  });

  it("formats the canonical search string omitting empties and nulls", () => {
    expect(
      formatCompareQuery({ baseline: "", contender: "", threshold: null, thresholdZ: null }),
    ).toBe("");
    expect(
      formatCompareQuery({ baseline: "b1", contender: "c1", threshold: null, thresholdZ: 3 }),
    ).toBe("?baseline=b1&contender=c1&threshold_z=3");
  });

  it("round-trips parse(format(q))", () => {
    const q = { baseline: "b1", contender: "c1", threshold: 2.5, thresholdZ: 3 };
    expect(parseCompareQuery(formatCompareQuery(q))).toEqual(q);
  });
});

describe("interceptNavClick", () => {
  it("intercepts only unmodified primary clicks", () => {
    expect(interceptNavClick(new MouseEvent("click", { button: 0 }))).toBe(true);
    expect(interceptNavClick(new MouseEvent("click", { button: 1 }))).toBe(false);
    expect(interceptNavClick(new MouseEvent("click", { button: 0, metaKey: true }))).toBe(false);
    expect(interceptNavClick(new MouseEvent("click", { button: 0, ctrlKey: true }))).toBe(false);
    expect(interceptNavClick(new MouseEvent("click", { button: 0, shiftKey: true }))).toBe(false);
    expect(interceptNavClick(new MouseEvent("click", { button: 0, altKey: true }))).toBe(false);
  });
});
