<script lang="ts">
  import { onMount } from "svelte";

  import { createConbenchClient } from "../api/client";
  import { formatMeasurement } from "../format";
  import {
    loadBatchPage,
    type BatchPageViewModel,
    type BatchResultRow,
    type BatchRunGroup,
  } from "../batch/loader";
  import { interceptNavClick, navigate } from "../router";

  let {
    batchId,
    baseUrl = "",
  }: {
    batchId: string;
    baseUrl?: string;
  } = $props();

  const client = $derived(createConbenchClient(baseUrl));

  let vm = $state<BatchPageViewModel | null>(null);
  let loading = $state(true);
  let loadingMore = $state(false);
  let errorMsg = $state<string | null>(null);
  let moreErrorMsg = $state<string | null>(null);

  onMount(() => {
    void load();
  });

  async function load() {
    loading = true;
    errorMsg = null;
    try {
      vm = await loadBatchPage(client, batchId);
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  async function loadMore() {
    if (vm === null || vm.nextCursor === null || loadingMore) return;
    loadingMore = true;
    moreErrorMsg = null;
    try {
      const current = vm;
      const page = await loadBatchPage(client, batchId, current.nextCursor);
      const rows = [...current.rows, ...page.rows];
      const loaded = loadedWindow(rows);
      vm = {
        ...current,
        rows,
        loadedResults: rows.length,
        loadedErrors: rows.filter((row) => row.hasError).length,
        loadedRuns: new Set(rows.map((row) => row.runId)).size,
        loadedSeries: new Set(rows.map((row) => row.historyFingerprint)).size,
        firstLoadedAt: loaded.firstLoadedAt,
        lastLoadedAt: loaded.lastLoadedAt,
        runGroups: mergeRunGroups(current.runGroups, page.runGroups),
        nextCursor: page.nextCursor,
      };
    } catch (err) {
      moreErrorMsg = err instanceof Error ? err.message : String(err);
    } finally {
      loadingMore = false;
    }
  }

  function go(e: MouseEvent, href: string) {
    if (!interceptNavClick(e)) return;
    e.preventDefault();
    navigate(href);
  }

  function formatTime(value: string | null): string {
    if (value === null) return "not set";
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(value));
  }

  function formatSVS(row: BatchResultRow): string {
    return formatMeasurement(row.singleValueSummary, row.unit, "not computed");
  }

  function tagText(tag: { key: string; value: string }): string {
    return `${tag.key} ${tag.value}`;
  }

  function mergeRunGroups(left: BatchRunGroup[], right: BatchRunGroup[]): BatchRunGroup[] {
    const merged = new Map(
      left.map((run) => [run.runId, { ...run, historyFingerprints: [...run.historyFingerprints] }]),
    );
    for (const run of right) {
      const existing = merged.get(run.runId);
      if (existing === undefined) {
        merged.set(run.runId, { ...run, historyFingerprints: [...run.historyFingerprints] });
      } else {
        const historyFingerprints = new Set([...existing.historyFingerprints, ...run.historyFingerprints]);
        existing.resultCount += run.resultCount;
        existing.errorCount += run.errorCount;
        existing.historyFingerprints = Array.from(historyFingerprints);
        existing.seriesCount = existing.historyFingerprints.length;
        existing.firstLoadedAt =
          existing.firstLoadedAt <= run.firstLoadedAt ? existing.firstLoadedAt : run.firstLoadedAt;
        existing.lastLoadedAt =
          existing.lastLoadedAt >= run.lastLoadedAt ? existing.lastLoadedAt : run.lastLoadedAt;
      }
    }
    return Array.from(merged.values());
  }

  function loadedWindow(rows: BatchResultRow[]): Pick<BatchPageViewModel, "firstLoadedAt" | "lastLoadedAt"> {
    const timestamps = rows.map((row) => row.timestamp).sort();
    return {
      firstLoadedAt: timestamps[0] ?? null,
      lastLoadedAt: timestamps[timestamps.length - 1] ?? null,
    };
  }

  function plural(n: number, word: string, pluralWord = `${word}s`): string {
    return `${n.toLocaleString()} ${n === 1 ? word : pluralWord}`;
  }
</script>

{#if errorMsg}
  <main class="page batch-page"><p class="error">Failed to load batch: {errorMsg}</p></main>
{:else if loading || vm === null}
  <main class="page batch-page"><p>Loading…</p></main>
{:else if vm.rows.length === 0}
  <main class="page batch-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Batch Detail</p>
        <h1>Batch <span class="id-heading mono">{batchId}</span></h1>
      </div>
    </header>
    <section class="panel empty-panel">
      <h2>No results found for this batch</h2>
      <p>Check the batch_id or open the recent-runs dashboard.</p>
      <a class="button-pill" href="/" onclick={(e) => go(e, "/")}>Recent runs</a>
    </section>
  </main>
{:else}
  <main class="page batch-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Batch Detail</p>
        <h1>Batch <span class="id-heading mono">{vm.batchId}</span></h1>
        <p class="page-subtitle">
          Inspect one batch_id across runs, then jump to run detail, CI reports, result detail, or series trends.
        </p>
      </div>
      <div class="page-meta">
        <span class="mono wrap-anywhere">{vm.shortCommit ?? "commit not set"}</span>
        <span>{vm.nextCursor === null ? "all loaded" : "more available"}</span>
      </div>
    </header>

    <p class="summary-line" aria-label="Batch summary">
      <span class="summary-item">{plural(vm.loadedResults, "result")}</span>
      <span class="summary-item">{plural(vm.loadedRuns, "run")}</span>
      <span class="summary-item" class:alert={vm.loadedErrors > 0}>{plural(vm.loadedErrors, "error")}</span>
      <span class="summary-item">{plural(vm.loadedSeries, "series", "series")}</span>
    </p>

    <section class="panel context-panel" aria-label="Batch context">
      <div class="key-value-grid">
        <dl class="key-value">
          <dt>repository</dt>
          <dd class="mono">{vm.repository || "not set"}</dd>
        </dl>
        <dl class="key-value">
          <dt>commit</dt>
          <dd class="mono">{vm.commitSha ?? "not set"}</dd>
        </dl>
        <dl class="key-value">
          <dt>loaded window</dt>
          <dd class="window-range">
            <span>{formatTime(vm.firstLoadedAt)}</span>
            <span>to</span>
            <span>{formatTime(vm.lastLoadedAt)}</span>
          </dd>
        </dl>
      </div>
      <a class="button-pill" href="/series" onclick={(e) => go(e, "/series")}>Browse series</a>
    </section>

    <section class="panel table-panel" aria-label="Runs in batch">
      <table class="data-table stacked-table batch-runs-table">
        <colgroup>
          <col class="run-col" />
          <col class="reason-col" />
          <col class="commit-col" />
          <col class="count-col" />
          <col class="count-col" />
          <col class="count-col" />
          <col class="actions-col" />
        </colgroup>
        <thead>
          <tr>
            <th>Run</th>
            <th>Reason</th>
            <th>Commit</th>
            <th>Results</th>
            <th>Series</th>
            <th>Errors</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each vm.runGroups as run (run.runId)}
            <tr class:error-row={run.errorCount > 0}>
              <td data-label="Run">
                <a
                  class="row-primary-link mono"
                  href={run.runHref}
                  aria-label={`Open run ${run.runId}`}
                  title={run.runId}
                  onclick={(e) => go(e, run.runHref)}
                >{run.displayRunId}</a>
              </td>
              <td data-label="Reason" class="wrap-anywhere">{run.runReason ?? "not set"}</td>
              <td data-label="Commit"><span class="mono value-code">{run.shortCommit ?? "not set"}</span></td>
              <td data-label="Results" class="numeric">{run.resultCount.toLocaleString()}</td>
              <td data-label="Series" class="numeric">{run.seriesCount.toLocaleString()}</td>
              <td data-label="Errors">
                <span class={`status-badge ${run.errorCount > 0 ? "warning" : "stable"}`}>
                  {run.errorCount.toLocaleString()}
                </span>
              </td>
              <td data-label="Actions">
                <div class="action-row table-actions">
                  {#if run.ciReportHref}
                    <a
                      class="button-pill"
                      href={run.ciReportHref}
                      aria-label={`Open CI report for run ${run.runId}`}
                      onclick={(e) => go(e, run.ciReportHref!)}
                    >CI report</a>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>

    <section class="panel table-panel" aria-label="Batch results">
      <table class="data-table stacked-table batch-results-table">
        <colgroup>
          <col class="benchmark-col" />
          <col class="svs-col" />
          <col class="status-col" />
          <col class="run-col" />
          <col class="time-col" />
          <col class="series-col" />
        </colgroup>
        <thead>
          <tr>
            <th>Benchmark</th>
            <th>Measurement</th>
            <th>Status</th>
            <th>Run</th>
            <th>Time</th>
            <th>Open</th>
          </tr>
        </thead>
        <tbody>
          {#each vm.rows as row (row.id)}
            <tr class:error-row={row.hasError}>
              <td data-label="Benchmark">
                <a
                  class="row-primary-link"
                  href={row.resultHref}
                  aria-label={`Open result ${row.id} for ${row.benchmarkName}`}
                  onclick={(e) => go(e, row.resultHref)}
                >{row.benchmarkName}</a>
                <div class="row-metadata">
                  <span class="muted-detail mono" title={row.id}>result {row.displayResultId}</span>
                  {#each row.primaryTags as tag}
                    <span class="tag-chip">{tagText(tag)}</span>
                  {/each}
                </div>
              </td>
              <td data-label="Measurement" class="numeric">
                <strong>{formatSVS(row)}</strong>
                <span class="subtle-inline">{row.singleValueSummaryType}</span>
              </td>
              <td data-label="Status">
                <span class={`status-badge ${row.hasError ? "warning" : "success"}`}>
                  {row.hasError ? "error" : "ok"}
                </span>
              </td>
              <td data-label="Run">
                <a
                  class="mono"
                  href={row.runHref}
                  aria-label={`Open run ${row.runId}`}
                  title={row.runId}
                  onclick={(e) => go(e, row.runHref)}
                >{row.displayRunId}</a>
              </td>
              <td data-label="Time">{formatTime(row.timestamp)}</td>
              <td data-label="Open">
                <a
                  class="button-pill secondary"
                  href={row.trendHref}
                  aria-label={`trend for ${row.benchmarkName} result ${row.id}`}
                  onclick={(e) => go(e, row.trendHref)}
                >
                  Series trend
                </a>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>

    {#if moreErrorMsg}
      <p class="error">Failed to load more: {moreErrorMsg}</p>
    {/if}
    {#if vm.nextCursor !== null}
      <button type="button" class="button-pill more" onclick={loadMore} disabled={loadingMore}>
        {loadingMore ? "Loading…" : "Load more"}
      </button>
    {/if}
  </main>
{/if}

<style>
  .batch-page {
    gap: 12px;
  }
  .id-heading {
    overflow-wrap: anywhere;
  }
  .batch-runs-table .run-col {
    width: 24%;
  }
  .batch-runs-table .reason-col {
    width: 18%;
  }
  .batch-runs-table .commit-col {
    width: 12%;
  }
  .batch-runs-table .count-col {
    width: 8%;
  }
  .batch-runs-table .actions-col {
    width: 22%;
  }
  .batch-results-table .benchmark-col {
    width: 38%;
  }
  .batch-results-table .run-col {
    width: 16%;
  }
  .batch-results-table .status-col {
    width: 10%;
  }
  .batch-results-table .svs-col {
    width: 14%;
  }
  .batch-results-table .time-col {
    width: 14%;
  }
  .batch-results-table .series-col {
    width: 12%;
  }
  .subtle-inline {
    color: var(--c-text-muted);
    font-size: 0.76rem;
    margin-left: 4px;
  }
  .context-panel {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    padding: 12px;
  }
  .context-panel .key-value-grid {
    flex: 1;
    min-width: 0;
  }
  .window-range {
    display: flex;
    flex-wrap: wrap;
    gap: 0 6px;
  }
  .value-code {
    display: inline-block;
    max-width: 100%;
    overflow-wrap: anywhere;
  }
  .numeric {
    text-align: right;
  }
  .table-actions {
    min-width: 0;
  }
  .row-metadata {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 8px;
    min-width: 0;
    margin-top: 4px;
  }
  .muted-detail {
    color: var(--c-text-faint);
    font-size: 0.72rem;
  }
  .tag-chip {
    color: var(--c-text-muted);
    background: var(--c-surface-subtle);
    border: 1px solid var(--c-border);
    border-radius: 999px;
    padding: 1px 6px;
    font-size: 0.68rem;
    line-height: 1.35;
  }
  @media (max-width: 1120px) {
    .context-panel {
      flex-direction: column;
    }
    .numeric {
      text-align: left;
    }
  }
</style>
