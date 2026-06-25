import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { components } from "../api/schema";
import { DEFAULT_TREND_QUERY } from "../router";
import TrendPage from "./TrendPage.svelte";

const GET = vi.fn();
vi.mock("../api/client", () => ({
  createConbenchClient: () => ({ GET }),
}));
vi.mock("./SeriesChart.svelte", async () => await import("./SeriesChart.stub.svelte"));

type HistorySample = components["schemas"]["HistorySample"];
type ZScoreStats = components["schemas"]["ZScoreStats"];

function zstats(over: Partial<NonNullable<ZScoreStats>> = {}): ZScoreStats {
  return {
    begins_distribution_change: false,
    is_outlier: false,
    is_step: false,
    residual: 0.1,
    rolling_mean: 1,
    rolling_mean_excluding_this_commit: 1,
    rolling_stddev: 0.05,
    segment_id: 0,
    ...over,
  };
}

const sample = (
  id: string,
  ts: string,
  svs = 1.1,
  over: Partial<HistorySample> = {},
): HistorySample => ({
  benchmark_result_id: id,
  commit_hash: `sha-${id}`,
  commit_message: "msg",
  commit_repository: "https://github.com/conbench/demo",
  commit_timestamp: ts,
  hardware_hash: "hw1",
  mean: svs,
  result_timestamp: ts,
  single_value_summary: svs,
  single_value_summary_type: "min",
  unit: "s",
  zscorestats: null,
  ...over,
});

const manySamples = (n: number) =>
  Array.from({ length: n }, (_, i) =>
    sample(`r${i}`, `2024-01-${String((i % 28) + 1).padStart(2, "0")}T12:00:00Z`, i + 1),
  );

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

function mockResultEntry(samples: unknown[]) {
  GET.mockImplementation(async (url: string) => {
    if (url === "/api/benchmark-results/{id}") return { data: detail };
    if (url === "/api/history/{benchmark_result_id}") {
      return { data: { history_fingerprint: "fp1", samples } };
    }
    throw new Error(`unexpected ${url}`);
  });
}

beforeEach(() => {
  GET.mockReset();
  window.history.replaceState(null, "", "/benchmarks/history/r1");
});

const RESULT_SOURCE = { kind: "result", resultId: "r1" } as const;

describe("TrendPage", () => {
  it("renders header identity, orientation, controls, and the table", async () => {
    mockResultEntry([sample("r1", "2024-01-07T12:00:00Z")]);
    render(TrendPage, {
      props: { source: RESULT_SOURCE, query: { ...DEFAULT_TREND_QUERY, range: "all" } },
    });
    await waitFor(() => screen.getByRole("heading", { name: "demo-benchmark" }));
    expect(screen.getByText(/scale=sf10/)).toBeInTheDocument();
    expect(screen.getByText(/lower is better/)).toBeInTheDocument();
    expect(screen.getByText("repo: conbench/demo")).toHaveAttribute(
      "title",
      "https://github.com/conbench/demo",
    );
    expect(screen.getByText("series fp1")).toHaveAttribute("title", "fp1");
    expect(screen.getByText("hardware hw1")).toHaveAttribute("title", "hw1");
    expect(screen.getByLabelText(/range/i)).toHaveValue("all");
    expect(screen.getByLabelText(/band/i)).toHaveValue("2");
    expect(screen.getByLabelText(/x-axis/i)).toHaveValue("commit");
    expect(screen.getByRole("link", { name: "sha-r1" })).toBeInTheDocument();
  });

  it("uses the shared dashboard shell primitives for context, metrics, and filters", async () => {
    mockResultEntry([
      sample("r1", "2024-01-07T12:00:00Z"),
      sample("r2", "2024-01-08T12:00:00Z", 1.4, {
        zscorestats: zstats({ is_outlier: true, residual: 0.3, rolling_stddev: 0.1 }),
      }),
      sample("r3", "2024-01-09T12:00:00Z", 1.8, {
        zscorestats: zstats({ is_step: true }),
      }),
    ]);
    render(TrendPage, {
      props: { source: RESULT_SOURCE, query: { ...DEFAULT_TREND_QUERY, range: "all" } },
    });

    await waitFor(() => screen.getByRole("heading", { name: "demo-benchmark" }));
    const context = screen.getByRole("region", { name: /trend context/i });
    expect(context.querySelector(".page-header")).not.toBeNull();
    expect(context.querySelector(".summary-line")).not.toBeNull();
    const summary = context.querySelector(".summary-line") as HTMLElement;
    expect(summary.querySelectorAll(".summary-item")).toHaveLength(3);
    expect(context.querySelector(".filter-bar")?.querySelectorAll(".button-pill")).toHaveLength(3);
    expect(within(summary).getByText(/^\d+ points?$/)).toBeInTheDocument();
    expect(within(summary).getByText(/^\d+ outliers?$/)).toBeInTheDocument();
    expect(within(summary).getByText(/^\d+ steps?$/)).toBeInTheDocument();
  });

  it("shows the error state when loading fails", async () => {
    GET.mockResolvedValue({ error: { detail: "boom" } });
    render(TrendPage, { props: { source: RESULT_SOURCE, query: DEFAULT_TREND_QUERY } });
    await waitFor(() => expect(screen.getByText(/failed to load/i)).toBeInTheDocument());
  });

  it("shows the no-history state for an empty series", async () => {
    mockResultEntry([]);
    render(TrendPage, { props: { source: RESULT_SOURCE, query: DEFAULT_TREND_QUERY } });
    await waitFor(() =>
      expect(screen.getByText(/no default-branch history/i)).toBeInTheDocument(),
    );
  });

  it("anchors the default range at the newest series result instead of wall-clock today", async () => {
    mockResultEntry([sample("r1", "2024-01-07T12:00:00Z")]);
    render(TrendPage, { props: { source: RESULT_SOURCE, query: DEFAULT_TREND_QUERY } });
    await waitFor(() => expect(screen.getByText(/^1 point$/i)).toBeInTheDocument());
    expect(screen.queryByText(/no points in the last/i)).not.toBeInTheDocument();
  });

  it("writes control changes to the URL, preserving the entry path", async () => {
    mockResultEntry([sample("r1", "2024-01-07T12:00:00Z")]);
    render(TrendPage, {
      props: { source: RESULT_SOURCE, query: { ...DEFAULT_TREND_QUERY, range: "all" } },
    });
    await waitFor(() => screen.getByLabelText(/band/i));
    await fireEvent.change(screen.getByLabelText(/band/i), { target: { value: "5" } });
    expect(window.location.pathname).toBe("/benchmarks/history/r1");
    expect(window.location.search).toBe("?range=all&sigma=5");
  });

  it("selects a point from the table and offers Open result", async () => {
    mockResultEntry([
      sample("r1", "2024-01-07T12:00:00Z"),
      sample("r2", "2024-01-08T12:00:00Z"),
    ]);
    render(TrendPage, {
      props: { source: RESULT_SOURCE, query: { ...DEFAULT_TREND_QUERY, range: "all" } },
    });
    await waitFor(() => screen.getByRole("link", { name: "sha-r2" }));
    await fireEvent.click(screen.getByRole("link", { name: "sha-r2" }).closest("tr")!);
    const strip = screen.getByText(/selected/i).closest("div");
    expect(strip).not.toBeNull();
    expect(screen.getByRole("link", { name: /open result/i })).toHaveAttribute(
      "href",
      "/results/r2",
    );
  });

  it("renders a capped history table with progressive reveal", async () => {
    mockResultEntry(manySamples(250));
    render(TrendPage, {
      props: { source: RESULT_SOURCE, query: { ...DEFAULT_TREND_QUERY, range: "all" } },
    });

    await waitFor(() => screen.getByText(/showing 200 of 250 points/i));
    expect(screen.queryByText("sha-r0")).not.toBeInTheDocument();
    expect(screen.getByText("sha-r249")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: /show more/i }));
    expect(screen.getByText(/showing 250 of 250 points/i)).toBeInTheDocument();
    expect(screen.getByText("sha-r0")).toBeInTheDocument();
  });

  it("summarizes and filters flagged points before applying the history cap", async () => {
    const samples = Array.from({ length: 250 }, (_, i) =>
      sample(`r${i}`, new Date(Date.UTC(2024, 0, i + 1, 12)).toISOString(), i + 1),
    );
    samples[10] = sample("r10", "2024-01-11T12:00:00Z", 10, {
      zscorestats: zstats({ is_outlier: true, residual: 0.3, rolling_stddev: 0.1 }),
    });
    samples[12] = sample("r12", "2024-01-13T12:00:00Z", 12, {
      zscorestats: zstats({ is_step: true }),
    });
    mockResultEntry(samples);
    render(TrendPage, {
      props: { source: RESULT_SOURCE, query: { ...DEFAULT_TREND_QUERY, range: "all" } },
    });

    await waitFor(() => screen.getByText(/^250 points$/i));
    const summary = screen.getByLabelText(/trend summary/i);
    expect(within(summary).getByText(/^1 outlier$/i)).toBeInTheDocument();
    expect(within(summary).getByText(/^1 step$/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "sha-r10" })).not.toBeInTheDocument();
    const shortcuts = screen.getByRole("region", { name: /flagged point shortcuts/i });
    expect(within(shortcuts).getByRole("button", { name: /jump to first outlier/i })).toBeInTheDocument();
    expect(within(shortcuts).getByRole("button", { name: /jump to first step/i })).toBeInTheDocument();

    await fireEvent.click(within(shortcuts).getByRole("button", { name: /jump to first outlier/i }));
    expect(screen.getByText(/showing 1 of 1 filtered points/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "sha-r10" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /selected point/i })).toHaveTextContent("sha-r10");

    await fireEvent.click(screen.getByRole("button", { name: /outliers 1/i }));
    expect(screen.getByText(/showing 1 of 1 filtered points/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "sha-r10" })).toBeInTheDocument();
    expect(screen.queryByText("sha-r249")).not.toBeInTheDocument();
  });

  it("keeps trend identity, filters, and compare state in one sticky context", async () => {
    mockResultEntry([
      sample("r1", "2024-01-07T12:00:00Z"),
      sample("r2", "2024-01-08T12:00:00Z"),
    ]);
    render(TrendPage, {
      props: { source: RESULT_SOURCE, query: { ...DEFAULT_TREND_QUERY, range: "all" } },
    });

    await waitFor(() => screen.getByRole("heading", { name: "demo-benchmark" }));
    expect(screen.getByRole("main")).toHaveClass("trend-page");
    const context = screen.getByRole("region", { name: /trend context/i });
    expect(context).toHaveClass("trend-context");
    expect(within(context).getByRole("heading", { name: "demo-benchmark" })).toBeInTheDocument();
    expect(within(context).getByLabelText(/range/i)).toHaveValue("all");
    expect(within(context).getByRole("button", { name: /all 2/i })).toBeInTheDocument();

    await fireEvent.click(screen.getByText("sha-r1").closest("tr")!);
    await fireEvent.click(screen.getByRole("button", { name: "set baseline" }));
    expect(within(context).getByText(/baseline: sha-r1/i)).toBeInTheDocument();
    expect(within(context).getByText(/pick both points to compare/i)).toBeInTheDocument();
  });

  it("renders a selected-point inspector with compare and history export actions", async () => {
    mockResultEntry([
      sample("r1", "2024-01-07T12:00:00Z"),
      sample("r2", "2024-01-08T12:00:00Z", 1.4, {
        zscorestats: zstats({ is_outlier: true, residual: 0.3, rolling_stddev: 0.1 }),
      }),
    ]);
    render(TrendPage, {
      props: {
        source: RESULT_SOURCE,
        query: { ...DEFAULT_TREND_QUERY, range: "all" },
        baseUrl: "https://conbench.example",
      },
    });

    await waitFor(() => screen.getByRole("link", { name: "sha-r2" }));
    await fireEvent.click(screen.getByRole("link", { name: "sha-r2" }).closest("tr")!);

    const inspector = screen.getByRole("region", { name: /selected point/i });
    expect(within(inspector).getByText("sha-r2")).toBeInTheDocument();
    expect(within(inspector).getByText("r2")).toBeInTheDocument();
    expect(within(inspector).getByText(/z 3\.00/i)).toBeInTheDocument();
    expect(within(inspector).getByText("outlier")).toBeInTheDocument();
    expect(within(inspector).getByRole("link", { name: /open result/i })).toHaveAttribute(
      "href",
      "/results/r2",
    );
    expect(within(inspector).getByRole("button", { name: "set baseline" })).toBeInTheDocument();
    expect(within(inspector).getByRole("button", { name: "set contender" })).toBeInTheDocument();

    const exportPanel = screen.getByRole("region", { name: /history export/i });
    expect(exportPanel).toHaveTextContent(
      "conbench history export r2 --server https://conbench.example --output history.csv",
    );
    expect(
      within(exportPanel).getByRole("button", { name: /copy export command/i }),
    ).toBeInTheDocument();
  });

  it("resets the copied export state when the selected point changes", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    mockResultEntry([
      sample("r1", "2024-01-07T12:00:00Z"),
      sample("r2", "2024-01-08T12:00:00Z"),
    ]);
    render(TrendPage, {
      props: {
        source: RESULT_SOURCE,
        query: { ...DEFAULT_TREND_QUERY, range: "all" },
        baseUrl: "https://conbench.example",
      },
    });

    await waitFor(() => screen.getByText("sha-r1"));
    await fireEvent.click(screen.getByText("sha-r1").closest("tr")!);
    await fireEvent.click(screen.getByRole("button", { name: /copy export command/i }));
    await waitFor(() => expect(screen.getByText("copied")).toBeInTheDocument());
    expect(writeText).toHaveBeenLastCalledWith(
      "conbench history export r1 --server https://conbench.example --output history.csv",
    );

    await fireEvent.click(screen.getByRole("link", { name: "sha-r2" }).closest("tr")!);
    expect(screen.queryByText("copied")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: /history export/i })).toHaveTextContent(
      "conbench history export r2 --server https://conbench.example --output history.csv",
    );
  });

  it("ignores a stale clipboard completion after the selected point changes", async () => {
    let resolveWrite!: () => void;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveWrite = resolve;
        }),
    );
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    mockResultEntry([
      sample("r1", "2024-01-07T12:00:00Z"),
      sample("r2", "2024-01-08T12:00:00Z"),
    ]);
    render(TrendPage, {
      props: {
        source: RESULT_SOURCE,
        query: { ...DEFAULT_TREND_QUERY, range: "all" },
        baseUrl: "https://conbench.example",
      },
    });

    await waitFor(() => screen.getByText("sha-r1"));
    await fireEvent.click(screen.getByText("sha-r1").closest("tr")!);
    await fireEvent.click(screen.getByRole("button", { name: /copy export command/i }));
    await fireEvent.click(screen.getByRole("link", { name: "sha-r2" }).closest("tr")!);
    expect(screen.queryByText("copied")).not.toBeInTheDocument();

    resolveWrite();
    await Promise.resolve();
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText("copied")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: /history export/i })).toHaveTextContent(
      "conbench history export r2 --server https://conbench.example --output history.csv",
    );
  });

  it("builds a compare link from baseline and contender picks", async () => {
    mockResultEntry([
      sample("r1", "2024-01-07T12:00:00Z"),
      sample("r2", "2024-01-08T12:00:00Z"),
    ]);
    render(TrendPage, {
      props: { source: RESULT_SOURCE, query: { ...DEFAULT_TREND_QUERY, range: "all" } },
    });
    await waitFor(() => screen.getByText("sha-r1"));
    await fireEvent.click(screen.getByText("sha-r1").closest("tr")!);
    await fireEvent.click(screen.getByRole("button", { name: "set baseline" }));
    expect(screen.getByText(/pick both points to compare/i)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("link", { name: "sha-r2" }).closest("tr")!);
    await fireEvent.click(screen.getByRole("button", { name: "set contender" }));
    expect(screen.getByRole("link", { name: "Compare" })).toHaveAttribute(
      "href",
      "/compare?baseline=r1&contender=r2",
    );
  });

  it("clears the compare picks", async () => {
    mockResultEntry([sample("r1", "2024-01-07T12:00:00Z")]);
    render(TrendPage, {
      props: { source: RESULT_SOURCE, query: { ...DEFAULT_TREND_QUERY, range: "all" } },
    });
    await waitFor(() => screen.getByText("sha-r1"));
    await fireEvent.click(screen.getByText("sha-r1").closest("tr")!);
    await fireEvent.click(screen.getByRole("button", { name: "set baseline" }));
    await fireEvent.click(screen.getByRole("button", { name: "clear" }));
    expect(screen.queryByText(/pick both points to compare/i)).not.toBeInTheDocument();
  });

  it("keeps the compare bar across range changes", async () => {
    mockResultEntry([sample("r1", "2024-01-07T12:00:00Z")]);
    const { rerender } = render(TrendPage, {
      props: { source: RESULT_SOURCE, query: { ...DEFAULT_TREND_QUERY, range: "all" } },
    });
    await waitFor(() => screen.getByText("sha-r1"));
    await fireEvent.click(screen.getByText("sha-r1").closest("tr")!);
    await fireEvent.click(screen.getByRole("button", { name: "set baseline" }));
    await rerender({ query: { ...DEFAULT_TREND_QUERY, range: "30d" } });
    expect(screen.queryByText(/no points in the last/i)).not.toBeInTheDocument();
    expect(screen.getByText(/pick both points to compare/i)).toBeInTheDocument();
  });

  it("loads by fingerprint and surfaces the mixed-unit banner", async () => {
    GET.mockImplementation(async (url: string) => {
      if (url === "/api/history") {
        return {
          data: {
            history_fingerprint: "fp1",
            samples: [
              sample("r1", "2024-01-07T12:00:00Z"),
              { ...sample("r2", "2024-01-08T12:00:00Z"), unit: "ms" },
            ],
          },
        };
      }
      if (url === "/api/series") {
        return {
          data: {
            series: [
              {
                history_fingerprint: "fp1",
                name: "demo-benchmark",
                tags: { name: "demo-benchmark" },
                context: {},
                hardware: { id: "h1", type: "machine", name: "m5", hash: "hw1" },
                repository: "https://github.com/conbench/demo",
                unit: null,
                less_is_better: null,
                status: "insufficient",
                latest_result_id: "r2",
                latest_single_value_summary: null,
                latest_single_value_summary_type: null,
                latest_commit_sha: "sha-r2",
                latest_commit_timestamp: "2024-01-08T12:00:00Z",
                latest_result_timestamp: "2024-01-08T12:00:00Z",
                point_count: 2,
                sparkline: null,
              },
            ],
            next_page_cursor: null,
          },
        };
      }
      throw new Error(`unexpected ${url}`);
    });
    window.history.replaceState(null, "", "/series/fp1");
    render(TrendPage, {
      props: {
        source: { kind: "fingerprint", fingerprint: "fp1" },
        query: { ...DEFAULT_TREND_QUERY, range: "all" },
      },
    });
    await waitFor(() => screen.getByRole("heading", { name: "demo-benchmark" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/mixes units/);
  });
});
