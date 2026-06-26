import type { components } from "../api/schema";
import { formatMeasurement, formatNumber } from "../format";
import type { BrowseWindow } from "../router";

type SeriesListItem = components["schemas"]["SeriesListItem"];

/** SeriesStatus is the wire enum (closed union in the generated schema). */
export type SeriesStatus = SeriesListItem["status"];

export interface BrowseRow {
  fingerprint: string;
  name: string;
  paramsText: string;
  contextText: string;
  hardwareKey: string;
  hardwareName: string;
  latestSVS: number | null;
  svsText: string;
  pointCount: number;
  sparkline: number[];
  status: SeriesStatus;
  commitSha: string;
  commitTimestampMs: number;
  commitDateText: string;
}

/** formatSVS renders an SVS for dense tables: exact grouped integers and
 * compact decimal values with trailing zeros trimmed. */
export function formatSVS(value: number): string {
  return formatNumber(value);
}

/** formatDate renders a short local date; datetimes are UTC on the wire and
 * local-time conversion belongs here in the UI. locale is injectable for tests. */
export function formatDate(iso: string, locale?: string): string {
  return new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "numeric" }).format(
    new Date(iso),
  );
}

/** tagsText joins tags as `k=v · k2=v2`, keys sorted for determinism. */
export function tagsText(tags: Record<string, unknown>, omit: string[] = []): string {
  const skip = new Set(omit);
  return Object.keys(tags)
    .filter((k) => !skip.has(k))
    .sort()
    .map((k) => `${k}=${String(tags[k])}`)
    .join(" · ");
}

export function toBrowseRows(items: SeriesListItem[], locale?: string): BrowseRow[] {
  return items.map((item) => {
    const svs = item.latest_single_value_summary;
    return {
      fingerprint: item.history_fingerprint,
      name: item.name,
      paramsText: tagsText(item.tags, ["name"]),
      contextText: tagsText(item.context),
      hardwareKey: item.hardware.hash || item.hardware.id,
      hardwareName: item.hardware.name,
      latestSVS: svs,
      svsText: formatMeasurement(svs, item.unit),
      pointCount: item.point_count,
      sparkline: item.sparkline ?? [],
      status: item.status,
      commitSha: item.latest_commit_sha.slice(0, 7),
      commitTimestampMs: Date.parse(item.latest_commit_timestamp),
      commitDateText: formatDate(item.latest_commit_timestamp, locale),
    };
  });
}

export type SortKey = "name" | "svs" | "points" | "commit";

export interface SortSpec {
  key: SortKey;
  dir: "asc" | "desc";
}

const SORT_ACCESSORS: Record<SortKey, (r: BrowseRow) => string | number | null> = {
  name: (r) => r.name,
  svs: (r) => r.latestSVS,
  points: (r) => r.pointCount,
  commit: (r) => r.commitTimestampMs,
};

/** sortRows orders the LOADED rows client-side; null keeps the server's
 * canonical order (latest activity DESC), which is also the pagination order.
 * A null SVS sorts last in both directions. Pure: returns a copy. */
export function sortRows(rows: BrowseRow[], sort: SortSpec | null): BrowseRow[] {
  if (sort === null) {
    return rows;
  }
  const get = SORT_ACCESSORS[sort.key];
  const dir = sort.dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = get(a);
    const bv = get(b);
    if (av === null) return bv === null ? 0 : 1;
    if (bv === null) return -1;
    if (typeof av === "string" && typeof bv === "string") return dir * av.localeCompare(bv);
    return dir * ((av as number) - (bv as number));
  });
}

const WINDOW_DAYS: Record<Exclude<BrowseWindow, "all">, number> = {
  "30d": 30,
  "3mo": 90,
  "1y": 365,
};

/** windowStartIso turns a window preset into the absolute UTC active_since the
 * endpoint takes; "all" means unconstrained (null). Presets are FIXED-LENGTH
 * rolling windows (30/90/365 days ending at now), not calendar-aligned months
 * or years: deterministic, DST-free, and shared with the trend's range presets
 * (windowPoints in series/transform.ts). now is injectable. */
export function windowStartIso(window: BrowseWindow, now: Date): string | null {
  if (window === "all") {
    return null;
  }
  return new Date(now.getTime() - WINDOW_DAYS[window] * 24 * 60 * 60 * 1000).toISOString();
}

/** sparklinePoints maps values onto an SVG polyline points string inside a
 * width x height box with pad margins; min/max normalized, larger = higher
 * (smaller y). A flat series renders as a midline. */
export function sparklinePoints(values: number[], width: number, height: number, pad: number): string {
  if (values.length === 0) {
    return "";
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;
  const innerW = width - 2 * pad;
  const innerH = height - 2 * pad;
  return values
    .map((v, i) => {
      const x = values.length === 1 ? width / 2 : pad + (i * innerW) / (values.length - 1);
      const y = span === 0 ? height / 2 : pad + innerH - ((v - min) / span) * innerH;
      return `${round2(x)},${round2(y)}`;
    })
    .join(" ");
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}
