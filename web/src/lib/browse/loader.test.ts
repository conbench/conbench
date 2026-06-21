import { describe, expect, it, vi } from "vitest";

import type { createConbenchClient } from "../api/client";
import { DEFAULT_BROWSE_QUERY } from "../router";
import { listSeries } from "./loader";

type Client = ReturnType<typeof createConbenchClient>;

const seriesItem = {
  history_fingerprint: "fp1",
  name: "demo",
  tags: { name: "demo" },
  context: {},
  hardware: { id: "h1", type: "machine", name: "m5", hash: "hw1" },
  repository: "https://github.com/conbench/demo",
  unit: "s",
  less_is_better: true,
  status: "stable",
  latest_result_id: "r1",
  latest_single_value_summary: 1.5,
  latest_single_value_summary_type: "min",
  latest_commit_sha: "abc1234def",
  latest_commit_timestamp: "2024-01-07T12:00:00Z",
  latest_result_timestamp: "2024-01-07T13:00:00Z",
  point_count: 6,
  sparkline: [1.4, 1.5],
};

function fakeClient(
  page: unknown,
  error: false | { detail: string } = false,
): { client: Client; GET: ReturnType<typeof vi.fn> } {
  const GET = vi.fn(async () =>
    error ? { error: { detail: error.detail } } : { data: page },
  );
  return { client: { GET } as unknown as Client, GET };
}

describe("listSeries", () => {
  it("maps filters, window, and cursor onto the endpoint params", async () => {
    const { client, GET } = fakeClient({ series: [seriesItem], next_page_cursor: "cur2" });
    const now = new Date("2026-06-09T00:00:00Z");
    const page = await listSeries(
      client,
      { q: "demo", hardware: "m5", repository: "https://github.com/conbench/demo", window: "30d" },
      "cur1",
      now,
    );
    expect(GET).toHaveBeenCalledWith("/api/series", {
      params: {
        query: {
          page_size: 25,
          q: "demo",
          hardware: "m5",
          repository: "https://github.com/conbench/demo",
          active_since: "2026-05-10T00:00:00.000Z",
          cursor: "cur1",
        },
      },
    });
    expect(page.rows).toHaveLength(1);
    expect(page.rows[0]!.name).toBe("demo");
    expect(page.nextCursor).toBe("cur2");
  });

  it("omits empty filters and the cursor on the first page", async () => {
    const { client, GET } = fakeClient({ series: [], next_page_cursor: null });
    const page = await listSeries(client, DEFAULT_BROWSE_QUERY);
    expect(GET).toHaveBeenCalledWith("/api/series", { params: { query: { page_size: 25 } } });
    expect(page.rows).toEqual([]);
    expect(page.nextCursor).toBeNull();
  });

  it("requests a production-credible first page", async () => {
    const { client, GET } = fakeClient({ series: [], next_page_cursor: null });
    await listSeries(client, DEFAULT_BROWSE_QUERY);
    expect(GET).toHaveBeenCalledWith("/api/series", { params: { query: { page_size: 25 } } });
  });

  it("treats a null series as an empty page", async () => {
    const { client } = fakeClient({ series: null, next_page_cursor: null });
    const page = await listSeries(client, DEFAULT_BROWSE_QUERY);
    expect(page.rows).toEqual([]);
    expect(page.nextCursor).toBeNull();
  });

  it("throws when the endpoint errors", async () => {
    const { client } = fakeClient(null, { detail: "failed to list series" });
    await expect(listSeries(client, DEFAULT_BROWSE_QUERY)).rejects.toThrow("series");
  });

  it("preserves server detail for browse failures", async () => {
    const { client } = fakeClient(null, {
      detail: "series query timed out; narrow your search",
    });
    await expect(listSeries(client, { ...DEFAULT_BROWSE_QUERY, q: "tpch" })).rejects.toThrow(
      /series query timed out; narrow your search/i,
    );
  });
});
