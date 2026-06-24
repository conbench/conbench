import { describe, expect, it, vi } from "vitest";

import type { createConbenchClient } from "../api/client";
import { loadRunPage } from "./loader";

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

describe("loadRunPage", () => {
  it("loads a bounded run result page and derives summary links", async () => {
    const { client, GET } = fakeClient({
      results: [
        result("r2", { has_error: true, batch_id: "batch-b" }),
        result("r1"),
      ],
      next_page_cursor: "cur2",
    });

    const page = await loadRunPage(client, "run-a");

    expect(GET).toHaveBeenCalledWith("/api/benchmark-results", {
      params: { query: { run_id: "run-a", page_size: 100 } },
    });
    expect(page).toMatchObject({
      runId: "run-a",
      runReason: "nightly",
      loadedResults: 2,
      loadedErrors: 1,
      loadedSeries: 2,
      loadedBatches: 2,
      repository: "https://github.com/apache/arrow",
      commitSha: "abcdef123456",
      shortCommit: "abcdef12",
      nextCursor: "cur2",
      ciReportHref:
        "/ci/report?repository=https%3A%2F%2Fgithub.com%2Fapache%2Farrow&commit_sha=abcdef123456&run_ids=run-a&baseline=fork_point",
    });
    expect(page.rows[0]).toMatchObject({
      id: "r2",
      resultHref: "/results/r2",
      trendHref: "/series/fp-r2",
      hasError: true,
    });
  });

  it("passes cursor when loading more", async () => {
    const { client, GET } = fakeClient({ results: [], next_page_cursor: null });
    await loadRunPage(client, "run-a", "cur1");
    expect(GET).toHaveBeenCalledWith("/api/benchmark-results", {
      params: { query: { run_id: "run-a", page_size: 100, cursor: "cur1" } },
    });
  });

  it("throws endpoint detail on failure", async () => {
    const { client } = fakeClient(null, { detail: "failed to list results" });
    await expect(loadRunPage(client, "run-a")).rejects.toThrow("failed to list results");
  });
});
