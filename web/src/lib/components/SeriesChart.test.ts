import { render, screen } from "@testing-library/svelte";
import { tick } from "svelte";
import { describe, expect, it, vi } from "vitest";

import type { SeriesPoint } from "../series/transform";

const plotState = vi.hoisted(() => ({
  cursorHook: undefined as ((plot: unknown) => void) | undefined,
  instance: undefined as unknown,
}));

vi.mock("uplot", () => {
  class MockUPlot {
    data: unknown;
    bbox = { left: 0, top: 0, width: 640, height: 280 };
    cursor = { left: 0, top: 0 };

    constructor(options: { hooks?: { setCursor?: ((plot: unknown) => void)[] } }, data: unknown) {
      this.data = data;
      plotState.cursorHook = options.hooks?.setCursor?.[0];
      plotState.instance = this;
    }

    destroy() {}
    redraw() {}
    setSize() {}
  }
  return { default: MockUPlot };
});

import SeriesChart from "./SeriesChart.svelte";

const boundaryPoint: SeriesPoint = {
  resultId: "r1",
  commitHash: "abc1234",
  commitMessage: "update benchmark setup",
  commitTimestampMs: Date.parse("2026-01-01T00:00:00Z"),
  resultTimestampMs: Date.parse("2026-01-01T00:01:00Z"),
  chartMs: Date.parse("2026-01-01T00:00:00Z"),
  measurements: [1],
  svs: 1,
  unit: "s",
  runTags: { channel: "nightly" },
  info: { build: "release" },
  changeAnnotations: { begins_distribution_change: true },
  stats: {
    z: null,
    rollingMean: 1,
    rollingStddev: null,
    isOutlier: false,
    isStep: false,
    beginsChange: true,
    segmentId: 1,
  },
};

describe("SeriesChart", () => {
  it("renders generic metadata in a boundary point tooltip", async () => {
    render(SeriesChart, { props: { points: [boundaryPoint] } });
    expect(plotState.cursorHook).toBeTypeOf("function");
    plotState.cursorHook?.(plotState.instance);
    await tick();
    expect(screen.getByText("info: build=release")).toBeInTheDocument();
    expect(screen.getByText("run: channel=nightly")).toBeInTheDocument();
  });
});
