<script lang="ts">
  import { tick } from "svelte";

  import { createConbenchClient } from "../api/client";
  import { formatNumber } from "../format";
  import { hasCIReportSelector, loadCIReport, type CIReport } from "../ci-report/loader";
  import { interceptNavClick, navigate, type CIReportQuery } from "../router";

  type ReportRun = NonNullable<CIReport["runs"]>[number];
  type ReportComparison = NonNullable<ReportRun["comparisons"]>[number];
  type RowStatus = ReportComparison["status"];
  type StatusFilter = "all" | RowStatus;
  type IssueStatus = (typeof ISSUE_STATUSES)[number];

  interface FilteredRun {
    run: ReportRun;
    comparisons: ReportComparison[];
  }

  interface IssueTarget {
    status: IssueStatus;
    label: string;
    count: number;
    anchor: string;
    href: string;
    runID: string;
    rowIndex: number;
    benchmark: string;
    hardware: string;
    delta: string;
    z: string;
    reason: string;
  }

  const CI_REPORT_INITIAL_ROWS = 200;
  const CI_REPORT_ROW_CHUNK = 200;

  const STATUS_FILTERS: RowStatus[] = [
    "regressed",
    "errored",
    "missing_baseline",
    "not_comparable",
    "improved",
    "stable",
    "insufficient",
  ];
  const ISSUE_STATUSES = ["regressed", "errored", "missing_baseline", "not_comparable"] as const;
  const STATUS_LABELS: Record<RowStatus, string> = {
    regressed: "regressed",
    improved: "improved",
    stable: "stable",
    insufficient: "insufficient",
    errored: "errored",
    missing_baseline: "missing baseline",
    not_comparable: "not comparable",
  };

  let {
    query,
    baseUrl = "",
  }: {
    query: CIReportQuery;
    baseUrl?: string;
  } = $props();

  const client = $derived(createConbenchClient(baseUrl));

  let report = $state<CIReport | null>(null);
  let errorMsg = $state<string | null>(null);
  let rowLimits = $state<Record<string, number>>({});
  let statusFilter = $state<StatusFilter>("all");
  let hardwareFilter = $state("all");
  let searchText = $state("");
  let reqToken = 0;

  let ready = $derived(hasCIReportSelector(query));
  let runs = $derived(reportRuns(report));
  let allComparisons = $derived(runs.flatMap((run) => runComparisons(run)));
  let statusCounts = $derived(countStatuses(allComparisons));
  let hardwareOptions = $derived(
    Array.from(new Set(allComparisons.map((row) => row.hardware.name).filter((name) => name !== ""))).sort((a, b) =>
      a.localeCompare(b),
    ),
  );
  let filteredRuns = $derived(filteredReportRuns(runs));
  let filteredComparisons = $derived(filteredRuns.flatMap((entry) => entry.comparisons));
  let filteredStatusCounts = $derived(countStatuses(filteredComparisons));
  let issueTargets = $derived(issueLinks(filteredRuns));

  $effect(() => {
    if (!ready) {
      return;
    }
    const snapshot = { ...query };
    const token = ++reqToken;
    loadCIReport(client, snapshot)
      .then((loaded) => {
        if (token !== reqToken) return;
        report = loaded;
        rowLimits = {};
        errorMsg = null;
      })
      .catch((err: unknown) => {
        if (token !== reqToken) return;
        errorMsg = err instanceof Error ? err.message : String(err);
      });
  });

  function go(e: MouseEvent, href: string) {
    if (!interceptNavClick(e)) return;
    e.preventDefault();
    navigate(href);
  }

  function reportRuns(value: CIReport | null): ReportRun[] {
    return value?.runs ?? [];
  }

  function runComparisons(run: ReportRun): ReportComparison[] {
    return run.comparisons ?? [];
  }

  function emptyStatusCounts(): Record<RowStatus, number> {
    return {
      regressed: 0,
      improved: 0,
      stable: 0,
      insufficient: 0,
      errored: 0,
      missing_baseline: 0,
      not_comparable: 0,
    };
  }

  function countStatuses(rows: ReportComparison[]): Record<RowStatus, number> {
    const counts = emptyStatusCounts();
    for (const row of rows) {
      counts[row.status] += 1;
    }
    return counts;
  }

  function filteredReportRuns(sourceRuns: ReportRun[]): FilteredRun[] {
    return sourceRuns
      .map((run) => ({
        run,
        comparisons: runComparisons(run).filter((row) => matchesFilters(run, row)),
      }))
      .filter((entry) => entry.comparisons.length > 0 || entry.run.baseline_error !== null);
  }

  function matchesFilters(run: ReportRun, row: ReportComparison): boolean {
    if (statusFilter !== "all" && row.status !== statusFilter) {
      return false;
    }
    if (hardwareFilter !== "all" && row.hardware.name !== hardwareFilter) {
      return false;
    }
    const q = searchText.trim().toLowerCase();
    if (q === "") {
      return true;
    }
    return [
      run.run_id,
      run.run_reason ?? "",
      row.name,
      row.history_fingerprint,
      row.hardware.name,
      row.status,
      statusLabel(row.status),
      row.unit ?? "",
      row.reason ?? "",
    ].some((value) => value.toLowerCase().includes(q));
  }

  function issueLinks(sourceRuns: FilteredRun[]): IssueTarget[] {
    const counts = emptyStatusCounts();
    const first = new Map<IssueStatus, { anchor: string; runID: string; rowIndex: number; row: ReportComparison }>();
    for (const entry of sourceRuns) {
      for (const [rowIndex, row] of entry.comparisons.entries()) {
        if (!isIssueStatus(row.status)) {
          continue;
        }
        counts[row.status] += 1;
        if (!first.has(row.status)) {
          first.set(row.status, {
            anchor: anchorID(entry.run.run_id, row),
            runID: entry.run.run_id,
            rowIndex,
            row,
          });
        }
      }
    }
    return ISSUE_STATUSES.flatMap((status) => {
      const target = first.get(status);
      return target === undefined
        ? []
        : [
            {
              status,
              label: statusLabel(status),
              count: counts[status],
              anchor: target.anchor,
              href: `#${target.anchor}`,
              runID: target.runID,
              rowIndex: target.rowIndex,
              benchmark: target.row.name,
              hardware: target.row.hardware.name || "-",
              delta: percentText(target.row),
              z: zText(target.row),
              reason: target.row.reason ?? "",
            },
          ];
    });
  }

  function isIssueStatus(status: RowStatus): status is IssueStatus {
    return (ISSUE_STATUSES as readonly string[]).includes(status);
  }

  function setStatusFilter(status: StatusFilter) {
    statusFilter = status;
    rowLimits = {};
  }

  function setHardwareFilter(value: string) {
    hardwareFilter = value;
    rowLimits = {};
  }

  function setSearchText(value: string) {
    searchText = value;
    rowLimits = {};
  }

  function dateText(value: string | null): string {
    if (value === null) return "-";
    return new Date(value).toLocaleString();
  }

  function numberText(value: number | null): string {
    return value === null ? "-" : formatNumber(value);
  }

  function unitText(value: string | null): string {
    return value ?? "-";
  }

  function percentText(row: ReportComparison): string {
    const pairwise = row.analysis?.pairwise ?? null;
    if (pairwise === null) {
      return "-";
    }
    const rounded = Number(pairwise.percent_change.toFixed(1));
    const display = Object.is(rounded, -0) ? 0 : rounded;
    return `${display > 0 ? "+" : ""}${display.toFixed(1)}%`;
  }

  function zText(row: ReportComparison): string {
    const lookback = row.analysis?.lookback_z_score ?? null;
    return lookback === null ? "-" : lookback.z_score.toFixed(2);
  }

  function reportStatusLabel(value: string): string {
    return value.replaceAll("_", " ");
  }

  function statusLabel(status: RowStatus): string {
    return STATUS_LABELS[status];
  }

  function rowLimit(runID: string): number {
    if (!Object.prototype.hasOwnProperty.call(rowLimits, runID)) {
      return CI_REPORT_INITIAL_ROWS;
    }
    return rowLimits[runID] ?? CI_REPORT_INITIAL_ROWS;
  }

  function showMore(runID: string) {
    rowLimits = { ...rowLimits, [runID]: rowLimit(runID) + CI_REPORT_ROW_CHUNK };
  }

  async function jumpToIssue(e: MouseEvent, target: IssueTarget) {
    if (!interceptNavClick(e)) return;
    e.preventDefault();
    rowLimits = { ...rowLimits, [target.runID]: Math.max(rowLimit(target.runID), target.rowIndex + 1) };
    await tick();
    history.replaceState(null, "", `${location.pathname}${location.search}${target.href}`);
    document.getElementById(target.anchor)?.scrollIntoView?.({ block: "center" });
  }

  function filtersActive(): boolean {
    return statusFilter !== "all" || hardwareFilter !== "all" || searchText.trim() !== "";
  }

  function rowCountText(visible: number, filtered: number, total: number): string {
    const matching = filtersActive() ? " matching" : "";
    const suffix = filtered !== total ? ` (filtered from ${total.toLocaleString()})` : "";
    return `showing ${visible.toLocaleString()} of ${filtered.toLocaleString()}${matching} comparisons${suffix}`;
  }

  function plural(n: number, word: string, pluralWord = `${word}s`): string {
    return `${n.toLocaleString()} ${n === 1 ? word : pluralWord}`;
  }

  function anchorID(runID: string, row: ReportComparison): string {
    return `ci-row-${token(row.status)}-${token(runID)}-${token(row.history_fingerprint)}`;
  }

  function token(value: string): string {
    return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "x";
  }
</script>

{#if !ready}
  <main class="page ci-report-page explain">
    <h1>CI report</h1>
    <p>Open a CI report URL with a commit selector or run IDs.</p>
  </main>
{:else if errorMsg}
  <main class="page ci-report-page"><p class="error">Failed to load CI report: {errorMsg}</p></main>
{:else if !report}
  <main class="page ci-report-page"><p>Loading...</p></main>
{:else}
  {@const r = report}
  <main class="page ci-report-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">CI Report</p>
        <h1>{r.repository || "Run selection"}</h1>
        <p class="page-subtitle">{r.status_reason}</p>
      </div>
      <div class="page-meta">
        {#if r.commit_sha}<span>commit {r.commit_sha}</span>{/if}
        <span>baseline {r.baseline}</span>
        <span class={`report-status ${r.status}`}>{reportStatusLabel(r.status)}</span>
      </div>
    </header>

    <p class="summary-line" aria-label="CI report summary">
      <span class="summary-item">{plural(r.summary.runs, "run")}</span>
      <span class="summary-item">{plural(r.summary.contender_results, "contender result")}</span>
      <span class="summary-item">{plural(r.summary.compared, "comparison")}</span>
      <span class="summary-item" class:alert={r.summary.regressions > 0}>{plural(r.summary.regressions, "regression")}</span>
      <span class="summary-item">{filteredComparisons.length} shown</span>
    </p>

    <section class="panel controls-panel" aria-label="CI report controls">
      <div class="status-tabs" aria-label="Filter comparisons by status">
        <button type="button" aria-pressed={statusFilter === "all"} onclick={() => setStatusFilter("all")}>
          <span>all</span>
          <strong>{allComparisons.length.toLocaleString()}</strong>
        </button>
        {#each STATUS_FILTERS as status}
          <button
            type="button"
            aria-pressed={statusFilter === status}
            onclick={() => setStatusFilter(status)}
          >
            <span>{statusLabel(status)}</span>
            <strong>{statusCounts[status].toLocaleString()}</strong>
          </button>
        {/each}
      </div>
      <div class="field-row">
        <label>
          Search comparisons
          <input
            aria-label="Search comparisons"
            type="search"
            value={searchText}
            placeholder="benchmark, fingerprint, run, hardware"
            oninput={(e) => setSearchText(e.currentTarget.value)}
          />
        </label>
        <label>
          Hardware
          <select
            aria-label="Hardware"
            value={hardwareFilter}
            onchange={(e) => setHardwareFilter(e.currentTarget.value)}
          >
            <option value="all">All hardware</option>
            {#each hardwareOptions as hardware}
              <option value={hardware}>{hardware}</option>
            {/each}
          </select>
        </label>
      </div>
    </section>

    {#if issueTargets.length > 0}
      <section class="issue-queue" aria-label="Investigation queue">
        <header>
          <span class="eyebrow">Investigation queue</span>
          <strong>{plural(issueTargets.reduce((sum, target) => sum + target.count, 0), "actionable comparison")}</strong>
        </header>
        <div class="issue-grid">
          {#each issueTargets as target}
            <a class={`issue-card ${target.status}`} href={target.href} onclick={(e) => jumpToIssue(e, target)}>
              <span class={`row-status ${target.status}`}>{target.label}</span>
              <strong>{target.benchmark}</strong>
              <span>{target.hardware}</span>
              <span>delta {target.delta} · z {target.z}</span>
              {#if target.reason}<span class="reason">{target.reason}</span>{/if}
              <span class="jump">Jump to {target.label} ({target.count.toLocaleString()})</span>
            </a>
          {/each}
        </div>
      </section>
    {/if}

    {#if r.missing_run_ids && r.missing_run_ids.length > 0}
      <section class="panel notice">
        <h2>Missing runs</h2>
        <p>{r.missing_run_ids.join(", ")}</p>
      </section>
    {/if}

    {#if filteredRuns.length === 0}
      <section class="panel empty-panel">
        <h2>No comparisons match the current filters</h2>
      </section>
    {:else}
      {#each filteredRuns as entry (entry.run.run_id)}
        {@const run = entry.run}
        {@const comparisons = entry.comparisons}
        {@const visibleComparisons = comparisons.slice(0, rowLimit(run.run_id))}
        {@const runCounts = countStatuses(comparisons)}
        {@const totalComparisons = runComparisons(run).length}
        <section class="panel run" aria-label={`Run ${run.run_id}`}>
          <header class="run-head">
            <div>
              <h2>{run.run_id}</h2>
              <div class="ident">
                {#if run.run_reason}<span>{run.run_reason}</span>{/if}
                {#if run.commit}<span>{run.commit.sha}</span>{/if}
                {#if run.baseline_run_id}<span>baseline {run.baseline_run_id}</span>{/if}
              </div>
            </div>
            <div class="run-summary" aria-label={`Summary for ${run.run_id}`}>
              <span>{plural(comparisons.length, "matching comparison")}</span>
              <span>{runCounts.regressed.toLocaleString()} regressed</span>
              <span>{runCounts.errored.toLocaleString()} benchmark {runCounts.errored === 1 ? "error" : "errors"}</span>
              <span>{runCounts.missing_baseline.toLocaleString()} missing baseline</span>
            </div>
          </header>

          {#if run.baseline_error}
            <p class="notice-line">{run.baseline_error.message}</p>
          {/if}

          {#if comparisons.length > 0}
            <p class="row-count">
              {rowCountText(visibleComparisons.length, comparisons.length, totalComparisons)}
            </p>
            <div class="comparison-list">
              <table class="data-table comparisons">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Benchmark</th>
                    <th>Hardware</th>
                    <th>Unit</th>
                    <th>Delta</th>
                    <th>Z</th>
                    <th>Contender</th>
                    <th>Baseline</th>
                    <th>Links</th>
                  </tr>
                </thead>
                <tbody>
                  {#each visibleComparisons as row}
                    <tr id={anchorID(run.run_id, row)} class={`row-${row.status}`}>
                      <td data-label="Status"><span class={`row-status ${row.status}`}>{statusLabel(row.status)}</span></td>
                      <td data-label="Benchmark">
                        <div class="bench-name">{row.name}</div>
                        <div class="fingerprint">{row.history_fingerprint}</div>
                      </td>
                      <td data-label="Hardware">{row.hardware.name}</td>
                      <td data-label="Unit">{unitText(row.unit)}</td>
                      <td data-label="Delta" class="num">{percentText(row)}</td>
                      <td data-label="Z" class="num">{zText(row)}</td>
                      <td data-label="Contender" class="num">{numberText(row.contender.single_value_summary)}</td>
                      <td data-label="Baseline" class="num">{numberText(row.baseline?.single_value_summary ?? null)}</td>
                      <td data-label="Links" class="links">
                        <a href={row.links.result} onclick={(e) => go(e, row.links.result)}>result</a>
                        {#if row.links.compare}
                          <a href={row.links.compare} onclick={(e) => go(e, row.links.compare!)}>compare</a>
                        {/if}
                        <a href={row.links.series} onclick={(e) => go(e, row.links.series)}>series</a>
                      </td>
                    </tr>
                    {#if row.status === "errored" && row.contender.error}
                      <tr class="detail-row"><td></td><td colspan="8"><code>{JSON.stringify(row.contender.error)}</code></td></tr>
                    {:else if row.reason}
                      <tr class="detail-row"><td></td><td colspan="8">{row.reason}</td></tr>
                    {:else if row.baseline}
                      <tr class="detail-row">
                        <td></td>
                        <td colspan="8">
                          contender {dateText(row.contender.commit_timestamp)}; baseline {dateText(row.baseline.commit_timestamp)}
                        </td>
                      </tr>
                    {/if}
                  {/each}
                </tbody>
              </table>
            </div>
            {#if visibleComparisons.length < comparisons.length}
              <button type="button" class="button-pill more" onclick={() => showMore(run.run_id)}>Show more</button>
            {/if}
          {:else}
            <p class="empty">No comparison rows.</p>
          {/if}
        </section>
      {/each}
    {/if}
  </main>
{/if}

<style>
  .ci-report-page {
    gap: 12px;
  }
  .report-status, .row-status {
    display: inline-flex;
    align-items: center;
    min-height: 20px;
    border-radius: 999px;
    padding: 0 8px;
    font-size: 0.72rem;
    color: var(--c-on-badge);
    background: var(--c-unknown);
  }
  .report-status.success, .row-status.improved {
    background: var(--c-success);
  }
  .report-status.failure, .row-status.regressed, .row-status.errored {
    background: var(--c-error);
  }
  .report-status.action_required, .row-status.missing_baseline, .row-status.not_comparable {
    background: var(--c-warning);
  }
  .report-status.skipped, .row-status.insufficient {
    background: var(--c-insufficient);
    color: var(--c-text-muted);
  }
  .row-status.stable {
    background: var(--c-stable);
  }
  .controls-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 10px;
  }
  .status-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .status-tabs button {
    min-height: 30px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 0 9px;
    border: 1px solid var(--c-border-muted);
    border-radius: var(--radius-sm);
    background: var(--c-surface);
    color: var(--c-text-muted);
    cursor: pointer;
    font-weight: 650;
  }
  .status-tabs button[aria-pressed="true"] {
    border-color: var(--c-accent);
    color: var(--c-accent);
    background: color-mix(in srgb, var(--c-accent) 8%, var(--c-surface));
  }
  .status-tabs strong {
    color: var(--c-text);
    font-variant-numeric: tabular-nums;
  }
  .field-row {
    display: grid;
    grid-template-columns: minmax(220px, 1fr) minmax(180px, 260px);
    gap: 10px;
  }
  .field-row label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    color: var(--c-text-muted);
    font-size: 0.72rem;
    font-weight: 750;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .field-row input, .field-row select {
    min-height: 32px;
    padding: 0 8px;
    border: 1px solid var(--c-border-muted);
    border-radius: var(--radius-sm);
    background: var(--c-surface);
    color: var(--c-text);
    font-size: 0.82rem;
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
  }
  .issue-queue {
    display: grid;
    gap: 8px;
  }
  .issue-queue header {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: end;
  }
  .issue-queue header strong {
    color: var(--c-text-muted);
    font-size: 0.8rem;
    font-weight: 700;
  }
  .eyebrow {
    color: var(--c-text-muted);
    font-size: 0.72rem;
    font-weight: 750;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .issue-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
  }
  .issue-card {
    min-width: 0;
    display: grid;
    gap: 4px;
    padding: 10px;
    border: 1px solid var(--c-border-muted);
    border-left: 4px solid var(--c-warning);
    border-radius: var(--radius-sm);
    background: var(--c-surface);
    color: var(--c-text-muted);
    text-decoration: none;
    font-size: 0.78rem;
  }
  .issue-card.regressed, .issue-card.errored {
    border-left-color: var(--c-error);
  }
  .issue-card:hover {
    border-color: var(--c-accent);
  }
  .issue-card strong {
    min-width: 0;
    color: var(--c-text);
    overflow-wrap: anywhere;
  }
  .issue-card .row-status {
    justify-self: start;
  }
  .issue-card .reason {
    overflow-wrap: anywhere;
  }
  .issue-card .jump {
    color: var(--c-accent);
    font-weight: 700;
  }
  .notice {
    padding: 12px;
    background: var(--c-warn-bg);
    color: var(--c-warn-text);
  }
  .notice h2 {
    margin-bottom: 4px;
    font-size: 0.95rem;
  }
  .notice p {
    margin: 0;
  }
  .run {
    overflow: hidden;
  }
  .run-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    padding: 12px;
    border-bottom: 1px solid var(--c-border-muted);
  }
  .run h2 {
    margin: 0 0 4px;
    font-size: 1rem;
  }
  .ident {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    color: var(--c-text-muted);
    font-size: 0.78rem;
  }
  .run-summary {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 6px;
    color: var(--c-text-muted);
    font-size: 0.74rem;
  }
  .run-summary span {
    min-height: 24px;
    display: inline-flex;
    align-items: center;
    padding: 0 7px;
    border: 1px solid var(--c-border-muted);
    border-radius: 999px;
    background: var(--c-bg-inset);
  }
  .notice-line {
    margin: 10px 12px 0;
    color: var(--c-warn-text);
    background: var(--c-warn-bg);
    border-radius: var(--radius-sm);
    padding: 8px;
  }
  .row-count {
    margin: 10px 12px 6px;
    color: var(--c-text-muted);
    font-size: 0.78rem;
  }
  .comparison-list {
    max-width: 100%;
  }
  .comparisons td {
    overflow-wrap: anywhere;
  }
  .row-regressed td, .row-errored td {
    background: color-mix(in srgb, var(--c-error) 5%, transparent);
  }
  .row-missing_baseline td, .row-not_comparable td {
    background: color-mix(in srgb, var(--c-warning) 5%, transparent);
  }
  .bench-name {
    font-weight: 700;
  }
  .fingerprint {
    color: var(--c-text-faint);
    font-size: 0.72rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .num {
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .links {
    white-space: nowrap;
  }
  .links a {
    margin-right: 7px;
    color: var(--c-accent);
  }
  .detail-row td {
    color: var(--c-text-muted);
    font-size: 0.76rem;
    background: var(--c-bg-inset);
  }
  .more {
    margin: 10px 12px 12px;
  }
  .empty-panel {
    padding: 18px;
  }
  .empty-panel h2 {
    margin: 0;
    font-size: 0.96rem;
  }
  .empty, .error {
    color: var(--c-text-muted);
  }
  .error {
    color: var(--c-error);
  }
  @media (max-width: 1080px) {
    .issue-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .run-head {
      flex-direction: column;
    }
    .run-summary {
      justify-content: flex-start;
    }
  }
  @media (max-width: 820px) {
    .field-row {
      grid-template-columns: 1fr;
    }
    .comparisons {
      min-width: 0;
    }
    .comparisons, .comparisons thead, .comparisons tbody, .comparisons tr, .comparisons th, .comparisons td {
      display: block;
    }
    .comparisons thead {
      display: none;
    }
    .comparisons tr {
      padding: 8px 10px;
      border-bottom: 1px solid var(--c-border-muted);
    }
    .comparisons td {
      display: grid;
      grid-template-columns: 88px minmax(0, 1fr);
      gap: 8px;
      padding: 4px 0;
      border-bottom: 0;
    }
    .comparisons td::before {
      content: attr(data-label);
      color: var(--c-text-muted);
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      font-weight: 750;
    }
    .detail-row td:first-child {
      display: none;
    }
  }
  @media (max-width: 560px) {
    .issue-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
