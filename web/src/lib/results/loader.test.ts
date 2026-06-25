import { describe, expect, it, vi } from "vitest";

import type { createConbenchClient } from "../api/client";
import { loadResultsPage } from "./loader";

type Client = ReturnType<typeof createConbenchClient>;

const result = (id: string, overrides: Record<string, unknown> = {}) => ({
  id,
  run_id: "66f23037065241d6ac22aaeaea96d29b",
  run_reason: "commit",
  run_tags: { name: "commit:2315161817ad5dcb94891567e7ac48a35921e05a" },
  batch_id: "66f23037065241d6ac22aaeaea96d29b-1p",
  timestamp: "2026-06-04T18:41:00Z",
  unit: "s",
  single_value_summary: 1.01982,
  single_value_summary_type: "min",
  history_fingerprint: `fp-${id}`,
  case_name: "tpch",
  case_tags: {
    query_id: "TPCH-09",
    scale_factor: 1,
    format: "parquet",
    language: "R",
    ignored_noise: "not-primary",
  },
  commit: {
    hash: "2315161817ad5dcb94891567e7ac48a35921e05a",
    repository: "https://github.com/apache/arrow",
    timestamp: "2026-06-04T18:41:00Z",
  },
  has_error: false,
  ...overrides,
});

function fakeClient(page: unknown): {
  client: Client;
  GET: ReturnType<typeof vi.fn>;
} {
  const GET = vi.fn(async () => ({ data: page }));
  return { client: { GET } as unknown as Client, GET };
}

describe("loadResultsPage", () => {
  it("derives human-first result row identity from benchmark case metadata", async () => {
    const { client } = fakeClient({
      results: [result("06a220d0d94471c480001414453ee7fc")],
      next_page_cursor: null,
    });

    const page = await loadResultsPage(client, {
      query: {
        runID: "",
        batchID: "",
        runReason: "",
        earliestTimestamp: "",
        latestTimestamp: "",
      },
      cursor: null,
    });

    expect(page.rows[0]).toMatchObject({
      id: "06a220d0d94471c480001414453ee7fc",
      displayResultId: "06a220d0d944…453ee7fc",
      runId: "66f23037065241d6ac22aaeaea96d29b",
      displayRunId: "66f230370652…ea96d29b",
      batchId: "66f23037065241d6ac22aaeaea96d29b-1p",
      displayBatchId: "66f230370652…6d29b-1p",
      benchmarkName: "tpch",
      benchmarkTags: {
        query_id: "TPCH-09",
        scale_factor: 1,
        format: "parquet",
        language: "R",
        ignored_noise: "not-primary",
      },
      primaryTags: [
        { key: "query_id", value: "TPCH-09" },
        { key: "scale_factor", value: "1" },
        { key: "format", value: "parquet" },
        { key: "language", value: "R" },
      ],
      repositoryLabel: "apache/arrow",
      shortCommit: "23151618",
    });
  });
});
