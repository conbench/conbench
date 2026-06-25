<script lang="ts">
  import { onMount } from "svelte";

  import { createConbenchClient } from "../api/client";
  import { loadRunPage, type RunPageViewModel, type RunResultRow } from "../run/loader";
  import { interceptNavClick, navigate } from "../router";

  let {
    runId,
    baseUrl = "",
  }: {
    runId: string;
    baseUrl?: string;
  } = $props();

  const client = $derived(createConbenchClient(baseUrl));

  let vm = $state<RunPageViewModel | null>(null);
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
      vm = await loadRunPage(client, runId);
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
      const page = await loadRunPage(client, runId, vm.nextCursor);
      const rows = [...vm.rows, ...page.rows];
      const loaded = loadedWindow(rows);
      vm = {
        ...vm,
        rows,
        loadedResults: vm.loadedResults + page.loadedResults,
        loadedErrors: vm.loadedErrors + page.loadedErrors,
        loadedSeries: unionCount(vm.rows, page.rows, (row) => row.historyFingerprint),
        loadedBatches: unionCount(vm.rows, page.rows, (row) => row.batchId ?? ""),
        firstLoadedAt: loaded.firstLoadedAt,
        lastLoadedAt: loaded.lastLoadedAt,
        nextCursor: page.nextCursor,
      };
    } catch (err) {
      moreErrorMsg = err instanceof Error ? err.message : String(err);
    } finally {
      loadingMore = false;
    }
  }

  function unionCount<T>(left: T[], right: T[], key: (row: T) => string): number {
    const keys = new Set([...left, ...right].map(key).filter(Boolean));
    return keys.size;
  }

  function loadedWindow(rows: RunResultRow[]): Pick<RunPageViewModel, "firstLoadedAt" | "lastLoadedAt"> {
    const timestamps = rows.map((row) => row.timestamp).sort();
    return {
      firstLoadedAt: timestamps[0] ?? null,
      lastLoadedAt: timestamps[timestamps.length - 1] ?? null,
    };
  }

  function go(e: MouseEvent, href: string) {
    if (!interceptNavClick(e)) return;
    e.preventDefault();
    navigate(href);
  }

  function goCIReport(e: MouseEvent) {
    if (vm?.ciReportHref) {
      go(e, vm.ciReportHref);
    }
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

  function formatSVS(row: RunResultRow): string {
    if (row.singleValueSummary === null) return "not computed";
    const value = Number.isInteger(row.singleValueSummary)
      ? row.singleValueSummary.toLocaleString()
      : row.singleValueSummary.toLocaleString(undefined, { maximumSignificantDigits: 6 });
    return row.unit === null ? value : `${value} ${row.unit}`;
  }

  function plural(n: number, word: string, pluralWord = `${word}s`): string {
    return `${n.toLocaleString()} ${n === 1 ? word : pluralWord}`;
  }

  function tagSummary(tags: Record<string, unknown>): string[] {
    const priority = ["query_id", "suite", "dataset", "scale_factor", "format", "language", "engine"];
    return Object.entries(tags)
      .filter(([, value]) => value !== null && value !== undefined && value !== "")
      .sort(([left], [right]) => {
        const leftIndex = priority.indexOf(left);
        const rightIndex = priority.indexOf(right);
        if (leftIndex >= 0 || rightIndex >= 0) {
          return (leftIndex < 0 ? priority.length : leftIndex) - (rightIndex < 0 ? priority.length : rightIndex);
        }
        return left.localeCompare(right);
      })
      .slice(0, 4)
      .map(([key, value]) => `${key} ${String(value)}`);
  }
</script>

{#if errorMsg}
  <main class="page run-page"><p class="error">Failed to load run: {errorMsg}</p></main>
{:else if loading || vm === null}
  <main class="page run-page"><p>Loading…</p></main>
{:else if vm.rows.length === 0}
  <main class="page run-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Run Detail</p>
        <h1>Run <span class="id-heading mono">{runId}</span></h1>
      </div>
    </header>
    <section class="panel empty-panel">
      <h2>No results found for this run</h2>
      <p>Check the run_id or open the recent-runs dashboard.</p>
      <a href="/" onclick={(e) => go(e, "/")}>Recent runs</a>
    </section>
  </main>
{:else}
  <main class="page run-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">{vm.repositoryLabel}</p>
        <h1>{vm.primaryLabel}</h1>
        <p class="page-subtitle run-subtitle">
          <span>{vm.secondaryLabel}</span>
          {#if vm.authorLabel !== "unknown author"}
            <span>{vm.authorLabel}{vm.authorLogin ? ` @${vm.authorLogin}` : ""}</span>
          {/if}
        </p>
      </div>
      <div class="page-meta">
        <span class="wrap-anywhere">{vm.runReason ?? "reason not set"}</span>
        {#if vm.commitHref && vm.shortCommit}
          <a
            class="mono wrap-anywhere"
            href={vm.commitHref}
            aria-label={`Open commit ${vm.shortCommit} on GitHub`}
            target="_blank"
            rel="noreferrer"
          >{vm.shortCommit}</a>
        {:else}
          <span class="mono wrap-anywhere">{vm.shortCommit ?? "commit not set"}</span>
        {/if}
      </div>
    </header>

    <p class="summary-line" aria-label="Run summary">
      <span class="summary-item">
        {plural(vm.loadedResults, "result")}{vm.nextCursor === null ? "" : "+"}
      </span>
      <span class="summary-item" class:alert={vm.loadedErrors > 0}>{plural(vm.loadedErrors, "error")}</span>
      <span class="summary-item">{plural(vm.loadedSeries, "series", "series")}</span>
      <span class="summary-item">{plural(vm.loadedBatches, "batch", "batches")}</span>
    </p>

    <section class="panel context-panel" aria-label="Run context">
      <div class="key-value-grid">
        <dl class="key-value">
          <dt>repository</dt>
          <dd>{vm.repositoryLabel}</dd>
        </dl>
        <dl class="key-value">
          <dt>author</dt>
          <dd>
            <span class="author-inline">
              {#if vm.authorAvatar}
                <img src={vm.authorAvatar} alt="" loading="lazy" referrerpolicy="no-referrer" />
              {/if}
              <span>{vm.authorLabel}</span>
            </span>
          </dd>
        </dl>
        <dl class="key-value">
          <dt>commit</dt>
          <dd>
            {#if vm.commitHref && vm.shortCommit}
              <a
                class="mono"
                href={vm.commitHref}
                aria-label={`Open commit ${vm.shortCommit} on GitHub`}
                target="_blank"
                rel="noreferrer"
              >{vm.shortCommit}</a>
            {:else}
              <span class="mono">{vm.shortCommit ?? "not set"}</span>
            {/if}
          </dd>
        </dl>
        <dl class="key-value">
          <dt>run</dt>
          <dd class="mono wrap-anywhere" title={vm.runId}>{vm.displayRunId}</dd>
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
      <div class="context-actions action-row">
        {#if vm.ciReportHref}
          <a
            class="button-pill"
            href={vm.ciReportHref}
            aria-label={`Open CI report for run ${vm.runId}`}
            onclick={goCIReport}
          >CI report</a>
        {/if}
        <a class="button-pill" href="/series" onclick={(e) => go(e, "/series")}>Browse series</a>
      </div>
    </section>

    <section class="panel table-panel" aria-label="Run results">
      <table class="data-table stacked-table run-results-table">
        <colgroup>
          <col class="benchmark-col" />
          <col class="measure-col" />
          <col class="status-col" />
          <col class="batch-col" />
          <col class="time-col" />
          <col class="actions-col" />
        </colgroup>
        <thead>
          <tr>
            <th>Benchmark</th>
            <th>Measurement</th>
            <th>Status</th>
            <th>Batch</th>
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
                  {#each tagSummary(row.benchmarkTags) as tag}
                    <span class="tag-chip">{tag}</span>
                  {/each}
                </div>
              </td>
              <td data-label="Measurement">
                <strong>{formatSVS(row)}</strong>
                <span class="subtle-inline">{row.singleValueSummaryType}</span>
              </td>
              <td data-label="Status">
                <span class={`status-badge ${row.hasError ? "warning" : "success"}`}>
                  {row.hasError ? "error" : "ok"}
                </span>
              </td>
              <td data-label="Batch">
                {#if row.batchId && row.batchHref}
                  <a
                    class="mono"
                    href={row.batchHref}
                    aria-label={`Open batch ${row.batchId}`}
                    title={row.batchId}
                    onclick={(e) => go(e, row.batchHref!)}
                  >
                    {row.displayBatchId}
                  </a>
                {:else}
                  not set
                {/if}
              </td>
              <td data-label="Time">{formatTime(row.timestamp)}</td>
              <td data-label="Open">
                <div class="inline-actions table-actions">
                  <a
                    class="inline-action-link"
                    href={row.trendHref}
                    aria-label={`Open series trend for ${row.benchmarkName} result ${row.id}`}
                    onclick={(e) => go(e, row.trendHref)}
                  >Trend</a>
                  <a
                    class="inline-action-link"
                    href={row.resultHref}
                    aria-label={`Open result ${row.id}`}
                    onclick={(e) => go(e, row.resultHref)}
                  >Result</a>
                </div>
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
  .run-page {
    gap: 12px;
  }
  .id-heading {
    overflow-wrap: anywhere;
  }
  .run-subtitle {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 12px;
  }
  .run-results-table .benchmark-col {
    width: 38%;
  }
  .run-results-table .measure-col {
    width: 15%;
  }
  .run-results-table .status-col {
    width: 8%;
  }
  .run-results-table .batch-col {
    width: 18%;
  }
  .run-results-table .time-col {
    width: 11%;
  }
  .run-results-table .actions-col {
    width: 10%;
  }
  .row-metadata,
  .table-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 8px;
    min-width: 0;
  }
  .row-metadata {
    margin-top: 4px;
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
  .subtle-inline {
    color: var(--c-text-muted);
    font-size: 0.76rem;
    margin-left: 4px;
  }
  .author-inline {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .author-inline img {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: var(--c-surface-subtle);
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
  .context-actions {
    align-content: flex-start;
  }
  .window-range {
    display: flex;
    flex-wrap: wrap;
    gap: 0 6px;
  }
  @media (max-width: 1120px) {
    .context-panel {
      flex-direction: column;
    }
  }
</style>
