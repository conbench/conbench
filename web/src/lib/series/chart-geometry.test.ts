import { describe, expect, it } from "vitest";

import {
  closestIndexForSortedValueOffset,
  closestIndexForValue,
  indexForCursorOffset,
  indexForCursorValue,
  paddedValueRange,
  tooltipLeftForCursor,
  tooltipTopForCursor,
} from "./chart-geometry";

describe("chart geometry", () => {
  it("maps a moving commit-order cursor value to the nearest data index", () => {
    expect(indexForCursorValue(0, 10)).toBe(0);
    expect(indexForCursorValue(4.4, 10)).toBe(4);
    expect(indexForCursorValue(4.6, 10)).toBe(5);
    expect(indexForCursorValue(99, 10)).toBe(9);
    expect(indexForCursorValue(-10, 10)).toBe(0);
    expect(indexForCursorValue(3, 0)).toBeNull();
  });

  it("maps cursor offsets across the plot width to commit-order indices", () => {
    expect(indexForCursorOffset(0, 100, 11)).toBe(0);
    expect(indexForCursorOffset(45, 100, 11)).toBe(5);
    expect(indexForCursorOffset(100, 100, 11)).toBe(10);
    expect(indexForCursorOffset(150, 100, 11)).toBe(10);
    expect(indexForCursorOffset(10, 0, 11)).toBeNull();
  });

  it("finds the nearest index in sorted time-axis values", () => {
    expect(closestIndexForValue(3, [0, 10, 20])).toBe(0);
    expect(closestIndexForValue(14, [0, 10, 20])).toBe(1);
    expect(closestIndexForValue(16, [0, 10, 20])).toBe(2);
    expect(closestIndexForValue(16, [])).toBeNull();
  });

  it("maps cursor offsets across sorted timestamp values to the nearest point", () => {
    const values = [1_000, 2_000, 4_000];
    expect(closestIndexForSortedValueOffset(0, 100, values)).toBe(0);
    expect(closestIndexForSortedValueOffset(50, 100, values)).toBe(1);
    expect(closestIndexForSortedValueOffset(75, 100, values)).toBe(2);
    expect(closestIndexForSortedValueOffset(100, 100, values)).toBe(2);
    expect(closestIndexForSortedValueOffset(10, 0, values)).toBeNull();
    expect(closestIndexForSortedValueOffset(10, 100, [])).toBeNull();
  });

  it("computes one padded numeric range for chart and overlay y scales", () => {
    expect(paddedValueRange([10, 20], 0.1)).toEqual({ min: 9, max: 21 });
    expect(paddedValueRange([5], 0.05)).toEqual({ min: 4.95, max: 5.05 });
    expect(paddedValueRange([Number.NaN, Number.POSITIVE_INFINITY])).toBeNull();
  });

  it("clamps tooltip left positions inside narrow chart bounds", () => {
    expect(tooltipLeftForCursor(100, 800, 320)).toBe(108);
    expect(tooltipLeftForCursor(620, 800, 320)).toBe(472);
    expect(tooltipLeftForCursor(10, 320, 448)).toBe(8);
    expect(tooltipLeftForCursor(300, 320, 448)).toBe(8);
  });

  it("keeps tooltips below the cursor when there is no room above", () => {
    expect(tooltipTopForCursor(20, 280, 96)).toEqual({ top: 28, placement: "below" });
    expect(tooltipTopForCursor(160, 280, 96)).toEqual({ top: 56, placement: "above" });
    expect(tooltipTopForCursor(140, 150, 128)).toEqual({ top: 14, placement: "clamped" });
  });
});
