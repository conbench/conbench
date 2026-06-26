<script lang="ts">
  import { createConbenchClient } from "../api/client";
  import { formatMeasurement } from "../format";
  import {
    loadResultsPage,
    type ResultListRow,
    type ResultsPageViewModel,
  } from "../results/loader";
  import {
    formatResultListQuery,
    interceptNavClick,
    navigate,
    type ResultListQuery,
  } from "../router";

  let {
    query,
    baseUrl = "",
  }: {
    query: ResultListQuery;
    baseUrl?: string;
  } = $props();

  const client = $derived(createConbenchClient(baseUrl));

  let vm = $state<ResultsPageViewModel | null>(null);
  let loading = $state(true);
  let loadingMore = $state(false);
  let errorMsg = $state<string | null>(null);
  let moreErrorMsg = $state<string | null>(null);
  let reqToken = 0;

  let runID = $state("");
  let batchID = $state("");
  let runReason = $state("");
  let earliestTimestamp = $state("");
  let latestTimestamp = $state("");
  let exactFiltersOpen = $state(false);

  $effect(() => {
    runID = query.runID;
    batchID = query.batchID;
    runReason = query.runReason;
    earliestTimestamp = utcToDatetimeLocal(query.earliestTimestamp);
    latestTimestamp = utcToDatetimeLocal(query.latestTimestamp);
    void load(query);
  });

  async function load(q: ResultListQuery) {
    const token = ++reqToken;
    loading = true;
    loadingMore = false;
    errorMsg = null;
    moreErrorMsg = null;
    vm = null;
    try {
      const page = await loadResultsPage(client, { query: q, cursor: null });
      if (token !== reqToken) return;
      vm = page;
    } catch (err) {
      if (token !== reqToken) return;
      errorMsg = err instanceof Error ? err.message : String(err);
    } finally {
      if (token === reqToken) loading = false;
    }
  }

  async function loadMore() {
    if (vm === null || vm.nextCursor === null || loadingMore) return;
    const token = reqToken;
    loadingMore = true;
    moreErrorMsg = null;
    try {
      const page = await loadResultsPage(client, { query, cursor: vm.nextCursor });
      if (token !== reqToken) return;
      vm = summarizeRows([...vm.rows, ...page.rows], page.nextCursor);
    } catch (err) {
      if (token !== reqToken) return;
      moreErrorMsg = err instanceof Error ? err.message : String(err);
    } finally {
      if (token === reqToken) loadingMore = false;
    }
  }

  function summarizeRows(rows: ResultListRow[], nextCursor: string | null): ResultsPageViewModel {
    return {
      rows,
      nextCursor,
      loadedResults: rows.length,
      loadedRuns: new Set(rows.map((row) => row.runId)).size,
      loadedBatches: new Set(rows.map((row) => row.batchId).filter(Boolean)).size,
      loadedErrors: rows.filter((row) => row.hasError).length,
      loadedSeries: new Set(rows.map((row) => row.historyFingerprint)).size,
    };
  }

  function submitFilters(e: SubmitEvent) {
    e.preventDefault();
    navigate(`/results${formatResultListQuery(currentFilterQuery())}`);
  }

  function currentFilterQuery(): ResultListQuery {
    return {
      runID: runID.trim(),
      batchID: batchID.trim(),
      runReason: runReason.trim(),
      earliestTimestamp: datetimeLocalToUTC(earliestTimestamp),
      latestTimestamp: datetimeLocalToUTC(latestTimestamp),
    };
  }

  function clearFilter(patch: Partial<ResultListQuery>) {
    navigate(`/results${formatResultListQuery({ ...query, ...patch })}`);
  }

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

  function utcToDatetimeLocal(value: string): string {
    if (value.trim() === "") return "";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "";
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  }

  function datetimeLocalToUTC(value: string): string {
    const trimmed = value.trim();
    if (trimmed === "") return "";
    return `${trimmed.length === 16 ? `${trimmed}:00` : trimmed}Z`;
  }

  function formatTimestampFilter(value: string): string {
    const localValue = utcToDatetimeLocal(value);
    return localValue === "" ? value : `${localValue.replace("T", " ")} UTC`;
  }

  function formatSVS(row: ResultListRow): string {
    return formatMeasurement(row.singleValueSummary, row.unit, "not computed");
  }

  function tagText(tag: { key: string; value: string }): string {
    return `${tag.key} ${tag.value}`;
  }

  function plural(n: number, word: string, pluralWord = `${word}s`): string {
    return `${n.toLocaleString()} ${n === 1 ? word : pluralWord}`;
  }

  let activeFilters = $derived([
    ...(query.runID !== ""
      ? [{ label: "run id", value: query.runID, clear: { runID: "" }, aria: `Remove run id filter ${query.runID}` }]
      : []),
    ...(query.batchID !== ""
      ? [{ label: "batch id", value: query.batchID, clear: { batchID: "" }, aria: `Remove batch id filter ${query.batchID}` }]
      : []),
    ...(query.runReason !== ""
      ? [{
          label: "run reason",
          value: query.runReason,
          clear: { runReason: "" },
          aria: `Remove run reason filter ${query.runReason}`,
        }]
      : []),
    ...(query.earliestTimestamp !== ""
      ? [{
          label: "earliest",
          value: formatTimestampFilter(query.earliestTimestamp),
          clear: { earliestTimestamp: "" },
          aria: `Remove earliest timestamp filter ${query.earliestTimestamp}`,
        }]
      : []),
    ...(query.latestTimestamp !== ""
      ? [{
          label: "latest",
          value: formatTimestampFilter(query.latestTimestamp),
          clear: { latestTimestamp: "" },
          aria: `Remove latest timestamp filter ${query.latestTimestamp}`,
        }]
      : []),
  ]);
</script>

<main class="page results-page">
  <header class="page-header">
    <div>
      <p class="eyebrow">Result Explorer</p>
      <h1>Benchmark results</h1>
      <p class="page-subtitle">
        Browse submitted benchmark measurements by case, commit, run, or exact IDs when needed.
      </p>
    </div>
    {#if vm !== null}
      <div class="page-meta">
        <span>{plural(vm.loadedResults, "loaded result")}</span>
        {#if vm.nextCursor !== null}<span>More available</span>{/if}
      </div>
    {/if}
  </header>

  <div class="filter-toolbar">
    <button
      type="button"
      class="button-pill secondary"
      aria-expanded={exactFiltersOpen}
      onclick={() => (exactFiltersOpen = !exactFiltersOpen)}
    >
      Exact result filters
    </button>
    {#if activeFilters.length > 0}
      <a class="button-pill secondary" href="/results" onclick={(e) => go(e, "/results")}>Clear</a>
    {/if}
  </div>

  {#if exactFiltersOpen}
    <section class="panel filter-disclosure" aria-label="Exact result filters">
      <form class="results-filters" onsubmit={submitFilters}>
        <label class="filter-label">
          Run ID
          <input type="text" bind:value={runID} placeholder="paste run id" autocomplete="off" />
        </label>
        <label class="filter-label">
          Batch ID
          <input type="text" bind:value={batchID} placeholder="paste batch id" autocomplete="off" />
        </label>
        <label class="filter-label">
          Run reason
          <input type="text" bind:value={runReason} placeholder="commit" autocomplete="off" />
        </label>
        <label class="filter-label">
          Earliest result time (UTC)
          <input type="datetime-local" bind:value={earliestTimestamp} />
        </label>
        <label class="filter-label">
          Latest result time (UTC)
          <input type="datetime-local" bind:value={latestTimestamp} />
        </label>
        <div class="filter-actions">
          <button type="submit" class="button-pill">Apply exact filters</button>
          <a class="button-pill secondary" href="/results" onclick={(e) => go(e, "/results")}>Clear</a>
        </div>
      </form>
    </section>
  {/if}

  {#if activeFilters.length > 0}
    <div class="active-filters" role="group" aria-label="Active result filters">
      {#each activeFilters as filter (filter)}
        <button type="button" class="filter-chip" aria-label={filter.aria} onclick={() => clearFilter(filter.clear)}>
          <span class="chip-label">{filter.label}</span>
          <span class="chip-value">{filter.value}</span>
          <span class="chip-x" aria-hidden="true">&times;</span>
        </button>
      {/each}
    </div>
  {/if}

  {#if errorMsg}
    <section class="panel state-panel error-panel" role="alert">
      <h2>Failed to load results</h2>
      <p>{errorMsg}</p>
    </section>
  {:else if loading || vm === null}
    <section class="panel state-panel loading-panel" aria-live="polite">
      <h2>Loading benchmark results</h2>
      <p>Loading...</p>
    </section>
  {:else if vm.rows.length === 0}
    <section class="panel state-panel empty-panel" aria-label="No matching benchmark results">
      <h2>No benchmark results match the current filters</h2>
      <p>Clear the filters or open the series explorer to find a result from a benchmark family.</p>
      <a class="button-pill" href="/series" onclick={(e) => go(e, "/series")}>Browse series</a>
    </section>
  {:else}
    <p class="summary-line" aria-label="Result list summary">
      <span class="summary-item">
        {plural(vm.loadedResults, "result")}{vm.nextCursor === null ? "" : "+"}
      </span>
      <span class="summary-item">{plural(vm.loadedRuns, "run")}</span>
      <span class="summary-item">{plural(vm.loadedBatches, "batch", "batches")}</span>
      <span class="summary-item" class:alert={vm.loadedErrors > 0}>{plural(vm.loadedErrors, "error")}</span>
      <span class="summary-item">{plural(vm.loadedSeries, "series", "series")}</span>
    </p>

    <section class="panel table-panel" aria-label="Benchmark results">
      <table class="data-table stacked-table results-table">
        <colgroup>
          <col class="benchmark-col" />
          <col class="svs-col" />
          <col class="status-col" />
          <col class="run-col" />
          <col class="batch-col" />
          <col class="commit-col" />
          <col class="time-col" />
          <col class="series-col" />
        </colgroup>
        <thead>
          <tr>
            <th>Benchmark</th>
            <th>Measurement</th>
            <th>Status</th>
            <th>Run</th>
            <th>Batch</th>
            <th>Commit</th>
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
              <td class="numeric" data-label="Measurement">
                <strong>{formatSVS(row)}</strong>
                <span class="subtle-inline">{row.singleValueSummaryType}</span>
              </td>
              <td class="status-cell" data-label="Status">
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
                >run {row.displayRunId}</a>
                {#if row.runReason}
                  <div class="metadata-line">{row.runReason}</div>
                {/if}
              </td>
              <td data-label="Batch">
                {#if row.batchId && row.batchHref}
                  <a
                    class="mono"
                    href={row.batchHref}
                    aria-label={`Open batch ${row.batchId}`}
                    title={row.batchId}
                    onclick={(e) => go(e, row.batchHref!)}
                  >batch {row.displayBatchId}</a>
                {:else}
                  not set
                {/if}
              </td>
              <td class="commit-cell" data-label="Commit">
                <span class="identity-stack">
                  {#if row.commitSha !== null}
                    <span class="mono" title={row.commitSha}>{row.shortCommit}</span>
                  {:else}
                    <span>not set</span>
                  {/if}
                  {#if row.repository !== ""}
                    <span class="metadata-line" title={row.repository}>{row.repositoryLabel}</span>
                  {/if}
                </span>
              </td>
              <td class="time-cell" data-label="Time">{formatTime(row.timestamp)}</td>
              <td data-label="Series">
                <a
                  class="button-pill secondary"
                  href={row.trendHref}
                  aria-label={`trend for ${row.benchmarkName} result ${row.id}`}
                  onclick={(e) => go(e, row.trendHref)}
                >
                  Trend
                </a>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>

    {#if moreErrorMsg}
      <section class="panel state-panel error-panel" role="alert">
        <h2>Failed to load more</h2>
        <p>{moreErrorMsg}</p>
      </section>
    {/if}
    {#if vm.nextCursor !== null}
      <button type="button" class="button-pill more" onclick={loadMore} disabled={loadingMore}>
        {loadingMore ? "Loading…" : "Load more"}
      </button>
    {/if}
  {/if}
</main>

<style>
  .results-page {
    gap: 12px;
  }
  .filter-toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .filter-disclosure {
    padding: 0;
  }

  .results-filters {
    display: grid;
    grid-template-columns: repeat(5, minmax(130px, 1fr)) auto;
    gap: 10px;
    align-items: end;
    padding: 0 12px 12px;
  }

  .secondary {
    background: var(--c-surface);
    color: var(--c-text-muted);
  }
  .subtle-inline {
    color: var(--c-text-muted);
    font-size: 0.76rem;
  }

  .results-table {
    --stacked-label-width: 82px;
  }

  .benchmark-col {
    width: 30%;
  }

  .run-col {
    width: 16%;
  }

  .batch-col {
    width: 13%;
  }

  .status-col {
    width: 8%;
  }

  .svs-col {
    width: 13%;
  }

  .commit-col {
    width: 12%;
  }

  .time-col {
    width: 10%;
  }

  .series-col {
    width: 86px;
  }

  .identity-stack {
    display: grid;
    gap: 3px;
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

  .tag-chip {
    color: var(--c-text-muted);
    background: var(--c-surface-subtle);
    border: 1px solid var(--c-border);
    border-radius: 999px;
    padding: 1px 6px;
    font-size: 0.68rem;
    line-height: 1.35;
  }

  .metadata-line {
    color: var(--c-text-faint);
    font-size: 0.72rem;
    line-height: 1.3;
    overflow-wrap: anywhere;
  }

  .muted-detail {
    color: var(--c-text-faint);
    font-size: 0.72rem;
  }

  .numeric {
    font-variant-numeric: tabular-nums;
  }

  .time-cell,
  .status-cell {
    white-space: nowrap;
  }

  .error-panel h2 {
    color: var(--c-error);
  }

  @media (max-width: 1120px) {
    .results-filters {
      grid-template-columns: repeat(3, minmax(140px, 1fr));
    }
  }
  @media (max-width: 760px) {
    .results-filters {
      grid-template-columns: 1fr;
    }
    .time-cell,
    .status-cell {
      white-space: normal;
    }
  }
</style>
