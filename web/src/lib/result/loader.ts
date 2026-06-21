import type { createConbenchClient } from "../api/client";
import type { components } from "../api/schema";
import { formatDate, formatSVS, tagsText } from "../browse/transform";

type Client = ReturnType<typeof createConbenchClient>;
export type ResultDetail = components["schemas"]["ResultDetail"];

export interface JSONBlock {
  label: string;
  value: string;
}

export interface ResultViewModel {
  id: string;
  name: string;
  paramsText: string;
  contextText: string;
  svsText: string;
  svsType: string;
  iterations: number | null;
  aggregates: { label: string; value: string }[];
  error: Record<string, unknown> | null;
  hardwareName: string;
  hardwareType: string;
  hardwareHash: string;
  commitSha: string | null;
  commitMessage: string | null;
  commitDateText: string | null;
  repository: string;
  runId: string;
  runReason: string | null;
  runTagsText: string;
  batchId: string | null;
  resultDateText: string;
  fingerprint: string;
  lessIsBetterText: string;
  timeUnitText: string;
  dataCountText: string;
  timesCountText: string;
  historyExportHref: string;
  beginsDistributionChange: boolean;
  jsonBlocks: JSONBlock[];
}

const AGGREGATE_LABELS = ["min", "max", "mean", "median", "q1", "q3", "stdev", "iqr"] as const;

function toAggregates(
  stats: ResultDetail["stats"],
  unit: string | null,
): { label: string; value: string }[] {
  return AGGREGATE_LABELS.flatMap((label) => {
    const v = stats[label];
    return v === null ? [] : [{ label, value: `${formatSVS(v)}${unit ? ` ${unit}` : ""}` }];
  });
}

function jsonText(value: unknown): string {
  return JSON.stringify(value ?? null, null, 2);
}

function valueCountText(values: unknown[] | null): string {
  if (values === null) return "not stored";
  return `${values.length.toLocaleString()} ${values.length === 1 ? "value" : "values"}`;
}

export function resultViewModelFromDetail(
  d: ResultDetail,
  locale?: string,
): ResultViewModel {
  const tags: Record<string, unknown> = { ...d.tags };
  const changeAnnotations = d.change_annotations ?? {};
  const rawName = tags["name"];
  const name = typeof rawName === "string" ? rawName : "(unnamed)";
  delete tags["name"];
  const svs = d.single_value_summary;
  return {
    id: d.id,
    name,
    paramsText: tagsText(tags),
    contextText: tagsText(d.context),
    svsText: svs === null ? "—" : `${formatSVS(svs)}${d.unit ? ` ${d.unit}` : ""}`,
    svsType: d.single_value_summary_type,
    iterations: d.iterations,
    aggregates: toAggregates(d.stats, d.unit),
    error: d.error,
    hardwareName: d.hardware.name,
    hardwareType: d.hardware.type,
    hardwareHash: d.hardware.hash,
    commitSha: d.commit === null ? null : d.commit.sha,
    commitMessage: d.commit === null ? null : d.commit.message,
    commitDateText:
      d.commit === null || d.commit.timestamp === null
        ? null
        : formatDate(d.commit.timestamp, locale),
    repository: d.commit_repo_url,
    runId: d.run_id,
    runReason: d.run_reason,
    runTagsText: tagsText(d.run_tags),
    batchId: d.batch_id,
    resultDateText: formatDate(d.timestamp, locale),
    fingerprint: d.history_fingerprint,
    lessIsBetterText: d.less_is_better === null ? "not set" : String(d.less_is_better),
    timeUnitText: d.time_unit ?? "not set",
    dataCountText: valueCountText(d.data),
    timesCountText: valueCountText(d.times),
    historyExportHref: `/api/history/${encodeURIComponent(d.id)}`,
    beginsDistributionChange: changeAnnotations["begins_distribution_change"] === true,
    jsonBlocks: [
      { label: "tags", value: jsonText(d.tags) },
      { label: "context", value: jsonText(d.context) },
      { label: "info", value: jsonText(d.info) },
      { label: "optional info", value: jsonText(d.optional_benchmark_info) },
      { label: "validation", value: jsonText(d.validation) },
      { label: "change annotations", value: jsonText(changeAnnotations) },
      { label: "run tags", value: jsonText(d.run_tags) },
      { label: "raw payload", value: jsonText(d) },
    ],
  };
}

/** loadResult fetches one benchmark result and shapes the light detail view.
 * Throws on failure so the page error state owns presentation. */
export async function loadResult(
  client: Client,
  id: string,
  locale?: string,
): Promise<ResultViewModel> {
  const res = await client.GET("/api/benchmark-results/{id}", { params: { path: { id } } });
  if (res.error || !res.data) {
    throw new Error(`failed to load benchmark result ${id}`);
  }
  return resultViewModelFromDetail(res.data, locale);
}
