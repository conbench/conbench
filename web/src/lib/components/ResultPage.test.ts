import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { components } from "../api/schema";
import ResultPage from "./ResultPage.svelte";

const GET = vi.fn();
const PUT = vi.fn();
const DELETE = vi.fn();
vi.mock("../api/client", () => ({
  createConbenchClient: () => ({ GET, PUT, DELETE }),
}));

type ResultDetail = components["schemas"]["ResultDetail"];

const detail: ResultDetail = {
  id: "r1",
  batch_id: null,
  run_id: "run1",
  run_reason: "commit",
  run_tags: {},
  tags: { name: "demo-benchmark", scale: "sf10" },
  context: { compiler: "gcc" },
  info: { suite: "arrow", benchmark_language: "C++" },
  hardware: { id: "h1", type: "machine", name: "m5", hash: "hw1" },
  commit: {
    id: "c1",
    message: "tune",
    repository: "https://github.com/conbench/demo",
    sha: "abc1234def",
    timestamp: "2024-01-07T12:00:00Z",
  },
  commit_repo_url: "https://github.com/conbench/demo",
  unit: "s",
  less_is_better: true,
  single_value_summary: 1.5,
  single_value_summary_type: "min",
  iterations: 3,
  data: [1.4, 1.5, 1.6],
  times: [0.1, 0.2, 0.3],
  time_unit: "s",
  error: null,
  stats: { min: 1.4, max: 1.6, mean: 1.5, median: 1.5, q1: null, q3: null, stdev: 0.1, iqr: null },
  optional_benchmark_info: { owner: "perf" },
  validation: { success: true, validator: "pandas.testing" },
  change_annotations: { begins_distribution_change: false, note: "checked" },
  history_fingerprint: "fp1",
  timestamp: "2024-01-07T13:00:00Z",
};

const signedInCapabilities = {
  signed_in: true,
  auth_disabled: false,
  can_write_results: true,
};

const readOnlyCapabilities = {
  signed_in: false,
  auth_disabled: false,
  can_write_results: false,
};

const authDisabledCapabilities = {
  signed_in: false,
  auth_disabled: true,
  can_write_results: true,
};

beforeEach(() => {
  GET.mockReset();
  PUT.mockReset();
  DELETE.mockReset();
});

function mockPage(result: ResultDetail = detail, capabilities = readOnlyCapabilities) {
  GET.mockImplementation((path: string) => {
    if (path === "/api/benchmark-results/{id}") {
      return Promise.resolve({ data: result });
    }
    if (path === "/api/auth/capabilities") {
      return Promise.resolve({ data: capabilities });
    }
    return Promise.resolve({ error: { detail: `unexpected GET ${path}` } });
  });
}

describe("ResultPage", () => {
  it("renders identity, measurement, commit, and run sections with a trend link", async () => {
    mockPage();
    render(ResultPage, { props: { resultId: "r1" } });
    await waitFor(() => screen.getByRole("heading", { name: "demo-benchmark" }));
    expect(screen.getByRole("main")).toHaveClass("page");
    expect(screen.getByRole("region", { name: /result measurement/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /result facts/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /result metadata/i })).toBeInTheDocument();
    expect(screen.getByText("scale=sf10")).toBeInTheDocument();
    // SVS, mean, and median all render "1.5 s"; scope to the SVS row so the
    // assertion targets the measured value specifically.
    expect(screen.getByText("SVS (min)").nextElementSibling).toHaveTextContent("1.5 s");
    expect(screen.getByText("sha").nextElementSibling).toHaveTextContent("abc1234d");
    expect(screen.getByText("sha").nextElementSibling).toHaveAttribute("title", "abc1234def");
    expect(screen.getByText("run1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view trend/i })).toHaveAttribute(
      "href",
      "/benchmarks/history/r1",
    );
    expect(screen.getByRole("link", { name: /export history json/i })).toHaveAttribute("href", "/api/history/r1");
    expect(screen.getByText("hardware hash").nextElementSibling).toHaveTextContent("hw1");
    expect(screen.getByText("less is better").nextElementSibling).toHaveTextContent("true");
    expect(screen.getByText("raw data").nextElementSibling).toHaveTextContent("3 values");
    expect(screen.getByText("raw times").nextElementSibling).toHaveTextContent("3 values");
    expect(screen.getAllByText(/"suite": "arrow"/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/"owner": "perf"/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/"validator": "pandas.testing"/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/"note": "checked"/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/"data": \[/).length).toBeGreaterThan(0);
  });

  it("does not show write actions to signed-out viewers", async () => {
    mockPage();

    render(ResultPage, { props: { resultId: "r1" } });
    await waitFor(() => screen.getByRole("heading", { name: "demo-benchmark" }));

    expect(screen.queryByRole("button", { name: /mark distribution change/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /delete result/i })).toBeNull();
  });

  it("shows write actions when auth-disabled dev mode allows result writes", async () => {
    mockPage(detail, authDisabledCapabilities);

    render(ResultPage, { props: { resultId: "r1" } });
    await waitFor(() => screen.getByRole("heading", { name: "demo-benchmark" }));

    expect(screen.getByRole("button", { name: /mark distribution change/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /delete result/i })).toBeInTheDocument();
  });

  it("marks and unmarks a result as a distribution change", async () => {
    mockPage({ ...detail, change_annotations: {} }, signedInCapabilities);
    PUT.mockResolvedValueOnce({ data: { ...detail, change_annotations: { begins_distribution_change: true } } });
    PUT.mockResolvedValueOnce({ data: { ...detail, change_annotations: {} } });

    render(ResultPage, { props: { resultId: "r1" } });
    await waitFor(() => screen.getByRole("heading", { name: "demo-benchmark" }));

    await fireEvent.click(screen.getByRole("button", { name: /mark distribution change/i }));
    await waitFor(() =>
      expect(PUT).toHaveBeenCalledWith("/api/benchmark-results/{id}", {
        params: { path: { id: "r1" } },
        body: { change_annotations: { begins_distribution_change: true } },
      }),
    );
    expect(screen.getByText(/annotation updated/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /unmark distribution change/i })).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: /unmark distribution change/i }));
    await waitFor(() =>
      expect(PUT).toHaveBeenLastCalledWith("/api/benchmark-results/{id}", {
        params: { path: { id: "r1" } },
        body: { change_annotations: { begins_distribution_change: null } },
      }),
    );
    expect(screen.getByRole("button", { name: /mark distribution change/i })).toBeInTheDocument();
  });

  it("deletes a result after confirmation", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    mockPage(detail, signedInCapabilities);
    DELETE.mockResolvedValueOnce({ response: { status: 204 } });

    render(ResultPage, { props: { resultId: "r1" } });
    await waitFor(() => screen.getByRole("heading", { name: "demo-benchmark" }));

    await fireEvent.click(screen.getByRole("button", { name: /delete result/i }));
    expect(confirm).toHaveBeenCalledWith("Delete result r1?");
    await waitFor(() =>
      expect(DELETE).toHaveBeenCalledWith("/api/benchmark-results/{id}", {
        params: { path: { id: "r1" } },
      }),
    );
    expect(screen.getByRole("heading", { name: /result deleted/i })).toBeInTheDocument();
    confirm.mockRestore();
  });

  it("shows the error payload for an errored result", async () => {
    mockPage({ ...detail, single_value_summary: null, error: { stack: "trace" } });
    render(ResultPage, { props: { resultId: "r1" } });
    await waitFor(() => screen.getByRole("heading", { name: "demo-benchmark" }));
    expect(screen.getByText("SVS (min)").nextElementSibling).toHaveTextContent("—");
    expect(screen.getAllByText(/"stack"/).length).toBeGreaterThan(0);
  });

  it("shows the error state when loading fails", async () => {
    GET.mockImplementation((path: string) => {
      if (path === "/api/auth/capabilities") {
        return Promise.resolve({ data: readOnlyCapabilities });
      }
      return Promise.resolve({ error: { detail: "boom" } });
    });
    render(ResultPage, { props: { resultId: "rX" } });
    await waitFor(() => expect(screen.getByText(/failed to load/i)).toBeInTheDocument());
  });
});
