import { describe, expect, it, vi } from "vitest";

import type { createConbenchClient } from "../api/client";
import { listRecentRuns } from "./loader";

type Client = ReturnType<typeof createConbenchClient>;

function fakeClient(page: unknown, error: false | { detail: string } = false): {
  client: Client;
  GET: ReturnType<typeof vi.fn>;
} {
  const GET = vi.fn(async () =>
    error ? { error: { detail: error.detail } } : { data: page },
  );
  return { client: { GET } as unknown as Client, GET };
}

describe("listRecentRuns", () => {
  it("loads a production-credible recent-run page", async () => {
    const { client, GET } = fakeClient({
      runs: [
        {
          run_id: "run-a",
          run_reason: "nightly",
          run_tags: { arch: "x86" },
          batch_count: 1,
          latest_batch_id: "batch-a",
          result_count: 180,
          error_count: 1,
          series_count: 90,
          latest_result_id: "result-a",
          repository: "https://github.com/apache/arrow",
          commit_sha: "abcdef123456",
          first_result_at: "2026-01-01T00:00:00Z",
          last_result_at: "2026-01-02T00:00:00Z",
          commit: {
            hash: "abcdef123456",
            repository: "https://github.com/apache/arrow",
            timestamp: "2026-01-02T00:00:00Z",
          },
        },
      ],
    });

    const page = await listRecentRuns(client);

    expect(GET).toHaveBeenCalledWith("/api/runs/recent", {
      params: { query: { page_size: 25 } },
    });
    expect(page.runs).toHaveLength(1);
    expect(page.runs[0]).toMatchObject({
      runId: "run-a",
      runReason: "nightly",
      resultCount: 180,
      errorCount: 1,
      seriesCount: 90,
      runHref: "/runs/run-a",
      latestBatchHref: "/batches/batch-a",
      latestResultHref: "/results/result-a",
      shortCommit: "abcdef12",
    });
    expect(page.runs[0]!.ciReportHref).toBe(
      "/ci/report?repository=https%3A%2F%2Fgithub.com%2Fapache%2Farrow&commit_sha=abcdef123456&run_ids=run-a&baseline=fork_point",
    );
  });

  it("treats null runs as an empty page", async () => {
    const { client } = fakeClient({ runs: null });
    await expect(listRecentRuns(client)).resolves.toEqual({ runs: [] });
  });

  it("throws endpoint detail on failure", async () => {
    const { client } = fakeClient(null, { detail: "statement timeout" });
    await expect(listRecentRuns(client)).rejects.toThrow("statement timeout");
  });
});
