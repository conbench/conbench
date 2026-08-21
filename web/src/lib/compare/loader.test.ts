import { describe, expect, it, vi } from "vitest";

import type { createConbenchClient } from "../api/client";
import { loadCompare, NotComparableError } from "./loader";

type Client = ReturnType<typeof createConbenchClient>;

const QUERY = { baseline: "b1", contender: "c1", threshold: null, thresholdZ: null };

const detail = (id: string) => ({
  id,
  batch_id: null,
  run_id: `run-${id}`,
  run_reason: "commit",
  run_tags: {},
  tags: { name: "demo-benchmark", scale: "sf10" },
  context: { compiler: "gcc" },
  info: {},
  hardware: { id: "h1", type: "machine", name: "m5", hash: "hw1" },
  commit: {
    id: `c-${id}`,
    message: `msg ${id}`,
    repository: "https://github.com/conbench/demo",
    sha: `sha-${id}`,
    timestamp: "2024-01-07T12:00:00Z",
  },
  commit_repo_url: "https://github.com/conbench/demo",
  unit: "s",
  less_is_better: true,
  single_value_summary: 1.5,
  single_value_summary_type: "min",
  iterations: 3,
  data: [1.5],
  times: null,
  time_unit: null,
  error: null,
  stats: { min: null, max: null, mean: 1.5, median: null, q1: null, q3: null, stdev: null, iqr: null },
  history_fingerprint: "fp1",
  timestamp: "2024-01-07T13:00:00Z",
});

const sample = (id: string, day: number) => ({
  benchmark_result_id: id,
  commit_hash: `sha-${id}`,
  commit_message: "msg",
  commit_repository: "https://github.com/conbench/demo",
  commit_timestamp: `2024-01-0${day}T12:00:00Z`,
  data: null,
  hardware_hash: "hw1",
  mean: 1.5,
  result_timestamp: `2024-01-0${day}T13:00:00Z`,
  single_value_summary: 1.5,
  single_value_summary_type: "min",
  unit: "s",
  run_tags: {},
  info: {},
  change_annotations: {},
  zscorestats: null,
});

const compareBody = {
  analysis: {
    lookback_z_score: {
      improvement_indicated: false,
      regression_indicated: true,
      z_score: -6.3,
      z_threshold: 5,
    },
    pairwise: null,
  },
  baseline: { benchmark_result_id: "b1", run_id: "run-b1", single_value_summary: 1.5 },
  contender: { benchmark_result_id: "c1", run_id: "run-c1", single_value_summary: 1.8 },
  less_is_better: true,
  unit: "s",
};

function fakeClient(over: Record<string, unknown> = {}): Client {
  const GET = vi.fn(async (url: string, opts?: { params?: { path?: { id?: string } } }) => {
    if (url in over) return over[url];
    if (url === "/api/compare/benchmark-results") return { data: compareBody };
    if (url === "/api/benchmark-results/{id}") {
      return { data: detail(opts?.params?.path?.id ?? "b1") };
    }
    if (url === "/api/history/{benchmark_result_id}") {
      return {
        data: {
          history_fingerprint: "fp1",
          samples: [sample("b1", 1), sample("x", 2), sample("c1", 3)],
        },
      };
    }
    throw new Error(`unexpected ${url}`);
  });
  return { GET } as unknown as Client;
}

describe("loadCompare", () => {
  it("assembles verdicts, both sides, and the marked mini-trend", async () => {
    const client = fakeClient();
    const vm = await loadCompare(client, QUERY);
    expect(vm.status).toBe("regressed");
    expect(vm.lookback?.z_score).toBe(-6.3);
    expect(vm.pairwise).toBeNull();
    expect(vm.unit).toBe("s");
    expect(vm.lessIsBetter).toBe(true);
    expect(vm.baseline.id).toBe("b1");
    expect(vm.contender.id).toBe("c1");
    expect(vm.points.map((p) => p.resultId)).toEqual(["b1", "x", "c1"]);
    expect(vm.marked).toEqual([0, 2]);
  });

  it("sends explicit thresholds and omits null ones", async () => {
    const client = fakeClient();
    await loadCompare(client, { ...QUERY, thresholdZ: 3 });
    const compareCall = (client.GET as ReturnType<typeof vi.fn>).mock.calls.find(
      (c) => c[0] === "/api/compare/benchmark-results",
    );
    expect(compareCall?.[1]?.params?.query).toEqual({
      baseline_result_id: "b1",
      contender_result_id: "c1",
      threshold_z: 3,
    });
  });

  it("throws NotComparableError with the endpoint reason on a 422, before any other fetch", async () => {
    const client = fakeClient({
      "/api/compare/benchmark-results": {
        error: { detail: "not comparable: history fingerprints differ" },
        response: { status: 422 },
      },
    });
    await expect(loadCompare(client, QUERY)).rejects.toThrow(NotComparableError);
    await expect(loadCompare(client, QUERY)).rejects.toThrow(
      "not comparable: history fingerprints differ",
    );
    const urls = (client.GET as ReturnType<typeof vi.fn>).mock.calls.map((c) => c[0]);
    expect(urls).toEqual([
      "/api/compare/benchmark-results",
      "/api/compare/benchmark-results",
    ]);
  });

  it("throws a plain error on a non-422 compare failure", async () => {
    const client = fakeClient({
      "/api/compare/benchmark-results": {
        error: { detail: "boom" },
        response: { status: 500 },
      },
    });
    const err = await loadCompare(client, QUERY).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(Error);
    expect(err).not.toBeInstanceOf(NotComparableError);
    expect((err as Error).message).toContain("b1");
  });

  it("treats null history samples as an unmarked empty mini-trend", async () => {
    const client = fakeClient({
      "/api/history/{benchmark_result_id}": {
        data: { history_fingerprint: "fp1", samples: null },
      },
    });
    const vm = await loadCompare(client, QUERY);
    expect(vm.points).toEqual([]);
    expect(vm.marked).toEqual([]);
  });
});
