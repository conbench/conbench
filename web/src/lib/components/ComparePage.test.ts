import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ComparePage from "./ComparePage.svelte";

const GET = vi.fn();
vi.mock("../api/client", () => ({
  createConbenchClient: () => ({ GET }),
}));
vi.mock("./SeriesChart.svelte", async () => await import("./SeriesChart.stub.svelte"));

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

const compareBody = (lookback: unknown, pairwise: unknown) => ({
  analysis: { lookback_z_score: lookback, pairwise },
  baseline: { benchmark_result_id: "b1", run_id: "run-b1", single_value_summary: 1.5 },
  contender: { benchmark_result_id: "c1", run_id: "run-c1", single_value_summary: 1.8 },
  less_is_better: true,
  unit: "s",
});

const seriesListItem = (overrides: Record<string, unknown> = {}) => ({
  history_fingerprint: "fp-shared",
  name: "demo-benchmark",
  tags: { name: "demo-benchmark", dataset: "uniform" },
  context: { compiler: "gcc-13" },
  hardware: { id: "h1", type: "machine", name: "demo-runner", hash: "hw1" },
  latest_single_value_summary: 1.45,
  unit: "s",
  point_count: 2,
  sparkline: [1, 1.45],
  status: "stable",
  latest_commit_sha: "sha-c1abcdef",
  latest_commit_timestamp: "2024-01-06T00:00:00Z",
  repository: "https://github.com/conbench/demo",
  less_is_better: true,
  ...overrides,
});

const historySample = (over: Record<string, unknown>) => ({
  benchmark_result_id: "x",
  commit_hash: "sha-x",
  commit_message: "msg",
  commit_repository: "repo",
  commit_timestamp: "2024-01-01T00:00:00Z",
  data: null,
  hardware_hash: "hw1",
  mean: 1,
  result_timestamp: "2024-01-01T01:00:00Z",
  single_value_summary: 1,
  single_value_summary_type: "min",
  unit: "s",
  run_tags: {},
  info: {},
  change_annotations: {},
  zscorestats: null,
  ...over,
});

const PICKER_SAMPLES = [
  historySample({
    benchmark_result_id: "b1",
    commit_hash: "sha-b1",
    commit_message: "Add baseline sort",
    commit_timestamp: "2024-01-01T00:00:00Z",
    single_value_summary: 1.0,
  }),
  historySample({
    benchmark_result_id: "c1",
    commit_hash: "sha-c1",
    commit_message: "Cache-friendly layout",
    commit_timestamp: "2024-01-06T00:00:00Z",
    single_value_summary: 1.45,
  }),
];

const EMPTY_QUERY = { baseline: "", contender: "", threshold: null, thresholdZ: null };

function mockHappy(lookback: unknown, pairwise: unknown) {
  GET.mockImplementation(async (url: string, opts?: { params?: { path?: { id?: string } } }) => {
    if (url === "/api/compare/benchmark-results") {
      return { data: compareBody(lookback, pairwise) };
    }
    if (url === "/api/benchmark-results/{id}") {
      return { data: detail(opts?.params?.path?.id ?? "b1") };
    }
    if (url === "/api/history/{benchmark_result_id}") {
      return {
        data: {
          history_fingerprint: "fp1",
          samples: [
            {
              benchmark_result_id: "b1",
              commit_hash: "sha-b1",
              commit_message: "msg",
              commit_repository: "repo",
              commit_timestamp: "2024-01-01T12:00:00Z",
              data: null,
              hardware_hash: "hw1",
              mean: 1.5,
              result_timestamp: "2024-01-01T13:00:00Z",
              single_value_summary: 1.5,
              single_value_summary_type: "min",
              unit: "s",
              run_tags: {},
              info: {},
              change_annotations: {},
              zscorestats: null,
            },
            {
              benchmark_result_id: "c1",
              commit_hash: "sha-c1",
              commit_message: "msg",
              commit_repository: "repo",
              commit_timestamp: "2024-01-02T12:00:00Z",
              data: null,
              hardware_hash: "hw1",
              mean: 1.8,
              result_timestamp: "2024-01-02T13:00:00Z",
              single_value_summary: 1.8,
              single_value_summary_type: "min",
              unit: "s",
              run_tags: {},
              info: {},
              change_annotations: {},
              zscorestats: null,
            },
          ],
        },
      };
    }
    throw new Error(`unexpected ${url}`);
  });
}

// Engine sign convention: oriented values are negative for regressions.
const REGRESSED = {
  improvement_indicated: false,
  regression_indicated: true,
  z_score: -6.3,
  z_threshold: 5,
};

beforeEach(() => {
  GET.mockReset();
  window.history.replaceState(null, "", "/compare?baseline=b1&contender=c1");
});

describe("ComparePage", () => {
  it("renders the benchmark picker when ids are missing, without calling the API", () => {
    render(ComparePage, { props: { query: EMPTY_QUERY } });
    expect(screen.getByRole("searchbox", { name: /search benchmarks/i })).toBeInTheDocument();
    expect(screen.getByText(/start typing to find a benchmark/i)).toBeInTheDocument();
    expect(GET).not.toHaveBeenCalled();
  });

  it("searches a benchmark and compares its latest two commits in one click", async () => {
    GET.mockImplementation(async (url: string) => {
      if (url === "/api/series") {
        return { data: { series: [seriesListItem()], next_page_cursor: null } };
      }
      if (url === "/api/history") {
        return { data: { samples: PICKER_SAMPLES } };
      }
      throw new Error(`unexpected ${url}`);
    });

    render(ComparePage, { props: { query: EMPTY_QUERY } });

    await fireEvent.input(screen.getByRole("searchbox", { name: /search benchmarks/i }), {
      target: { value: "demo" },
    });
    await waitFor(() => screen.getByRole("button", { name: /demo-benchmark/i }));
    await fireEvent.click(screen.getByRole("button", { name: /demo-benchmark/i }));

    // The latest commit (contender) and the one before it (baseline) are
    // preselected, so the page is one click from a comparison.
    const compareBtn = await screen.findByRole("button", { name: /^Compare/ });
    expect(compareBtn).toBeEnabled();
    await fireEvent.click(compareBtn);

    expect(window.location.pathname).toBe("/compare");
    expect(window.location.search).toBe("?baseline=b1&contender=c1");
  });

  it("compares by pasted result IDs via the advanced option, without searching", async () => {
    render(ComparePage, { props: { query: EMPTY_QUERY } });

    await fireEvent.click(screen.getByRole("button", { name: /advanced: compare by result id/i }));
    await fireEvent.input(screen.getByLabelText(/baseline result id/i), { target: { value: "b1" } });
    await fireEvent.input(screen.getByLabelText(/contender result id/i), { target: { value: "c1" } });
    await fireEvent.click(screen.getByRole("button", { name: /open compare/i }));

    expect(window.location.pathname).toBe("/compare");
    expect(window.location.search).toBe("?baseline=b1&contender=c1");
    expect(GET).not.toHaveBeenCalled();
  });

  it("preserves a one-sided compare URL in the advanced result-ID picker", async () => {
    render(ComparePage, {
      props: { query: { baseline: "b1", contender: "", threshold: null, thresholdZ: null } },
    });

    await fireEvent.click(screen.getByRole("button", { name: /advanced: compare by result id/i }));
    expect(screen.getByLabelText(/baseline result id/i)).toHaveValue("b1");
    expect(screen.getByLabelText(/contender result id/i)).toHaveValue("");
    expect(GET).not.toHaveBeenCalled();
  });

  it("renders the badge, verdict rows, side table, and marked mini-trend", async () => {
    mockHappy(REGRESSED, {
      improvement_indicated: false,
      regression_indicated: false,
      percent_change: 4.25,
      percent_threshold: 5,
    });
    render(ComparePage, { props: { query: QUERY } });
    await waitFor(() => screen.getByText("regressed"));
    expect(screen.getByRole("main")).toHaveClass("compare-page");
    expect(screen.getByRole("region", { name: /comparison verdict/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /threshold controls/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /baseline and contender/i })).toBeInTheDocument();
    expect(screen.getByText("z -6.30 vs threshold 5 — regression indicated")).toBeInTheDocument();
    expect(screen.getByText("+4.3% vs threshold 5% — within threshold")).toBeInTheDocument();
    expect(screen.getByText("sha-b1")).toBeInTheDocument();
    expect(screen.getByText("sha-c1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view full trend/i })).toHaveAttribute(
      "href",
      "/series/fp1",
    );
    expect(document.querySelector(".chart-stub")).not.toBeNull();
  });

  it("wraps the side table for responsive layouts", async () => {
    mockHappy(REGRESSED, null);
    const { container } = render(ComparePage, { props: { query: QUERY } });
    await waitFor(() => screen.getByText("regressed"));
    expect(container.querySelector(".sides-list > table.sides")).not.toBeNull();
  });

  it("groups commit mobile cell content into one value item", async () => {
    mockHappy(REGRESSED, null);
    render(ComparePage, { props: { query: QUERY } });
    await waitFor(() => screen.getByText("regressed"));
    const baselineCommitCell = screen.getByRole("link", { name: "sha-b1" }).closest("td");
    expect(baselineCommitCell?.querySelector(".cell-value")).not.toBeNull();
    expect(baselineCommitCell?.querySelector(".cell-value .msg")).toHaveTextContent("msg b1");
  });

  it("renders n/a for null verdicts and an insufficient badge", async () => {
    mockHappy(null, null);
    render(ComparePage, { props: { query: QUERY } });
    await waitFor(() => screen.getByText("insufficient"));
    expect(screen.getAllByText("n/a")).toHaveLength(2);
  });

  it("surfaces the endpoint's 422 inline", async () => {
    GET.mockImplementation(async (url: string) => {
      if (url === "/api/compare/benchmark-results") {
        return {
          error: { detail: "not comparable: history fingerprints differ" },
          response: { status: 422 },
        };
      }
      return { data: detail("b1") };
    });
    render(ComparePage, { props: { query: QUERY } });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/history fingerprints differ/),
    );
  });

  it("shows the error state when loading fails", async () => {
    GET.mockResolvedValue({ error: { detail: "boom" }, response: { status: 500 } });
    render(ComparePage, { props: { query: QUERY } });
    await waitFor(() => expect(screen.getByText(/failed to load/i)).toBeInTheDocument());
  });

  it("clears a stale not-comparable alert when a refetch fails generically", async () => {
    GET.mockImplementation(async (url: string) => {
      if (url === "/api/compare/benchmark-results") {
        return {
          error: { detail: "not comparable: history fingerprints differ" },
          response: { status: 422 },
        };
      }
      return { data: detail("b1") };
    });
    const { rerender } = render(ComparePage, { props: { query: QUERY } });
    await waitFor(() => screen.getByRole("alert"));

    GET.mockResolvedValue({ error: { detail: "boom" }, response: { status: 500 } });
    await rerender({ query: { ...QUERY, thresholdZ: 3 } });
    await waitFor(() => expect(screen.getByText(/failed to load/i)).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("writes threshold changes to the URL and refetches on the new query", async () => {
    mockHappy(REGRESSED, null);
    const { rerender } = render(ComparePage, { props: { query: QUERY } });
    await waitFor(() => screen.getByText("regressed"));
    await fireEvent.change(screen.getByLabelText(/threshold σ/i), { target: { value: "3" } });
    expect(window.location.search).toBe("?baseline=b1&contender=c1&threshold_z=3");

    GET.mockClear();
    mockHappy(REGRESSED, null);
    await rerender({ query: { ...QUERY, thresholdZ: 3 } });
    await waitFor(() => {
      const call = GET.mock.calls.find((c) => c[0] === "/api/compare/benchmark-results");
      expect(call?.[1]?.params?.query).toMatchObject({ threshold_z: 3 });
    });
  });
});
