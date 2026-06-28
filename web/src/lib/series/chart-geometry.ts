export function indexForCursorValue(value: number, count: number): number | null {
  if (!Number.isFinite(value) || count <= 0) return null;
  const idx = Math.round(value);
  return Math.min(count - 1, Math.max(0, idx));
}

export function indexForCursorOffset(left: number, width: number, count: number): number | null {
  if (!Number.isFinite(left) || !Number.isFinite(width) || width <= 0 || count <= 0) return null;
  if (count === 1) return 0;
  const pct = Math.min(1, Math.max(0, left / width));
  return indexForCursorValue(pct * (count - 1), count);
}

export function closestIndexForValue(value: number, values: readonly number[]): number | null {
  if (!Number.isFinite(value) || values.length === 0) return null;
  let lo = 0;
  let hi = values.length - 1;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (values[mid]! < value) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }
  const right = lo;
  const left = Math.max(0, right - 1);
  return Math.abs(values[left]! - value) <= Math.abs(values[right]! - value) ? left : right;
}

export function closestIndexForSortedValueOffset(
  left: number,
  width: number,
  values: readonly number[],
): number | null {
  if (!Number.isFinite(left) || !Number.isFinite(width) || width <= 0 || values.length === 0) {
    return null;
  }
  const first = values[0]!;
  const last = values[values.length - 1]!;
  if (!Number.isFinite(first) || !Number.isFinite(last)) return null;
  const pct = Math.min(1, Math.max(0, left / width));
  return closestIndexForValue(first + (last - first) * pct, values);
}

export interface ValueRange {
  min: number;
  max: number;
}

function tooltipUsableWidth(containerWidth: number, tooltipWidth: number, margin: number): number {
  return Math.min(tooltipWidth, Math.max(0, containerWidth - margin * 2));
}

export function tooltipLeftForCursor(
  left: number,
  containerWidth: number,
  tooltipWidth = 448,
  margin = 8,
): number {
  if (!Number.isFinite(left) || !Number.isFinite(containerWidth) || containerWidth <= 0) {
    return margin;
  }
  const usableWidth = tooltipUsableWidth(containerWidth, tooltipWidth, margin);
  const minLeft = margin;
  const maxLeft = Math.max(minLeft, containerWidth - usableWidth - margin);
  return Math.min(maxLeft, Math.max(minLeft, left + margin));
}

export type TooltipVerticalPlacement = "above" | "below" | "clamped";

export interface TooltipVerticalPosition {
  top: number;
  placement: TooltipVerticalPlacement;
}

export function tooltipTopForCursor(
  top: number,
  containerHeight: number,
  tooltipHeight = 128,
  margin = 8,
): TooltipVerticalPosition {
  if (!Number.isFinite(top) || !Number.isFinite(containerHeight) || containerHeight <= 0) {
    return { top: margin, placement: "below" };
  }
  const safeTooltipHeight = Number.isFinite(tooltipHeight) && tooltipHeight > 0 ? tooltipHeight : 0;
  const minTop = margin;
  const maxTop = Math.max(minTop, containerHeight - safeTooltipHeight - margin);
  const aboveTop = top - safeTooltipHeight - margin;
  if (aboveTop >= minTop) {
    return { top: aboveTop, placement: "above" };
  }
  const belowTop = top + margin;
  if (belowTop <= maxTop) {
    return { top: belowTop, placement: "below" };
  }
  return {
    top: Math.min(maxTop, Math.max(minTop, top - safeTooltipHeight / 2)),
    placement: "clamped",
  };
}

export function paddedValueRange(
  values: readonly number[],
  padFraction = 0.05,
): ValueRange | null {
  const finite = values.filter(Number.isFinite);
  if (finite.length === 0) return null;
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  const span = max - min || 1;
  const pad = span * padFraction;
  return { min: min - pad, max: max + pad };
}
