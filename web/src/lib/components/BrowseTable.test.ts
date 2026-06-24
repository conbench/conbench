import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { toBrowseRows } from "../browse/transform";
import BrowseTable from "./BrowseTable.svelte";

// Anchor clicks that the component does not handle fall through to the native
// default action; jsdom does not implement navigation and logs to stderr.
// Swallow the default here so output stays clean while recording the component's
// own decision. When the component intercepts a click it calls
// stopPropagation(), so this document-level listener never runs and the value
// stays at its "prevented" default. When the component declines (no onopen, or a
// modified click) the event bubbles here with defaultPrevented still false,
// which records the native fall-through before we swallow it. Hence the reset is
// true (assume intercepted) and only an observed bubble flips it to false.
let componentPreventedDefault = true;

function swallowAnchorNavigation(e: Event) {
  componentPreventedDefault = e.defaultPrevented;
  e.preventDefault();
}

beforeEach(() => {
  componentPreventedDefault = true;
  document.addEventListener("click", swallowAnchorNavigation);
});
afterEach(() => document.removeEventListener("click", swallowAnchorNavigation));

const rows = toBrowseRows(
  [
    {
      history_fingerprint: "fp1",
      name: "tpch-q1",
      tags: { name: "tpch-q1", scale: "sf10" },
      context: { compiler: "gcc-13" },
      hardware: { id: "h1", type: "machine", name: "m5", hash: "hw1" },
      repository: "https://github.com/conbench/demo",
      unit: "s",
      less_is_better: true,
      status: "regressed",
      latest_result_id: "r9",
      latest_single_value_summary: 1.2,
      latest_single_value_summary_type: "min",
      latest_commit_sha: "a1b2c3d4e5",
      latest_commit_timestamp: "2024-01-07T12:00:00Z",
      latest_result_timestamp: "2024-01-07T13:00:00Z",
      point_count: 8,
      sparkline: [1.0, 1.1, 1.2],
    },
  ],
  "en-US",
);

describe("BrowseTable", () => {
  it("renders one row with identity, value, status, and trend link", () => {
    render(BrowseTable, { props: { rows } });
    expect(screen.getByRole("link", { name: "tpch-q1" })).toHaveAttribute("href", "/series/fp1");
    expect(screen.getByText("scale=sf10")).toBeInTheDocument();
    expect(screen.getByText("1.2 s")).toBeInTheDocument();
    expect(screen.getByText("regressed")).toBeInTheDocument();
    expect(screen.getByText(/a1b2c3d/)).toBeInTheDocument();
  });

  it("uses the shared data-table and stacked-table treatment", () => {
    const { container } = render(BrowseTable, { props: { rows } });
    expect(container.querySelector(".table-panel > table.data-table.stacked-table.browse-table")).not.toBeNull();
  });

  it("groups multi-part mobile cell content into one value item", () => {
    render(BrowseTable, { props: { rows } });
    const nameCell = screen.getByRole("link", { name: "tpch-q1" }).closest("td");
    expect(nameCell?.querySelector(".identity-stack")).not.toBeNull();
    expect(nameCell?.querySelector(".identity-stack .metadata-line")).toHaveTextContent("scale=sf10");
  });

  it("keeps production-shaped long metadata in wrapped value stacks with compact signal cells", () => {
    const longRows = toBrowseRows(
      [
        {
          history_fingerprint: "long-fp",
          name: "benchmark-with-a-very-long-name/including/repository-ish/path/components/and-extra-identifiers",
          tags: {
            name: "benchmark-with-a-very-long-name/including/repository-ish/path/components/and-extra-identifiers",
            parameter_set: "dataset=parquet-wide-1tb-and-filter=very-long-expression",
            codec: "zstd-level-19-with-long-option-name",
          },
          context: {
            compiler_flags:
              "-O3 -march=native -fno-omit-frame-pointer -fdebug-prefix-map=/very/long/build/root=/src",
            runtime: "python-3.13.0-cpython-with-long-build-tag",
          },
          hardware: {
            id: "host-with-long-id",
            type: "machine",
            name: "production-runner-us-east-1-c7i-metal-24xl-with-extra-suffix",
            hash: "hw-long",
          },
          repository: "https://github.com/conbench/demo",
          unit: "s",
          less_is_better: true,
          status: "stable",
          latest_result_id: "long-r",
          latest_single_value_summary: 1234.567,
          latest_single_value_summary_type: "min",
          latest_commit_sha: "0123456789abcdef",
          latest_commit_timestamp: "2024-01-07T12:00:00Z",
          latest_result_timestamp: "2024-01-07T13:00:00Z",
          point_count: 42,
          sparkline: [1230, 1234, 1232],
        },
      ],
      "en-US",
    );

    render(BrowseTable, { props: { rows: longRows } });

    expect(screen.getByRole("link", { name: /^benchmark-with-a-very-long-name/ })).toHaveClass("row-primary-link");
    expect(screen.getByText(/compiler_flags=/).closest("td")).toHaveClass("wrap-anywhere");
    expect(screen.getByText(/production-runner-us-east-1/).closest("td")).toHaveClass("wrap-anywhere");
    expect(screen.getByLabelText("sparkline of 3 points").closest("td")).toHaveClass("trend-cell");
    expect(screen.getByText("stable").closest("td")).toHaveClass("status-cell");
  });

  it("opens a row on link click without a page load", async () => {
    const onopen = vi.fn();
    render(BrowseTable, { props: { rows, onopen } });
    await fireEvent.click(screen.getByRole("link", { name: "tpch-q1" }));
    expect(onopen).toHaveBeenCalledWith(rows[0]);
    expect(componentPreventedDefault).toBe(true);
  });

  it("falls back to native link navigation when onopen is absent", async () => {
    render(BrowseTable, { props: { rows } });
    await fireEvent.click(screen.getByRole("link", { name: "tpch-q1" }));
    expect(componentPreventedDefault).toBe(false);
  });

  it("opens exactly once per link click (no tr double-fire)", async () => {
    const onopen = vi.fn();
    render(BrowseTable, { props: { rows, onopen } });
    await fireEvent.click(screen.getByRole("link", { name: "tpch-q1" }));
    expect(onopen).toHaveBeenCalledTimes(1);
  });

  it("leaves modified link clicks to the browser", async () => {
    const onopen = vi.fn();
    render(BrowseTable, { props: { rows, onopen } });
    await fireEvent.click(screen.getByRole("link", { name: "tpch-q1" }), { metaKey: true });
    expect(onopen).not.toHaveBeenCalled();
  });

  it("reports header clicks for sortable columns only", async () => {
    const onsort = vi.fn();
    render(BrowseTable, { props: { rows, onsort } });
    await fireEvent.click(screen.getByRole("button", { name: "Sort by benchmark" }));
    expect(onsort).toHaveBeenCalledWith("name");
    expect(screen.queryByRole("button", { name: /^status$/ })).toBeNull();
  });

  it("marks the active sort header for assistive technology", () => {
    render(BrowseTable, { props: { rows, sort: { key: "name", dir: "desc" } } });
    const button = screen.getByRole("button", { name: "Sort by benchmark" });
    expect(button).toHaveClass("active");
    expect(button).toHaveAttribute("aria-pressed", "true");
    expect(button.closest("th")).toHaveAttribute("aria-sort", "descending");
    expect(screen.getByRole("button", { name: "Sort by last value" }).closest("th")).not.toHaveAttribute(
      "aria-sort",
    );
  });
});
