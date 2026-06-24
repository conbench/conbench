import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RunPage from "./RunPage.svelte";

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

const formatTime = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));

beforeEach(() => {
  GET.mockReset();
  window.history.replaceState(null, "", "/runs/run-a");
});

describe("RunPage", () => {
  it("renders run metadata, result rows, and investigation links", async () => {
    GET.mockResolvedValueOnce({
      data: { results: [result("r2", { has_error: true }), result("r1")], next_page_cursor: null },
    });

    render(RunPage, { props: { runId: "run-a" } });

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("heading", { name: /run run-a/i })).toBeInTheDocument());
    expect(screen.getByText(/nightly/i)).toBeInTheDocument();
    expect(screen.getByText(/^2 results\+?$/i)).toBeInTheDocument();
    expect(screen.getByText(/^1 error$/i)).toBeInTheDocument();
    expect(screen.getByText("abcdef12")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open CI report for run run-a" })).toHaveAttribute(
      "href",
      "/ci/report?repository=https%3A%2F%2Fgithub.com%2Fapache%2Farrow&commit_sha=abcdef123456&run_ids=run-a&baseline=fork_point",
    );
    expect(screen.getAllByRole("link", { name: "batch-a" })[0]).toHaveAttribute(
      "href",
      "/batches/batch-a",
    );
    expect(screen.getByRole("link", { name: "r2" })).toHaveAttribute("href", "/results/r2");
    expect(screen.getByRole("link", { name: "Open series trend for result r2" })).toHaveAttribute(
      "href",
      "/series/fp-r2",
    );
  });

  it("loads more results, appends them, and expands the loaded window", async () => {
    GET.mockResolvedValueOnce({ data: { results: [result("r1")], next_page_cursor: "cur2" } });
    GET.mockResolvedValueOnce({
      data: {
        results: [result("r2", { timestamp: "2026-01-03T00:00:00Z" })],
        next_page_cursor: null,
      },
    });

    render(RunPage, { props: { runId: "run-a" } });
    await waitFor(() => screen.getByRole("link", { name: "r1" }));
    const runContext = screen.getByRole("region", { name: /run context/i });
    expect(within(runContext).getAllByText(formatTime("2026-01-02T00:00:00Z"))).toHaveLength(2);

    await fireEvent.click(screen.getByRole("button", { name: /load more/i }));
    await waitFor(() => expect(screen.getByRole("link", { name: "r2" })).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /load more/i })).toBeNull();
    expect(within(runContext).getByText(formatTime("2026-01-03T00:00:00Z"))).toBeInTheDocument();
    expect(GET).toHaveBeenLastCalledWith("/api/benchmark-results", {
      params: { query: { run_id: "run-a", page_size: 100, cursor: "cur2" } },
    });
  });

  it("shows empty and error states", async () => {
    GET.mockResolvedValueOnce({ data: { results: [], next_page_cursor: null } });
    const { unmount } = render(RunPage, { props: { runId: "run-a" } });
    await waitFor(() => expect(screen.getByText(/no results found for this run/i)).toBeInTheDocument());
    unmount();

    GET.mockResolvedValueOnce({ error: { detail: "statement timeout" } });
    render(RunPage, { props: { runId: "run-a" } });
    await waitFor(() => expect(screen.getByText(/failed to load run/i)).toBeInTheDocument());
    expect(screen.getByText(/statement timeout/i)).toBeInTheDocument();
  });
});
