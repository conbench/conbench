import { describe, expect, it, vi } from "vitest";

import type { createConbenchClient } from "../api/client";
import { loadBatchPage } from "./loader";

type Client = ReturnType<typeof createConbenchClient>;

const result = (id: string, overrides: Record<string, unknown> = {}) => ({
  id,
  run_id: "run-a",
  run_reason: "nightly",
  run_tags: { arch: "x86" },
  batch_id: "batch-a",
  timestamp: "2026-01-02T00:00:00Z",
  unit: "s",
  single_value_summary: 1.25,
  single_value_summary_type: "min",
  history_fingerprint: `fp-${id}`,
  case_name: "tpch",
  case_tags: {
    query_id: "TPCH-09",
    scale_factor: 1,
    format: "parquet",
    language: "R",
  },
  commit: {
    hash: "abcdef123456",
    repository: "https://github.com/apache/arrow",
    timestamp: "2026-01-02T00:00:00Z",
  },
  has_error: false,
  ...overrides,
});

function fakeClient(page: unknown, error: false | { detail: string } = false): {
  client: Client;
  GET: ReturnType<typeof vi.fn>;
} {
  const GET = vi.fn(async () =>
    error ? { error: { detail: error.detail } } : { data: page },
  );
  return { client: { GET } as unknown as Client, GET };
}

describe("loadBatchPage", () => {
  it("loads a bounded batch result page and groups rows by run", async () => {
    const { client, GET } = fakeClient({
      results: [
        result("r3", { run_id: "run-b", has_error: true }),
        result("r2", { run_id: "run-a" }),
        result("r1", { run_id: "run-a" }),
      ],
      next_page_cursor: "cur2",
    });

    const page = await loadBatchPage(client, "batch-a");

    expect(GET).toHaveBeenCalledWith("/api/benchmark-results", {
      params: { query: { batch_id: "batch-a", page_size: 100 } },
    });
    expect(page).toMatchObject({
      batchId: "batch-a",
      loadedResults: 3,
      loadedRuns: 2,
      loadedErrors: 1,
      loadedSeries: 3,
      repository: "https://github.com/apache/arrow",
      commitSha: "abcdef123456",
      shortCommit: "abcdef12",
      nextCursor: "cur2",
    });
    expect(page.runGroups).toHaveLength(2);
    expect(page.runGroups[0]).toMatchObject({
      runId: "run-b",
      runHref: "/runs/run-b",
      resultCount: 1,
      errorCount: 1,
      ciReportHref:
        "/ci/report?repository=https%3A%2F%2Fgithub.com%2Fapache%2Farrow&commit_sha=abcdef123456&run_ids=run-b&baseline=fork_point",
    });
    expect(page.runGroups[1]).toMatchObject({
      runId: "run-a",
      resultCount: 2,
      errorCount: 0,
    });
    expect(page.rows[0]).toMatchObject({
      id: "r3",
      displayResultId: "r3",
      benchmarkName: "tpch",
      primaryTags: [
        { key: "query_id", value: "TPCH-09" },
        { key: "scale_factor", value: "1" },
        { key: "format", value: "parquet" },
        { key: "language", value: "R" },
      ],
      resultHref: "/results/r3",
      trendHref: "/series/fp-r3",
      displayRunId: "run-b",
      runHref: "/runs/run-b",
      hasError: true,
    });
  });

  it("passes cursor when loading more", async () => {
    const { client, GET } = fakeClient({ results: [], next_page_cursor: null });
    await loadBatchPage(client, "batch-a", "cur1");
    expect(GET).toHaveBeenCalledWith("/api/benchmark-results", {
      params: { query: { batch_id: "batch-a", page_size: 100, cursor: "cur1" } },
    });
  });

  it("throws endpoint detail on failure", async () => {
    const { client } = fakeClient(null, { detail: "failed to list results" });
    await expect(loadBatchPage(client, "batch-a")).rejects.toThrow("failed to list results");
  });
});
