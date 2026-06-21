import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CIReportPage from "./CIReportPage.svelte";

const GET = vi.fn();
vi.mock("../api/client", () => ({
  createConbenchClient: () => ({ GET }),
}));

const QUERY = {
  repository: "https://github.com/conbench/demo",
  commit: "c4",
  runIDs: "ci-run",
  baselineRunIDs: "",
  baseline: "fork_point" as const,
  threshold: "",
  thresholdZ: "",
};

const report = {
  repository: "https://github.com/conbench/demo",
  commit_sha: "c4",
  selected_run_ids: ["ci-run"],
  missing_run_ids: [],
  baseline: "fork_point",
  status: "failure",
  status_reason: "lookback regression detected",
  threshold: 5,
  threshold_z: 5,
  report_url: "https://conbench.example/ci/report?commit_sha=c4",
  summary: {
    runs: 1,
    missing_runs: 0,
    contender_results: 1,
    compared: 1,
    analyzed: 1,
    regressions: 1,
    improvements: 0,
    benchmark_errors: 0,
    missing_baseline: 0,
    not_comparable: 0,
  },
  runs: [
    {
      run_id: "ci-run",
      run_reason: "commit",
      run_tags: {},
      commit: { id: "c4-id", sha: "c4", repository: "https://github.com/conbench/demo", message: "", timestamp: "2024-01-04T12:00:00Z" },
      baseline_run_id: "main-run",
      baseline_commit: { id: "c3-id", sha: "c3", repository: "https://github.com/conbench/demo", message: "", timestamp: "2024-01-03T12:00:00Z" },
      commits_skipped: [],
      baseline_error: null,
      comparisons: [
        {
          status: "regressed",
          name: "demo-bench",
          tags: { name: "demo-bench" },
          context: { compiler: "gcc" },
          info: {},
          hardware: { id: "hw1", type: "machine", name: "m5", hash: "hash" },
          history_fingerprint: "fp1",
          unit: "s",
          less_is_better: true,
          contender: {
            result_id: "contender-id",
            run_id: "ci-run",
            result_timestamp: "2024-01-04T12:30:00Z",
            commit_sha: "c4",
            commit_timestamp: "2024-01-04T12:00:00Z",
            error: null,
            single_value_summary: 100,
            single_value_summary_type: "min",
          },
          baseline: {
            result_id: "baseline-id",
            run_id: "main-run",
            result_timestamp: "2024-01-03T12:30:00Z",
            commit_sha: "c3",
            commit_timestamp: "2024-01-03T12:00:00Z",
            single_value_summary: 30,
            single_value_summary_type: "min",
          },
          analysis: {
            pairwise: {
              percent_change: -233.3,
              percent_threshold: 5,
              regression_indicated: true,
              improvement_indicated: false,
            },
            lookback_z_score: {
              z_score: -10.47,
              z_threshold: 5,
              regression_indicated: true,
              improvement_indicated: false,
            },
          },
          error: null,
          links: {
            result: "/results/contender-id",
            compare: "/compare?baseline=baseline-id&contender=contender-id",
            series: "/series/fp1",
          },
        },
      ],
    },
  ],
};

function comparison(overrides: Record<string, unknown> = {}) {
  const baseRun = report.runs[0];
  const baseComparison = baseRun?.comparisons[0];
  if (!baseRun || !baseComparison) {
    throw new Error("CI report fixture must contain one run with one comparison");
  }
  return {
    ...baseComparison,
    ...overrides,
  };
}

function withMixedComparisons() {
  const baseRun = report.runs[0];
  const baseComparison = baseRun?.comparisons[0];
  if (!baseRun || !baseComparison) {
    throw new Error("CI report fixture must contain one run with one comparison");
  }
  const contender = baseComparison.contender;
  return {
    ...report,
    summary: {
      ...report.summary,
      contender_results: 4,
      compared: 2,
      analyzed: 2,
      regressions: 1,
      benchmark_errors: 1,
      missing_baseline: 1,
      not_comparable: 0,
    },
    runs: [
      {
        ...baseRun,
        comparisons: [
          comparison({
            status: "regressed",
            name: "regress-bench",
            history_fingerprint: "fp-regressed",
            hardware: { id: "hw1", type: "machine", name: "m5", hash: "hash1" },
            contender: { ...contender, result_id: "contender-regressed" },
            links: { result: "/results/contender-regressed", compare: "/compare?baseline=b&contender=r", series: "/series/fp-regressed" },
          }),
          comparison({
            status: "stable",
            name: "stable-bench",
            history_fingerprint: "fp-stable",
            hardware: { id: "hw2", type: "machine", name: "c6", hash: "hash2" },
            contender: { ...contender, result_id: "contender-stable" },
            links: { result: "/results/contender-stable", compare: "/compare?baseline=b&contender=s", series: "/series/fp-stable" },
          }),
          comparison({
            status: "errored",
            name: "errored-bench",
            history_fingerprint: "fp-errored",
            hardware: { id: "hw1", type: "machine", name: "m5", hash: "hash1" },
            contender: { ...contender, result_id: "contender-errored", error: { message: "benchmark failed" } },
            links: { result: "/results/contender-errored", series: "/series/fp-errored" },
          }),
          comparison({
            status: "missing_baseline",
            name: "missing-bench",
            history_fingerprint: "fp-missing",
            hardware: { id: "hw3", type: "machine", name: "m6", hash: "hash3" },
            baseline: null,
            contender: { ...contender, result_id: "contender-missing" },
            reason: "no matching baseline result",
            links: { result: "/results/contender-missing", series: "/series/fp-missing" },
          }),
        ],
      },
    ],
  };
}

function withComparisons(count: number, runID = "ci-run") {
  const baseRun = report.runs[0];
  const baseComparison = baseRun?.comparisons[0];
  if (!baseRun || !baseComparison) {
    throw new Error("CI report fixture must contain one run with one comparison");
  }

  return {
    ...report,
    summary: { ...report.summary, contender_results: count, missing_baseline: count },
    runs: [
      {
        ...baseRun,
        run_id: runID,
        comparisons: Array.from({ length: count }, (_, i) => ({
          ...baseComparison,
          name: `bench-${i}`,
          history_fingerprint: `fp-${i}`,
          contender: {
            ...baseComparison.contender,
            result_id: `contender-${i}`,
          },
          links: {
            ...baseComparison.links,
            result: `/results/contender-${i}`,
            series: `/series/fp-${i}`,
          },
        })),
      },
    ],
  };
}

function withLateRegression(count: number, index: number) {
  const baseRun = report.runs[0];
  const baseComparison = baseRun?.comparisons[0];
  if (!baseRun || !baseComparison) {
    throw new Error("CI report fixture must contain one run with one comparison");
  }
  return {
    ...report,
    summary: { ...report.summary, contender_results: count, regressions: 1 },
    runs: [
      {
        ...baseRun,
        comparisons: Array.from({ length: count }, (_, i) => ({
          ...baseComparison,
          status: i === index ? "regressed" : "stable",
          name: `bench-${i}`,
          history_fingerprint: `fp-${i}`,
          contender: {
            ...baseComparison.contender,
            result_id: `contender-${i}`,
          },
          links: {
            ...baseComparison.links,
            result: `/results/contender-${i}`,
            series: `/series/fp-${i}`,
          },
        })),
      },
    ],
  };
}

beforeEach(() => {
  GET.mockReset();
});

describe("CIReportPage", () => {
  it("does not call the API without a selector", () => {
    render(CIReportPage, {
      props: {
        query: { repository: "", commit: "", runIDs: "", baselineRunIDs: "", baseline: "", threshold: "", thresholdZ: "" },
      },
    });
    expect(screen.getByText(/open a ci report url/i)).toBeInTheDocument();
    expect(GET).not.toHaveBeenCalled();
  });

  it("renders report status, summary, rows, and links", async () => {
    GET.mockResolvedValue({ data: report });
    render(CIReportPage, { props: { query: QUERY } });
    await waitFor(() => screen.getByText("failure"));

    expect(screen.getByText("lookback regression detected")).toBeInTheDocument();
    expect(screen.getAllByText("demo-bench").length).toBeGreaterThan(0);
    expect(screen.getByText("ci-run")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "result" })).toHaveAttribute("href", "/results/contender-id");
    expect(screen.getByRole("link", { name: "compare" })).toHaveAttribute(
      "href",
      "/compare?baseline=baseline-id&contender=contender-id",
    );
    expect(GET).toHaveBeenCalledWith("/api/ci/report", {
      params: { query: { repository: QUERY.repository, commit_sha: "c4", run_ids: "ci-run", baseline: "fork_point" } },
    });
  });

  it("renders investigation controls, issue jumps, and grouped summaries", async () => {
    GET.mockResolvedValue({ data: withMixedComparisons() });
    render(CIReportPage, { props: { query: QUERY } });

    await waitFor(() => screen.getByRole("button", { name: /all 4/i }));

    expect(screen.getByLabelText(/search comparisons/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/hardware/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /regressed 1/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /errored 1/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /missing baseline 1/i })).toBeInTheDocument();
    const queue = screen.getByRole("region", { name: /investigation queue/i });
    expect(within(queue).getByText(/3 actionable comparisons/i)).toBeInTheDocument();
    expect(within(queue).getByText("regress-bench")).toBeInTheDocument();
    expect(within(queue).getByText("errored-bench")).toBeInTheDocument();
    expect(within(queue).getByText("missing-bench")).toBeInTheDocument();
    expect(within(queue).getAllByText(/delta -233\.3% · z -10\.47/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /jump to regressed/i })).toHaveAttribute(
      "href",
      "#ci-row-regressed-ci-run-fp-regressed",
    );
    expect(screen.getByRole("link", { name: /jump to errored/i })).toHaveAttribute(
      "href",
      "#ci-row-errored-ci-run-fp-errored",
    );
    expect(screen.getByRole("link", { name: /jump to missing baseline/i })).toHaveAttribute(
      "href",
      "#ci-row-missing-baseline-ci-run-fp-missing",
    );
    expect(screen.getAllByText(/4 matching comparisons/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/1 regressed/i)).toBeInTheDocument();
    expect(screen.getByText(/1 benchmark error/i)).toBeInTheDocument();
    expect(screen.getByText(/1 missing baseline/i)).toBeInTheDocument();
  });

  it("filters comparisons by status, hardware, and search text", async () => {
    GET.mockResolvedValue({ data: withMixedComparisons() });
    render(CIReportPage, { props: { query: QUERY } });
    await waitFor(() => screen.getAllByText("regress-bench"));

    await fireEvent.click(screen.getByRole("button", { name: /errored 1/i }));
    expect(screen.getAllByText("errored-bench").length).toBeGreaterThan(0);
    expect(screen.queryByText("regress-bench")).toBeNull();
    expect(screen.queryByText("stable-bench")).toBeNull();

    await fireEvent.click(screen.getByRole("button", { name: /all 4/i }));
    await fireEvent.change(screen.getByLabelText(/hardware/i), { target: { value: "m6" } });
    expect(screen.getAllByText("missing-bench").length).toBeGreaterThan(0);
    expect(screen.queryByText("errored-bench")).toBeNull();

    await fireEvent.change(screen.getByLabelText(/hardware/i), { target: { value: "all" } });
    await fireEvent.input(screen.getByLabelText(/search comparisons/i), { target: { value: "stable" } });
    expect(screen.getAllByText("stable-bench").length).toBeGreaterThan(0);
    expect(screen.queryByText("missing-bench")).toBeNull();
  });

  it("passes explicit baseline run IDs to the API", async () => {
    GET.mockResolvedValue({ data: { ...report, baseline: "explicit_run" } });
    render(CIReportPage, { props: { query: { ...QUERY, baseline: "", baselineRunIDs: "main-run" } } });
    await waitFor(() => screen.getByText("failure"));

    expect(GET).toHaveBeenCalledWith("/api/ci/report", {
      params: { query: { repository: QUERY.repository, commit_sha: "c4", run_ids: "ci-run", baseline_run_ids: "main-run" } },
    });
  });

  it("wraps the comparison table for responsive layouts", async () => {
    GET.mockResolvedValue({ data: report });
    const { container } = render(CIReportPage, { props: { query: QUERY } });
    await waitFor(() => screen.getAllByText("demo-bench"));
    expect(container.querySelector(".comparison-list > table.comparisons")).not.toBeNull();
  });

  it("renders the error state when loading fails", async () => {
    GET.mockResolvedValue({ error: { detail: "bad selector" }, response: { status: 422 } });
    render(CIReportPage, { props: { query: QUERY } });
    await waitFor(() => expect(screen.getByText(/bad selector/)).toBeInTheDocument());
  });

  it("renders comparison rows progressively per run", async () => {
    GET.mockResolvedValue({ data: withComparisons(250) });
    render(CIReportPage, { props: { query: QUERY } });

    await waitFor(() => screen.getByText(/showing 200 of 250 comparisons/i));
    expect(screen.getByText("bench-199")).toBeInTheDocument();
    expect(screen.queryByText("bench-200")).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: /show more/i }));
    expect(screen.getByText(/showing 250 of 250 comparisons/i)).toBeInTheDocument();
    expect(screen.getAllByText("bench-249").length).toBeGreaterThan(0);
  });

  it("filters before applying row chunk limits", async () => {
    GET.mockResolvedValue({ data: withComparisons(250) });
    render(CIReportPage, { props: { query: QUERY } });

    await waitFor(() => screen.getByText(/showing 200 of 250 comparisons/i));
    expect(screen.queryByText("bench-249")).not.toBeInTheDocument();

    await fireEvent.input(screen.getByLabelText(/search comparisons/i), { target: { value: "bench-249" } });

    expect(screen.getByText(/showing 1 of 1 matching comparisons/i)).toBeInTheDocument();
    expect(screen.getAllByText("bench-249").length).toBeGreaterThan(0);
    expect(screen.queryByText("bench-199")).not.toBeInTheDocument();
  });

  it("expands a run before jumping to an issue past the rendered row cap", async () => {
    GET.mockResolvedValue({ data: withLateRegression(250, 240) });
    render(CIReportPage, { props: { query: QUERY } });

    await waitFor(() => screen.getByText(/showing 200 of 250 comparisons/i));
    expect(document.getElementById("ci-row-regressed-ci-run-fp-240")).toBeNull();

    await fireEvent.click(screen.getByRole("link", { name: /jump to regressed/i }));

    await waitFor(() => expect(document.getElementById("ci-row-regressed-ci-run-fp-240")).not.toBeNull());
    expect(window.location.hash).toBe("#ci-row-regressed-ci-run-fp-240");
  });

  it("uses the default row limit for run IDs that match object prototype keys", async () => {
    GET.mockResolvedValue({ data: withComparisons(250, "constructor") });
    render(CIReportPage, { props: { query: QUERY } });

    await waitFor(() => screen.getByText(/showing 200 of 250 comparisons/i));
    expect(screen.getByText("bench-199")).toBeInTheDocument();
    expect(screen.queryByText("bench-200")).not.toBeInTheDocument();
  });
});
