import { describe, expect, it, vi } from "vitest";

import type { createConbenchClient } from "../api/client";
import { loadTrend } from "./loader";

type Client = ReturnType<typeof createConbenchClient>;

const zsNull = null;

const sample = (id: string, ts: string) => ({
  benchmark_result_id: id,
  commit_hash: `sha-${id}`,
  commit_message: "msg",
  commit_repository: "https://github.com/conbench/demo",
  commit_timestamp: ts,
  hardware_hash: "hw1",
  mean: 1.1,
  result_timestamp: ts,
  single_value_summary: 1.1,
  single_value_summary_type: "min",
  unit: "s",
  zscorestats: zsNull,
});

const detail = {
  id: "r1",
  tags: { name: "demo-benchmark", scale: "sf10" },
  context: { compiler: "gcc" },
  hardware: { id: "h1", type: "machine", name: "m5", hash: "hw1" },
  commit_repo_url: "https://github.com/conbench/demo",
  unit: "s",
  less_is_better: true,
  history_fingerprint: "fp1",
};

const seriesItem = {
  history_fingerprint: "fp1",
  name: "demo-benchmark",
  tags: { name: "demo-benchmark", scale: "sf10" },
  context: { compiler: "gcc" },
  hardware: { id: "h1", type: "machine", name: "m5", hash: "hw1" },
  repository: "https://github.com/conbench/demo",
  unit: "s",
  less_is_better: true,
  status: "stable",
  latest_result_id: "r2",
  latest_single_value_summary: 1.1,
  latest_single_value_summary_type: "min",
  latest_commit_sha: "sha-r2",
  latest_commit_timestamp: "2024-01-08T12:00:00Z",
  latest_result_timestamp: "2024-01-08T12:00:00Z",
  point_count: 2,
  sparkline: [1.0, 1.1],
};

describe("loadTrend by result", () => {
  it("loads identity from result detail and points from the result history", async () => {
    const GET = vi.fn(async (url: string) => {
      if (url === "/api/benchmark-results/{id}") return { data: detail };
      if (url === "/api/history/{benchmark_result_id}") {
        return {
          data: {
            history_fingerprint: "fp1",
            samples: [sample("r2", "2024-01-08T12:00:00Z"), sample("r1", "2024-01-07T12:00:00Z")],
          },
        };
      }
      throw new Error(`unexpected url ${url}`);
    });
    const vm = await loadTrend({ GET } as unknown as Client, { kind: "result", resultId: "r1" });
    expect(vm.identity).toMatchObject({
      benchmarkName: "demo-benchmark",
      caseTags: { scale: "sf10" },
      hardwareName: "m5",
      unit: "s",
      lessIsBetter: true,
      fingerprint: "fp1",
    });
    // ordered ascending by chart time
    expect(vm.points.map((p) => p.resultId)).toEqual(["r1", "r2"]);
    expect(vm.unitConsistent).toBe(true);
  });

  it("derives compact trend identity labels from result detail", async () => {
    const GET = vi.fn(async (url: string) => {
      if (url === "/api/benchmark-results/{id}") {
        return {
          data: {
            ...detail,
            hardware: {
              ...detail.hardware,
              hash: "0123456789abcdef0123456789abcdef",
            },
            commit_repo_url: "https://github.com/apache/arrow",
            history_fingerprint: "fff41571debd35f721110e6a7d99440a",
          },
        };
      }
      if (url === "/api/history/{benchmark_result_id}") {
        return { data: { history_fingerprint: "fp1", samples: [] } };
      }
      throw new Error(`unexpected url ${url}`);
    });

    const vm = await loadTrend({ GET } as unknown as Client, { kind: "result", resultId: "r1" });

    expect(vm.identity.displayFingerprint).toBe("fff41571debd…7d99440a");
    expect(vm.identity.displayHardwareHash).toBe("0123456789ab…89abcdef");
    expect(vm.identity.repositoryLabel).toBe("apache/arrow");
  });

  it("throws when the detail load fails", async () => {
    const GET = vi.fn(async () => ({ error: { detail: "boom" } }));
    await expect(
      loadTrend({ GET } as unknown as Client, { kind: "result", resultId: "rX" }),
    ).rejects.toThrow("rX");
  });
});

describe("loadTrend by fingerprint", () => {
  it("loads identity from the series row and points from the fingerprint history", async () => {
    const GET = vi.fn(async (url: string, opts?: { params?: { query?: unknown } }) => {
      if (url === "/api/history") {
        expect(opts?.params?.query).toEqual({ fingerprint: "fp1" });
        return {
          data: { history_fingerprint: "fp1", samples: [sample("r1", "2024-01-07T12:00:00Z")] },
        };
      }
      if (url === "/api/series") {
        expect(opts?.params?.query).toEqual({ fingerprint: "fp1", page_size: 1 });
        return { data: { series: [seriesItem], next_page_cursor: null } };
      }
      throw new Error(`unexpected url ${url}`);
    });
    const vm = await loadTrend({ GET } as unknown as Client, {
      kind: "fingerprint",
      fingerprint: "fp1",
    });
    expect(vm.identity).toMatchObject({
      benchmarkName: "demo-benchmark",
      caseTags: { scale: "sf10" },
      lessIsBetter: true,
      fingerprint: "fp1",
    });
    expect(vm.points).toHaveLength(1);
    expect(vm.identity.displayFingerprint).toBe("fp1");
    expect(vm.identity.displayHardwareHash).toBe("hw1");
    expect(vm.identity.repositoryLabel).toBe("conbench/demo");
  });

  it("throws a not-found error for an unknown fingerprint", async () => {
    const GET = vi.fn(async (url: string) =>
      url === "/api/history"
        ? { data: { history_fingerprint: "nope", samples: [] } }
        : { data: { series: [], next_page_cursor: null } },
    );
    await expect(
      loadTrend({ GET } as unknown as Client, { kind: "fingerprint", fingerprint: "nope" }),
    ).rejects.toThrow("not found");
  });

  it("treats null samples as an empty series", async () => {
    const GET = vi.fn(async (url: string) =>
      url === "/api/history"
        ? { data: { history_fingerprint: "fp1", samples: null } }
        : { data: { series: [seriesItem], next_page_cursor: null } },
    );
    const vm = await loadTrend({ GET } as unknown as Client, {
      kind: "fingerprint",
      fingerprint: "fp1",
    });
    expect(vm.points).toEqual([]);
  });
});
