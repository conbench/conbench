import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BatchPage from "./BatchPage.svelte";

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
  case_name: "tpch",
  case_tags: {
    query_id: "TPCH-09",
    scale_factor: 1,
    format: "parquet",
    language: "R",
  },
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
  window.history.replaceState(null, "", "/batches/batch-a");
});

describe("BatchPage", () => {
  it("renders batch metadata, grouped run summaries, result rows, and investigation links", async () => {
    GET.mockResolvedValueOnce({
      data: {
        results: [
          result("r3", { run_id: "run-b", has_error: true }),
          result("r2", { run_id: "run-a" }),
          result("r1", { run_id: "run-a" }),
        ],
        next_page_cursor: null,
      },
    });

    render(BatchPage, { props: { batchId: "batch-a" } });

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("heading", { name: /batch batch-a/i })).toBeInTheDocument());
    expect(screen.getByText(/^3 results$/i)).toBeInTheDocument();
    expect(screen.getByText(/^2 runs$/i)).toBeInTheDocument();
    expect(screen.getByText(/^1 error$/i)).toBeInTheDocument();
    expect(screen.getByText("3 series")).toBeInTheDocument();
    expect(screen.getAllByText("abcdef12").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /run-b/i })[0]).toHaveAttribute("href", "/runs/run-b");
    expect(screen.getByRole("link", { name: "Open CI report for run run-b" })).toHaveAttribute(
      "href",
      "/ci/report?repository=https%3A%2F%2Fgithub.com%2Fapache%2Farrow&commit_sha=abcdef123456&run_ids=run-b&baseline=fork_point",
    );
    expect(screen.getAllByRole("link", { name: /tpch/i })[0]).toHaveAttribute("href", "/results/r3");
    expect(screen.getAllByText("query_id TPCH-09").length).toBeGreaterThan(0);
    expect(screen.getAllByText("format parquet").length).toBeGreaterThan(0);
    expect(screen.getByText("result r3")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /trend for tpch result r3/i })).toHaveAttribute(
      "href",
      "/series/fp-r3",
    );
  });

  it("loads more results, appends them, and preserves the first page context", async () => {
    GET.mockResolvedValueOnce({ data: { results: [result("r1")], next_page_cursor: "cur2" } });
    GET.mockResolvedValueOnce({
      data: {
        results: [
          result("r2", {
            run_id: "run-b",
            commit: {
              hash: "999999991111",
              repository: "https://github.com/example/other",
              timestamp: "2026-01-03T00:00:00Z",
            },
          }),
        ],
        next_page_cursor: null,
      },
    });

    render(BatchPage, { props: { batchId: "batch-a" } });
    await waitFor(() => screen.getByText("result r1"));

    await fireEvent.click(screen.getByRole("button", { name: /load more/i }));
    await waitFor(() => expect(screen.getByText("result r2")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /load more/i })).toBeNull();
    const batchContext = screen.getByText("repository").closest("section");
    expect(batchContext).not.toBeNull();
    expect(within(batchContext!).getByText("https://github.com/apache/arrow")).toBeInTheDocument();
    expect(within(batchContext!).getByText("abcdef123456")).toBeInTheDocument();
    expect(within(batchContext!).queryByText("https://github.com/example/other")).toBeNull();
    expect(within(batchContext!).queryByText("999999991111")).toBeNull();
    expect(screen.getAllByText("abcdef12").length).toBeGreaterThan(0);
    const runGroups = screen.getByRole("region", { name: /runs in batch/i });
    expect(within(runGroups).getByRole("link", { name: /^open run run-a$/i })).toHaveAttribute("href", "/runs/run-a");
    expect(within(runGroups).getByRole("link", { name: /^open run run-b$/i })).toHaveAttribute("href", "/runs/run-b");
    expect(GET).toHaveBeenLastCalledWith("/api/benchmark-results", {
      params: { query: { batch_id: "batch-a", page_size: 100, cursor: "cur2" } },
    });
  });

  it("deduplicates run-group series counts across appended pages", async () => {
    GET.mockResolvedValueOnce({
      data: {
        results: [
          result("r1", {
            history_fingerprint: "fp-shared",
            timestamp: "2026-01-02T00:00:00Z",
          }),
        ],
        next_page_cursor: "cur2",
      },
    });
    GET.mockResolvedValueOnce({
      data: {
        results: [
          result("r2", {
            history_fingerprint: "fp-shared",
            timestamp: "2026-01-02T00:01:00Z",
          }),
        ],
        next_page_cursor: null,
      },
    });

    render(BatchPage, { props: { batchId: "batch-a" } });
    await waitFor(() => screen.getByText("result r1"));

    await fireEvent.click(screen.getByRole("button", { name: /load more/i }));
    await waitFor(() => expect(screen.getByText("result r2")).toBeInTheDocument());

    const runGroups = screen.getByRole("region", { name: /runs in batch/i });
    expect(within(runGroups).getByRole("row", { name: /run-a nightly abcdef12 2 1 0/i })).toBeInTheDocument();
    expect(screen.getByText("1 series")).toBeInTheDocument();
  });

  it("shows empty and error states", async () => {
    GET.mockResolvedValueOnce({ data: { results: [], next_page_cursor: null } });
    const { unmount } = render(BatchPage, { props: { batchId: "batch-a" } });
    await waitFor(() => expect(screen.getByText(/no results found for this batch/i)).toBeInTheDocument());
    unmount();

    GET.mockResolvedValueOnce({ error: { detail: "statement timeout" } });
    render(BatchPage, { props: { batchId: "batch-a" } });
    await waitFor(() => expect(screen.getByText(/failed to load batch/i)).toBeInTheDocument());
    expect(screen.getByText(/statement timeout/i)).toBeInTheDocument();
  });
});
