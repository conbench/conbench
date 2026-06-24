import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_RESULT_LIST_QUERY } from "../router";
import ResultsPage from "./ResultsPage.svelte";

const GET = vi.fn();
vi.mock("../api/client", () => ({
  createConbenchClient: () => ({ GET }),
}));

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

beforeEach(() => {
  GET.mockReset();
  window.history.replaceState(null, "", "/results");
});

describe("ResultsPage", () => {
  it("renders recent benchmark results with investigation links", async () => {
    GET.mockResolvedValueOnce({
      data: {
        results: [
          result("r2", { run_id: "run-b", batch_id: null, has_error: true }),
          result("r1"),
        ],
        next_page_cursor: "cur2",
      },
    });

    const { container } = render(ResultsPage, { props: { query: DEFAULT_RESULT_LIST_QUERY } });

    await waitFor(() => screen.getByRole("heading", { name: /benchmark results/i }));
    expect(screen.getAllByText(/2 results\+?/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/^2 runs$/i)).toBeInTheDocument();
    expect(screen.getByText(/^1 error$/i)).toBeInTheDocument();
    expect(container.querySelector(".filter-bar.panel.results-filters")).not.toBeNull();
    expect(container.querySelector("table.data-table.stacked-table.results-table")).not.toBeNull();
    expect(screen.getByRole("link", { name: "r2" })).toHaveAttribute("href", "/results/r2");
    expect(screen.getByRole("link", { name: "run-b" })).toHaveAttribute("href", "/runs/run-b");
    expect(screen.getByRole("link", { name: "batch-a" })).toHaveAttribute("href", "/batches/batch-a");
    expect(screen.getByRole("link", { name: /trend for r2/i })).toHaveAttribute("href", "/series/fp-r2");
    expect(screen.getAllByText("https://github.com/apache/arrow").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /load more/i })).toBeInTheDocument();
  });

  it("loads and appends the next page", async () => {
    GET.mockResolvedValueOnce({ data: { results: [result("r1")], next_page_cursor: "cur2" } });
    GET.mockResolvedValueOnce({ data: { results: [result("r2")], next_page_cursor: null } });

    render(ResultsPage, { props: { query: DEFAULT_RESULT_LIST_QUERY } });
    await waitFor(() => screen.getByRole("link", { name: "r1" }));

    await fireEvent.click(screen.getByRole("button", { name: /load more/i }));
    await waitFor(() => expect(screen.getByRole("link", { name: "r2" })).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /load more/i })).toBeNull();
    const secondCall = GET.mock.calls[1]![1] as { params: { query: { cursor?: string } } };
    expect(secondCall.params.query.cursor).toBe("cur2");
  });

  it("navigates with result list filters", async () => {
    GET.mockResolvedValueOnce({ data: { results: [], next_page_cursor: null } });
    render(ResultsPage, { props: { query: DEFAULT_RESULT_LIST_QUERY } });
    await waitFor(() => screen.getByText(/no benchmark results match/i));

    await fireEvent.input(screen.getByLabelText(/run id/i), { target: { value: "run-a " } });
    await fireEvent.input(screen.getByLabelText(/run reason/i), { target: { value: "nightly" } });
    await fireEvent.submit(screen.getByRole("button", { name: /apply filters/i }).closest("form")!);

    expect(window.location.pathname).toBe("/results");
    expect(window.location.search).toBe("?run_id=run-a&run_reason=nightly");
  });

  it("shows active result filters with clearable deep-link hrefs", async () => {
    GET.mockResolvedValueOnce({ data: { results: [], next_page_cursor: null } });
    render(ResultsPage, {
      props: {
        query: {
          ...DEFAULT_RESULT_LIST_QUERY,
          runID: "run-a",
          batchID: "batch-a",
          runReason: "nightly",
        },
      },
    });

    await waitFor(() => screen.getByText(/no benchmark results match/i));
    expect(screen.getByRole("link", { name: /clear/i })).toHaveAttribute("href", "/results");
    expect(screen.getByRole("group", { name: /active result filters/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /remove run id filter run-a/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /remove batch id filter batch-a/i })).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: /remove run id filter run-a/i }));

    expect(window.location.pathname).toBe("/results");
    const params = new URLSearchParams(window.location.search);
    expect(params.get("run_id")).toBeNull();
    expect(params.get("batch_id")).toBe("batch-a");
    expect(params.get("run_reason")).toBe("nightly");
  });

  it("shows endpoint errors", async () => {
    GET.mockResolvedValueOnce({ error: { detail: "statement timeout" } });
    render(ResultsPage, { props: { query: DEFAULT_RESULT_LIST_QUERY } });
    await waitFor(() => expect(screen.getByText(/failed to load results/i)).toBeInTheDocument());
    expect(screen.getByText(/statement timeout/i)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("statement timeout");
  });

  it("shows a state-panel empty result", async () => {
    GET.mockResolvedValueOnce({ data: { results: [], next_page_cursor: null } });
    render(ResultsPage, { props: { query: DEFAULT_RESULT_LIST_QUERY } });

    const empty = await screen.findByRole("region", { name: /no matching benchmark results/i });
    expect(empty).toHaveClass("state-panel");
    expect(within(empty).getByRole("link", { name: /browse series/i })).toHaveAttribute("href", "/series");
  });
});
