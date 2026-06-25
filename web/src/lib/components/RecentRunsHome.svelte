<script lang="ts">
  import { onMount } from "svelte";

  import { createConbenchClient } from "../api/client";
  import { listRecentRuns, type RecentRunViewModel } from "../home/loader";
  import { interceptNavClick, navigate } from "../router";

  let { baseUrl = "" }: { baseUrl?: string } = $props();

  const client = $derived(createConbenchClient(baseUrl));

  let runs = $state<RecentRunViewModel[]>([]);
  let loading = $state(true);
  let errorMsg = $state<string | null>(null);

  onMount(() => {
    void load();
  });

  async function load() {
    loading = true;
    errorMsg = null;
    try {
      const page = await listRecentRuns(client);
      runs = page.runs;
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  const totalResults = $derived(runs.reduce((sum, run) => sum + run.resultCount, 0));
  const totalErrors = $derived(runs.reduce((sum, run) => sum + run.errorCount, 0));
  const repositoryLabels = $derived(uniqueRepositoryLabels(runs));
  const showReasonColumn = $derived(runs.some((run) => (run.runReason ?? "").trim() !== ""));
  const showRepositoryColumn = $derived(repositoryLabels.length > 1);
  const showErrorsColumn = $derived(totalErrors > 0);

  function go(e: MouseEvent, href: string) {
    if (!interceptNavClick(e)) return;
    e.preventDefault();
    navigate(href);
  }

  function formatTime(value: string): string {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(value));
  }

  function plural(n: number, word: string, pluralWord = `${word}s`): string {
    return `${n.toLocaleString()} ${n === 1 ? word : pluralWord}`;
  }

  function uniqueRepositoryLabels(source: RecentRunViewModel[]): string[] {
    const labels = new Map<string, string>();
    for (const run of source) {
      if (run.repository === "") continue;
      labels.set(run.repository, run.repositoryLabel);
    }
    return Array.from(labels.values()).sort();
  }

  function repositorySummary(labels: string[]): string {
    if (labels.length === 0) return "repository not set";
    if (labels.length === 1) return `repository ${labels[0]}`;
    return plural(labels.length, "repository", "repositories");
  }
</script>

<main class="page home-page">
  <header class="page-header">
    <div>
      <p class="eyebrow">Activity</p>
      <h1>Recent runs</h1>
      <p class="page-subtitle">
        Start from the latest benchmark activity, then jump into CI reports, sample results, or the series explorer.
      </p>
    </div>
    <div class="page-meta">
      <span>Grouped by run_id</span>
      <span>Newest first</span>
    </div>
  </header>

  {#if errorMsg}
    <p class="error">Failed to load recent runs: {errorMsg}</p>
  {:else if loading}
    <p>Loading…</p>
  {:else if runs.length === 0}
    <section class="panel empty-panel">
      <h2>No recent runs</h2>
      <p>Submitted benchmark results will appear here once a run is available.</p>
      <a href="/series" onclick={(e) => go(e, "/series")}>Browse benchmark series</a>
    </section>
  {:else}
    <p class="summary-line" aria-label="Recent run summary">
      <span class="summary-item">{plural(runs.length, "run")}</span>
      <span class="summary-item">{plural(totalResults, "result")}</span>
      {#if showErrorsColumn}
        <span class="summary-item alert">{plural(totalErrors, "error")}</span>
      {/if}
      <span class="summary-item">{repositorySummary(repositoryLabels)}</span>
    </p>

    <section class="panel table-panel" aria-label="Recent runs">
      <table class="data-table stacked-table runs-table">
        <colgroup>
          <col class="run-col" />
          {#if showReasonColumn}
            <col class="reason-col" />
          {/if}
          {#if showRepositoryColumn}
            <col class="repository-col" />
          {/if}
          <col class="commit-col" />
          <col class="count-col" />
          <col class="count-col" />
          {#if showErrorsColumn}
            <col class="count-col" />
          {/if}
          <col class="time-col" />
          <col class="actions-col" />
        </colgroup>
        <thead>
          <tr>
            <th>Run</th>
            {#if showReasonColumn}
              <th>Reason</th>
            {/if}
            {#if showRepositoryColumn}
              <th>Repository</th>
            {/if}
            <th>Commit</th>
            <th>Results</th>
            <th>Series</th>
            {#if showErrorsColumn}
              <th>Errors</th>
            {/if}
            <th>Latest</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each runs as run (run.runId)}
            <tr class:error-row={run.errorCount > 0}>
              <td data-label="Run">
                <div class="identity-stack">
                  <a
                    class="row-primary-link mono"
                    href={run.runHref}
                    aria-label={`Open run ${run.runId}`}
                    title={run.runId}
                    onclick={(e) => go(e, run.runHref)}
                  >
                    {run.displayRunId}
                  </a>
                  {#if run.latestBatchId}
                    <div class="meta-line">
                      {#if run.latestBatchHref}
                        <a
                          class="muted-detail batch-link"
                          href={run.latestBatchHref}
                          aria-label={`Open batch ${run.latestBatchId}`}
                          title={run.latestBatchId}
                          onclick={(e) => go(e, run.latestBatchHref!)}
                        >batch {run.displayLatestBatchId}</a>
                      {:else}
                        <span class="muted-detail" title={run.latestBatchId}>batch {run.displayLatestBatchId}</span>
                      {/if}
                      {#if run.batchCount > 1}
                        <span class="muted-detail">{run.batchCount - 1} earlier {run.batchCount === 2 ? "batch" : "batches"}</span>
                      {/if}
                    </div>
                  {/if}
                </div>
              </td>
              {#if showReasonColumn}
                <td data-label="Reason" class="wrap-anywhere">{run.runReason ?? "not set"}</td>
              {/if}
              {#if showRepositoryColumn}
                <td data-label="Repository">
                  <span class="mono value-code" title={run.repository || "not set"}>{run.repositoryLabel}</span>
                </td>
              {/if}
              <td data-label="Commit">
                <span class="mono value-code">{run.shortCommit ?? "not set"}</span>
              </td>
              <td data-label="Results" class="numeric">{run.resultCount.toLocaleString()}</td>
              <td data-label="Series" class="numeric">{run.seriesCount.toLocaleString()}</td>
              {#if showErrorsColumn}
                <td data-label="Errors">
                  {#if run.errorCount > 0}
                    <span class="status-badge warning">
                      {run.errorCount.toLocaleString()}
                    </span>
                  {/if}
                </td>
              {/if}
              <td data-label="Latest" class="time-cell">{formatTime(run.lastResultAt)}</td>
              <td data-label="Actions">
                <div class="inline-actions table-actions">
                  {#if run.ciReportHref}
                    <a
                      class="inline-action-link"
                      href={run.ciReportHref}
                      aria-label={`Open CI report for run ${run.runId}`}
                      onclick={(e) => go(e, run.ciReportHref!)}
                    >CI report</a>
                  {/if}
                  <a
                    class="inline-action-link"
                    href={run.latestResultHref}
                    aria-label={`Open sample result for run ${run.runId}`}
                    onclick={(e) => go(e, run.latestResultHref)}
                  >Sample result</a>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}
</main>

<style>
  .home-page {
    gap: 12px;
  }
  .runs-table {
    --stacked-label-width: 88px;
  }
  .runs-table .run-col {
    width: 20%;
  }
  .runs-table .reason-col {
    width: 11%;
  }
  .runs-table .repository-col {
    width: 19%;
  }
  .runs-table .commit-col {
    width: 9%;
  }
  .runs-table .count-col {
    width: 6%;
  }
  .runs-table .time-col {
    width: 10%;
  }
  .runs-table .actions-col {
    width: 13%;
  }
  .identity-stack {
    display: grid;
    gap: 4px;
    min-width: 0;
  }
  .meta-line,
  .table-actions {
    min-width: 0;
  }
  .inline-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 2px 8px;
  }
  .inline-action-link {
    color: var(--c-accent);
    font-weight: 650;
    text-decoration: none;
    white-space: nowrap;
  }
  .inline-action-link:hover {
    color: var(--c-accent-strong);
    text-decoration: underline;
  }
  .inline-action-link + .inline-action-link::before {
    content: "·";
    margin-right: 8px;
    color: var(--c-border);
    font-weight: 400;
    text-decoration: none;
  }
  .meta-line {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 3px 7px;
  }
  .muted-detail {
    color: var(--c-text-faint);
    font-size: 0.72rem;
    line-height: 1.25;
    overflow-wrap: anywhere;
  }
  .batch-link {
    text-decoration: none;
  }
  .batch-link:hover {
    color: var(--c-accent);
  }
  .value-code {
    display: inline-block;
    max-width: 100%;
    overflow-wrap: anywhere;
  }
  .numeric {
    text-align: right;
  }
  .time-cell {
    color: var(--c-text-muted);
    white-space: nowrap;
  }
  @media (max-width: 1120px) {
    .numeric {
      text-align: left;
    }
    .time-cell {
      white-space: normal;
    }
  }
</style>
