import { render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RecentRunsHome from "./RecentRunsHome.svelte";

const GET = vi.fn();
vi.mock("../api/client", () => ({
  createConbenchClient: () => ({ GET }),
}));

const run = (overrides: Record<string, unknown> = {}) => ({
  run_id: "run-a",
  run_reason: "nightly",
  run_tags: { arch: "x86" },
  batch_count: 1,
  latest_batch_id: "batch-a",
  result_count: 180,
  error_count: 1,
  series_count: 90,
  latest_result_id: "result-a",
  repository: "https://github.com/apache/arrow",
  commit_sha: "abcdef123456",
  first_result_at: "2026-01-01T00:00:00Z",
  last_result_at: "2026-01-02T00:00:00Z",
  commit: {
    hash: "abcdef123456",
    repository: "https://github.com/apache/arrow",
    timestamp: "2026-01-02T00:00:00Z",
  },
  ...overrides,
});

beforeEach(() => {
  GET.mockReset();
  window.history.replaceState(null, "", "/");
});

describe("RecentRunsHome", () => {
  it("renders recent run summaries with investigation links", async () => {
    GET.mockResolvedValueOnce({ data: { runs: [run(), run({ run_id: "run-b", error_count: 0 })] } });

    render(RecentRunsHome, { props: {} });

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("heading", { name: /recent runs/i })).toBeInTheDocument());

    expect(screen.getByText(/2 runs/i)).toBeInTheDocument();
    expect(screen.getByText(/360 results/i)).toBeInTheDocument();
    expect(screen.getByText(/1 error/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open run run-a" })).toHaveAttribute("href", "/runs/run-a");
    expect(screen.getAllByRole("link", { name: "Open batch batch-a" })[0]).toHaveAttribute(
      "href",
      "/batches/batch-a",
    );
    expect(screen.getAllByText("nightly")).toHaveLength(2);
    expect(screen.getAllByText("abcdef12")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Open CI report for run run-a" })).toHaveAttribute(
      "href",
      "/ci/report?repository=https%3A%2F%2Fgithub.com%2Fapache%2Farrow&commit_sha=abcdef123456&run_ids=run-a&baseline=fork_point",
    );
    expect(screen.getByRole("link", { name: "Open sample result for run run-a" })).toHaveAttribute(
      "href",
      "/results/result-a",
    );
  });

  it("uses compact production identifiers without losing full link targets", async () => {
    const longRunID = "66f23037065241d6ac22aaeaea96d29b";
    const longBatchID = "66f23037065241d6ac22aaeaea96d29b-1p";
    GET.mockResolvedValueOnce({
      data: {
        runs: [
          run({
            run_id: longRunID,
            latest_batch_id: longBatchID,
            repository: "https://github.com/apache/arrow",
            result_count: 4568,
            series_count: 4568,
            error_count: 0,
          }),
        ],
      },
    });

    render(RecentRunsHome, { props: {} });

    await waitFor(() => expect(screen.getByRole("heading", { name: /recent runs/i })).toBeInTheDocument());
    expect(screen.getByText("66f230370652…ea96d29b")).toBeInTheDocument();
    expect(screen.getByText("batch 66f230370652…29b-1p")).toBeInTheDocument();
    expect(screen.getByText("repository apache/arrow")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: `Open run ${longRunID}` })).toHaveAttribute(
      "href",
      `/runs/${longRunID}`,
    );
    expect(screen.getByRole("link", { name: `Open batch ${longBatchID}` })).toHaveAttribute(
      "href",
      `/batches/${longBatchID}`,
    );
  });

  it("suppresses empty row metadata and renders compact inline actions", async () => {
    GET.mockResolvedValueOnce({
      data: {
        runs: [
          run({ run_id: "run-a", run_reason: null, error_count: 0 }),
          run({ run_id: "run-b", run_reason: null, error_count: 0 }),
        ],
      },
    });

    const { container } = render(RecentRunsHome, { props: {} });

    await waitFor(() => expect(screen.getByRole("heading", { name: /recent runs/i })).toBeInTheDocument());
    expect(screen.getByText("repository apache/arrow")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Reason" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Repository" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Errors" })).not.toBeInTheDocument();
    expect(screen.queryByText("0 errors")).not.toBeInTheDocument();
    expect(container.querySelector(".button-pill")).toBeNull();
    expect(container.querySelector(".inline-actions")).not.toBeNull();
  });

  it("shows an empty state", async () => {
    GET.mockResolvedValueOnce({ data: { runs: [] } });
    render(RecentRunsHome, { props: {} });
    await waitFor(() => expect(screen.getByText(/no recent runs/i)).toBeInTheDocument());
  });

  it("shows an error state", async () => {
    GET.mockResolvedValueOnce({ error: { detail: "statement timeout" } });
    render(RecentRunsHome, { props: {} });
    await waitFor(() => expect(screen.getByText(/failed to load recent runs/i)).toBeInTheDocument());
    expect(screen.getByText(/statement timeout/i)).toBeInTheDocument();
  });
});
