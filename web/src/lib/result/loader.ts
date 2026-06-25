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
  displayResultId: string;
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
  displayHardwareHash: string;
  commitSha: string | null;
  shortCommit: string | null;
  commitMessage: string | null;
  commitDateText: string | null;
  repository: string;
  repositoryLabel: string;
  runId: string;
  displayRunId: string;
  runReason: string | null;
  runTagsText: string;
  batchId: string | null;
  displayBatchId: string | null;
  resultDateText: string;
  fingerprint: string;
  displayFingerprint: string;
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
  const commitSha = d.commit === null ? null : d.commit.sha;
  const repository = d.commit_repo_url;
  return {
    id: d.id,
    displayResultId: compactIdentifier(d.id, 12, 8),
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
    displayHardwareHash: compactIdentifier(d.hardware.hash, 12, 8),
    commitSha,
    shortCommit: commitSha === null ? null : commitSha.slice(0, 8),
    commitMessage: d.commit === null ? null : d.commit.message,
    commitDateText:
      d.commit === null || d.commit.timestamp === null
        ? null
        : formatDate(d.commit.timestamp, locale),
    repository,
    repositoryLabel: formatRepositoryLabel(repository),
    runId: d.run_id,
    displayRunId: compactIdentifier(d.run_id, 12, 8),
    runReason: d.run_reason,
    runTagsText: compactTagsText(d.run_tags),
    batchId: d.batch_id,
    displayBatchId: d.batch_id === null ? null : compactIdentifier(d.batch_id, 12, 8),
    resultDateText: formatDate(d.timestamp, locale),
    fingerprint: d.history_fingerprint,
    displayFingerprint: compactIdentifier(d.history_fingerprint, 12, 8),
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

function compactIdentifier(value: string, head: number, tail: number): string {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

function formatRepositoryLabel(repository: string): string {
  if (repository === "") return "repository not set";
  let u: URL;
  try {
    u = new URL(repository);
  } catch {
    return repository;
  }
  const path = u.pathname.replace(/^\/+|\/+$/g, "");
  if (u.hostname === "github.com" || u.hostname === "www.github.com") {
    return path || u.hostname;
  }
  return `${u.hostname}${path === "" ? "" : `/${path}`}`;
}

function compactTagsText(tags: Record<string, unknown>): string {
  return Object.keys(tags)
    .sort()
    .map((k) => `${k}=${compactTagValue(String(tags[k]))}`)
    .join(" · ");
}

function compactTagValue(value: string): string {
  return value.replace(/\b([0-9a-f]{32,40})\b/gi, (match) => compactIdentifier(match, 12, 8));
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
