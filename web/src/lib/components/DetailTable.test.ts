import { fireEvent, render, screen } from "@testing-library/svelte";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { toSeriesPoints, toTableRows } from "../series/transform";
import DetailTable from "./DetailTable.svelte";

function swallowAnchorNavigation(e: Event) {
  e.preventDefault();
}

beforeEach(() => document.addEventListener("click", swallowAnchorNavigation));
afterEach(() => document.removeEventListener("click", swallowAnchorNavigation));

const rows = toTableRows(
  toSeriesPoints([
    {
      benchmark_result_id: "r1",
      commit_hash: "abc1234",
      commit_message: "tune",
      commit_repository: "repo",
      commit_timestamp: "2024-01-07T12:00:00Z",
      data: null,
      hardware_hash: "hw1",
      mean: 1.1,
      result_timestamp: "2024-01-07T13:00:00Z",
      single_value_summary: 1.1,
      single_value_summary_type: "min",
      unit: "s",
      run_tags: {},
      info: {},
      change_annotations: {},
      zscorestats: {
        begins_distribution_change: false,
        is_outlier: true,
        is_step: false,
        residual: 0.2,
        rolling_mean: 1.0,
        rolling_mean_excluding_this_commit: 1.0,
        rolling_stddev: 0.05,
        segment_id: 0,
      },
    },
  ]),
);

describe("DetailTable", () => {
  it("renders commit links, z, and flags", () => {
    render(DetailTable, { props: { rows } });
    expect(screen.getByRole("link", { name: "abc1234" })).toHaveAttribute(
      "href",
      "/results/r1",
    );
    expect(screen.getByText("4.00")).toBeInTheDocument();
    expect(screen.getByText("outlier")).toBeInTheDocument();
  });

  it("wraps the table for responsive layouts", () => {
    const { container } = render(DetailTable, { props: { rows } });
    expect(container.querySelector(".detail-list > table.detail")).not.toBeNull();
  });

  it("groups commit mobile cell content into one value item", () => {
    render(DetailTable, { props: { rows } });
    const commitCell = screen.getByRole("link", { name: "abc1234" }).closest("td");
    expect(commitCell?.querySelector(".cell-value")).not.toBeNull();
    expect(commitCell?.querySelector(".cell-value .msg")).toHaveTextContent("tune");
  });

  it("selects a row on click and opens the result via the commit link", async () => {
    const onselect = vi.fn();
    const onopen = vi.fn();
    render(DetailTable, { props: { rows, onselect, onopen } });
    await fireEvent.click(screen.getByText("outlier"));
    expect(onselect).toHaveBeenCalledWith(0);
    await fireEvent.click(screen.getByRole("link", { name: "abc1234" }));
    expect(onopen).toHaveBeenCalledWith(rows[0]);
    expect(onselect).toHaveBeenCalledTimes(1);
  });

  it("leaves modified commit-link clicks to the browser", async () => {
    const onopen = vi.fn();
    render(DetailTable, { props: { rows, onopen } });
    await fireEvent.click(screen.getByRole("link", { name: "abc1234" }), { metaKey: true });
    expect(onopen).not.toHaveBeenCalled();
  });
});
