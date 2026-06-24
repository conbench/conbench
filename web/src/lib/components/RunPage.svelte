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
        <p class="eyebrow">Run Detail</p>
        <h1>Run <span class="id-heading mono">{vm.runId}</span></h1>
        <p class="page-subtitle">
          Inspect submitted results for one run_id, then jump to CI diagnostics, result detail, or series trends.
        </p>
      </div>
      <div class="page-meta">
        <span class="wrap-anywhere">{vm.runReason ?? "reason not set"}</span>
        <span class="mono wrap-anywhere">{vm.shortCommit ?? "commit not set"}</span>
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
          <col class="result-col" />
          <col class="status-col" />
          <col class="svs-col" />
          <col class="batch-col" />
          <col class="time-col" />
          <col class="series-col" />
        </colgroup>
        <thead>
          <tr>
            <th>Result</th>
            <th>Status</th>
            <th>SVS</th>
            <th>Batch</th>
            <th>Time</th>
            <th>Series</th>
          </tr>
        </thead>
        <tbody>
          {#each vm.rows as row (row.id)}
            <tr class:error-row={row.hasError}>
              <td data-label="Result">
                <a
                  class="row-primary-link mono"
                  href={row.resultHref}
                  onclick={(e) => go(e, row.resultHref)}
                >{row.id}</a>
              </td>
              <td data-label="Status">
                <span class={`status-badge ${row.hasError ? "warning" : "success"}`}>
                  {row.hasError ? "error" : "ok"}
                </span>
              </td>
              <td data-label="SVS">{formatSVS(row)} <span class="subtle-inline">{row.singleValueSummaryType}</span></td>
              <td data-label="Batch">
                {#if row.batchId && row.batchHref}
                  <a
                    class="mono"
                    href={row.batchHref}
                    onclick={(e) => go(e, row.batchHref!)}
                  >
                    {row.batchId}
                  </a>
                {:else}
                  not set
                {/if}
              </td>
              <td data-label="Time">{formatTime(row.timestamp)}</td>
              <td data-label="Series">
                <a
                  class="button-pill secondary"
                  href={row.trendHref}
                  aria-label={`Open series trend for result ${row.id}`}
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
  .run-page {
    gap: 12px;
  }
  .id-heading {
    overflow-wrap: anywhere;
  }
  .run-results-table .result-col {
    width: 26%;
  }
  .run-results-table .status-col {
    width: 10%;
  }
  .run-results-table .svs-col {
    width: 17%;
  }
  .run-results-table .batch-col {
    width: 21%;
  }
  .run-results-table .time-col {
    width: 14%;
  }
  .run-results-table .series-col {
    width: 12%;
  }
  .subtle-inline {
    color: var(--c-text-muted);
    font-size: 0.76rem;
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
