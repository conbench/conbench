<script lang="ts">
  import { untrack } from "svelte";

  import { createConbenchClient } from "../api/client";
  import { listSeries } from "../browse/loader";
  import type { BrowseRow } from "../browse/transform";
  import { defaultPair, toCommitChoices, type CommitChoice } from "../compare/benchmark-picker";
  import { loadCompare, NotComparableError, type CompareViewModel } from "../compare/loader";
  import { lookbackText, pairwiseText } from "../compare/transform";
  import { loadTrend } from "../series/loader";
  import {
    DEFAULT_BROWSE_QUERY,
    formatCompareQuery,
    interceptNavClick,
    navigate,
    type CompareQuery,
  } from "../router";
  import SeriesChart from "./SeriesChart.svelte";
  import StatusBadge from "./StatusBadge.svelte";

  let {
    query,
    baseUrl = "",
  }: {
    query: CompareQuery;
    baseUrl?: string;
  } = $props();

  // baseUrl is a fixed prop; $derived rebuilds the client only if it ever
  // changes, which silences Svelte's "captures the initial value" warning.
  const client = $derived(createConbenchClient(baseUrl));

  let vm = $state<CompareViewModel | null>(null);
  let errorMsg = $state<string | null>(null);
  let notComparableMsg = $state<string | null>(null);

  // Benchmark-first picker: search a benchmark, then pick two of its commits.
  // Shown until a baseline+contender pair is in the URL (ready).
  let benchmarkQuery = $state("");
  let seriesResults = $state<BrowseRow[]>([]);
  let seriesLoading = $state(false);
  let seriesError = $state<string | null>(null);
  let selectedSeries = $state<BrowseRow | null>(null);
  let commitChoices = $state<CommitChoice[]>([]);
  let commitsLoading = $state(false);
  let commitsError = $state<string | null>(null);
  // Seed the picker from the URL so a one-sided link (/compare?baseline=b1)
  // preserves the supplied ID in the advanced result-ID flow instead of blanking
  // it. The App remounts this page when the pair changes, so capturing the
  // initial value (via untrack) is intentional and sufficient.
  let baselineID = $state(untrack(() => query.baseline));
  let contenderID = $state(untrack(() => query.contender));
  let showAdvanced = $state(false);

  let reqToken = 0;
  let searchToken = 0;
  let commitToken = 0;
  let searchTimer: ReturnType<typeof setTimeout> | undefined;

  let ready = $derived(query.baseline !== "" && query.contender !== "");
  let sameSelection = $derived(
    baselineID.trim() !== "" && baselineID.trim() === contenderID.trim(),
  );
  let canOpenCompare = $derived(
    baselineID.trim() !== "" && contenderID.trim() !== "" && !sameSelection,
  );

  // One load path: runs on mount and again when a threshold changes (the App
  // remounts the page when the PAIR changes). The token guards a stale slow
  // response; the current view-model stays rendered while the refetch is in
  // flight.
  $effect(() => {
    if (!ready) {
      return;
    }
    const snapshot = { ...query };
    const token = ++reqToken;
    loadCompare(client, snapshot)
      .then((loaded) => {
        if (token !== reqToken) return;
        vm = loaded;
        errorMsg = null;
        notComparableMsg = null;
      })
      .catch((err: unknown) => {
        if (token !== reqToken) return;
        if (err instanceof NotComparableError) {
          notComparableMsg = err.message;
          errorMsg = null;
        } else {
          errorMsg = err instanceof Error ? err.message : String(err);
          notComparableMsg = null;
        }
      });
  });

  function runSearch(q: string) {
    const token = ++searchToken;
    seriesLoading = true;
    seriesError = null;
    listSeries(client, { ...DEFAULT_BROWSE_QUERY, q })
      .then((page) => {
        if (token !== searchToken) return;
        seriesResults = page.rows;
      })
      .catch((err: unknown) => {
        if (token !== searchToken) return;
        seriesError = err instanceof Error ? err.message : String(err);
        seriesResults = [];
      })
      .finally(() => {
        if (token === searchToken) seriesLoading = false;
      });
  }

  function onSearchInput(value: string) {
    benchmarkQuery = value;
    clearTimeout(searchTimer);
    const q = value.trim();
    if (q === "") {
      // Cancel any in-flight search and clear the list.
      searchToken++;
      seriesResults = [];
      seriesLoading = false;
      seriesError = null;
      return;
    }
    searchTimer = setTimeout(() => runSearch(q), 250);
  }

  function selectSeries(row: BrowseRow) {
    selectedSeries = row;
    baselineID = "";
    contenderID = "";
    commitChoices = [];
    commitsError = null;
    commitsLoading = true;
    const token = ++commitToken;
    loadTrend(client, { kind: "fingerprint", fingerprint: row.fingerprint })
      .then((trend) => {
        if (token !== commitToken) return;
        const choices = toCommitChoices(trend.points, trend.identity.unit);
        commitChoices = choices;
        const pair = defaultPair(choices);
        if (pair !== null) {
          baselineID = pair.baselineId;
          contenderID = pair.contenderId;
        }
      })
      .catch((err: unknown) => {
        if (token !== commitToken) return;
        commitsError = err instanceof Error ? err.message : String(err);
      })
      .finally(() => {
        if (token === commitToken) commitsLoading = false;
      });
  }

  function clearSeries() {
    selectedSeries = null;
    commitChoices = [];
    baselineID = "";
    contenderID = "";
    commitsError = null;
  }

  // Picking a row already used by the other side swaps the two selections rather
  // than rejecting the click, so a two-row picker can still reverse the pair.
  function pickBaseline(id: string) {
    if (contenderID === id) contenderID = baselineID;
    baselineID = id;
  }

  function pickContender(id: string) {
    if (baselineID === id) baselineID = contenderID;
    contenderID = id;
  }

  function setThreshold(patch: Partial<CompareQuery>) {
    navigate(`/compare${formatCompareQuery({ ...query, ...patch })}`);
  }

  function openCompare() {
    if (!canOpenCompare) return;
    navigate(
      `/compare${formatCompareQuery({
        baseline: baselineID.trim(),
        contender: contenderID.trim(),
        threshold: query.threshold,
        thresholdZ: query.thresholdZ,
      })}`,
    );
  }

  /** positive parses a threshold input; junk or non-positive values mean
   * "back to the server default" (null), matching parseCompareQuery. */
  function positive(value: string): number | null {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? n : null;
  }

  function go(e: MouseEvent, href: string) {
    if (!interceptNavClick(e)) return;
    e.preventDefault();
    navigate(href);
  }
</script>

{#if !ready}
  <main class="page compare-page">
    <header class="page-header">
      <div>
        <h1>Compare benchmark results</h1>
      </div>
    </header>

    {#if selectedSeries === null}
      <section class="panel picker-step" aria-label="Choose a benchmark">
        <div class="step-head">
          <span class="step-num" aria-hidden="true">1</span>
          <h2>Choose a benchmark</h2>
        </div>
        <label class="sr-only" for="compare-benchmark-search">Search benchmarks</label>
        <input
          id="compare-benchmark-search"
          class="text-input"
          type="search"
          placeholder="Search benchmarks by name, tag, or context"
          autocomplete="off"
          spellcheck="false"
          value={benchmarkQuery}
          oninput={(e) => onSearchInput(e.currentTarget.value)}
        />
        {#if seriesLoading}
          <p class="hint">Searching…</p>
        {:else if seriesError}
          <p class="error">{seriesError}</p>
        {:else if benchmarkQuery.trim() === ""}
          <p class="hint">Start typing to find a benchmark to compare.</p>
        {:else if seriesResults.length === 0}
          <p class="hint">No benchmarks match “{benchmarkQuery.trim()}”.</p>
        {:else}
          <ul class="series-results">
            {#each seriesResults as row (row.fingerprint)}
              <li>
                <button type="button" class="series-option" onclick={() => selectSeries(row)}>
                  <span class="series-name">{row.name}</span>
                  <span class="series-meta">
                    {[row.paramsText, row.hardwareName, `${row.pointCount} points`, `latest ${row.svsText}`]
                      .filter((part) => part !== "")
                      .join(" · ")}
                  </span>
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </section>
    {:else}
      <section class="panel picker-step selected-benchmark" aria-label="Selected benchmark">
        <div class="step-head">
          <span class="step-num done" aria-hidden="true">✓</span>
          <div>
            <h2>{selectedSeries.name}</h2>
            <p class="series-meta">
              {[selectedSeries.paramsText, selectedSeries.hardwareName]
                .filter((part) => part !== "")
                .join(" · ")}
            </p>
          </div>
        </div>
        <button type="button" class="button-pill" onclick={clearSeries}>Change benchmark</button>
      </section>

      <section class="panel picker-step" aria-label="Pick two commits">
        <div class="step-head">
          <span class="step-num" aria-hidden="true">2</span>
          <h2>Pick two commits</h2>
        </div>
        {#if commitsLoading}
          <p class="hint">Loading commits…</p>
        {:else if commitsError}
          <p class="error">{commitsError}</p>
        {:else if commitChoices.length < 2}
          <p class="hint">This benchmark has fewer than two results — nothing to compare.</p>
        {:else}
          <div class="table-panel">
            <table class="commit-table">
              <thead>
                <tr>
                  <th scope="col">baseline</th>
                  <th scope="col">contender</th>
                  <th scope="col">commit</th>
                  <th scope="col">date</th>
                  <th scope="col" class="num">SVS</th>
                </tr>
              </thead>
              <tbody>
                {#each commitChoices as c (c.resultId)}
                  <tr class:is-baseline={baselineID === c.resultId} class:is-contender={contenderID === c.resultId}>
                    <td data-label="baseline">
                      <input
                        type="radio"
                        class="pick base"
                        name="compare-baseline"
                        checked={baselineID === c.resultId}
                        aria-label={`Use commit ${c.shortCommit} as baseline`}
                        onchange={() => pickBaseline(c.resultId)}
                      />
                    </td>
                    <td data-label="contender">
                      <input
                        type="radio"
                        class="pick cont"
                        name="compare-contender"
                        checked={contenderID === c.resultId}
                        aria-label={`Use commit ${c.shortCommit} as contender`}
                        onchange={() => pickContender(c.resultId)}
                      />
                    </td>
                    <td data-label="commit">
                      <span class="mono commit-sha">{c.shortCommit}</span>
                      {#if c.commitMessage !== ""}<span class="msg">{c.commitMessage}</span>{/if}
                    </td>
                    <td data-label="date">{c.dateText}</td>
                    <td data-label="SVS" class="num">{c.svsText}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
          <div class="compare-actions">
            <button type="button" class="button-pill primary" disabled={!canOpenCompare} onclick={openCompare}>
              Compare →
            </button>
            {#if sameSelection}
              <span class="hint">Baseline and contender must be different commits.</span>
            {/if}
          </div>
        {/if}
      </section>
    {/if}

    <section class="panel advanced" aria-label="Compare by result ID">
      <button
        type="button"
        class="disclosure"
        aria-expanded={showAdvanced}
        onclick={() => (showAdvanced = !showAdvanced)}
      >
        {showAdvanced ? "▾" : "▸"} Advanced: compare by result ID
      </button>
      {#if showAdvanced}
        <div class="result-inputs">
          <label class="field">
            Baseline result ID
            <input
              class="text-input"
              spellcheck="false"
              value={baselineID}
              oninput={(e) => (baselineID = e.currentTarget.value)}
            />
          </label>
          <label class="field">
            Contender result ID
            <input
              class="text-input"
              spellcheck="false"
              value={contenderID}
              oninput={(e) => (contenderID = e.currentTarget.value)}
            />
          </label>
          <button type="button" class="button-pill primary" disabled={!canOpenCompare} onclick={openCompare}>
            Open compare
          </button>
        </div>
      {/if}
    </section>
  </main>
{:else if notComparableMsg}
  <main class="page compare-page">
    <section class="panel state-panel" role="alert">
      <h1>Not comparable</h1>
      <p class="error">Not comparable: {notComparableMsg}</p>
    </section>
  </main>
{:else if errorMsg}
  <main class="page compare-page">
    <section class="panel state-panel">
      <h1>Comparison unavailable</h1>
      <p class="error">Failed to load comparison: {errorMsg}</p>
    </section>
  </main>
{:else if !vm}
  <main class="page compare-page">
    <section class="panel state-panel">
      <h1>Loading comparison</h1>
      <p>Loading...</p>
    </section>
  </main>
{:else}
  <!-- @const pins the narrowed view-model: TS narrowing on the nullable $state
       does not survive into the onclick closures (same pattern as TrendPage's
       selected strip). -->
  {@const m = vm}
  <main class="page compare-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Compare</p>
        <h1>Compare</h1>
        <p class="page-subtitle compare-subtitle">
          <span>{m.baseline.name}</span>
          {#if m.baseline.paramsText !== ""}<span>{m.baseline.paramsText}</span>{/if}
        </p>
      </div>
      <div class="header-actions">
        <div class="page-meta">
          <span>{m.unit} ({m.lessIsBetter ? "lower is better" : "higher is better"})</span>
          <span>{m.baseline.id} vs {m.contender.id}</span>
        </div>
        <div class="action-row">
          <a
            class="button-pill primary"
            href={`/series/${m.baseline.fingerprint}`}
            onclick={(e) => go(e, `/series/${m.baseline.fingerprint}`)}
          >View full trend</a>
        </div>
      </div>
    </header>

    <section class="panel verdict-panel" aria-label="Comparison verdict">
      <div class="verdict">
        <StatusBadge status={m.status} />
        <dl class="verdicts">
          <dt>lookback z</dt>
          <dd>{lookbackText(m.lookback)}</dd>
          <dt>pairwise</dt>
          <dd>{pairwiseText(m.pairwise)}</dd>
        </dl>
      </div>
    </section>

    <section class="panel controls threshold-panel" aria-label="Threshold controls">
      <label>
        threshold %
        <input
          type="number"
          min="0.1"
          step="0.1"
          value={query.threshold ?? 5}
          onchange={(e) => setThreshold({ threshold: positive(e.currentTarget.value) })}
        />
      </label>
      <label>
        threshold σ
        <input
          type="number"
          min="0.1"
          step="0.1"
          value={query.thresholdZ ?? 5}
          onchange={(e) => setThreshold({ thresholdZ: positive(e.currentTarget.value) })}
        />
      </label>
    </section>

    <section class="panel side-panel" aria-label="Baseline and contender">
      <div class="sides-list">
        <table class="sides">
          <thead>
            <tr><th></th><th>baseline</th><th>contender</th></tr>
          </thead>
          <tbody>
            <tr>
              <th>SVS</th>
              <td class="num" data-label="baseline">{m.baseline.svsText}</td>
              <td class="num" data-label="contender">{m.contender.svsText}</td>
            </tr>
            <tr>
              <th>commit</th>
              <td data-label="baseline">
                <span class="cell-value">
                  <a href={`/results/${m.baseline.id}`} onclick={(e) => go(e, `/results/${m.baseline.id}`)}>
                    {m.baseline.commitSha ?? "—"}
                  </a>
                  <span class="msg">{m.baseline.commitMessage ?? ""}</span>
                </span>
              </td>
              <td data-label="contender">
                <span class="cell-value">
                  <a href={`/results/${m.contender.id}`} onclick={(e) => go(e, `/results/${m.contender.id}`)}>
                    {m.contender.commitSha ?? "—"}
                  </a>
                  <span class="msg">{m.contender.commitMessage ?? ""}</span>
                </span>
              </td>
            </tr>
            <tr>
              <th>date</th>
              <td data-label="baseline">{m.baseline.commitDateText ?? "—"}</td>
              <td data-label="contender">{m.contender.commitDateText ?? "—"}</td>
            </tr>
            <tr>
              <th>run</th>
              <td data-label="baseline">{m.baseline.runId}{m.baseline.runReason ? ` (${m.baseline.runReason})` : ""}</td>
              <td data-label="contender">{m.contender.runId}{m.contender.runReason ? ` (${m.contender.runReason})` : ""}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel chart-panel" aria-label="Comparison trend">
      <SeriesChart points={m.points} height={160} markedIndices={m.marked} />
    </section>
  </main>
{/if}

<style>
  .compare-page {
    gap: 12px;
  }

  /* benchmark-first picker */
  .picker-step {
    padding: 14px;
  }
  .step-head {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
  }
  .step-num {
    width: 22px;
    height: 22px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
    border-radius: 999px;
    background: var(--c-accent-soft);
    color: var(--c-accent-strong);
    font-size: 0.72rem;
    font-weight: 800;
  }
  .step-num.done {
    background: var(--c-success-soft);
    color: var(--c-success);
  }
  .step-head h2 {
    margin: 0;
    font-size: 0.98rem;
  }
  .step-head .series-meta {
    margin: 1px 0 0;
  }

  .text-input {
    width: 100%;
    min-height: 34px;
    padding: 0 10px;
    border: 1px solid var(--c-border);
    border-radius: var(--radius-sm);
    background: var(--c-bg-inset);
    color: var(--c-text);
    font: inherit;
    font-size: 0.86rem;
  }
  .text-input::placeholder {
    color: var(--c-text-faint);
  }
  .text-input:focus-visible {
    outline: 2px solid var(--c-accent);
    outline-offset: 1px;
    border-color: var(--c-accent);
  }

  .hint {
    margin: 10px 0 0;
    color: var(--c-text-muted);
    font-size: 0.82rem;
  }
  .error {
    color: var(--c-error);
  }

  .series-results {
    list-style: none;
    margin: 12px 0 0;
    padding: 0;
    border: 1px solid var(--c-border-muted);
    border-radius: var(--radius-md);
    overflow: hidden;
  }
  .series-option {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    padding: 9px 12px;
    border: 0;
    border-bottom: 1px solid var(--c-border-muted);
    background: var(--c-surface);
    color: var(--c-text);
    text-align: left;
    cursor: pointer;
  }
  .series-results li:last-child .series-option {
    border-bottom: 0;
  }
  .series-option:hover {
    background: var(--c-row-hover);
  }
  .series-name {
    font-weight: 700;
    font-size: 0.88rem;
  }
  .series-meta {
    color: var(--c-text-muted);
    font-size: 0.76rem;
    overflow-wrap: anywhere;
  }

  .selected-benchmark {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .selected-benchmark .step-head {
    margin-bottom: 0;
  }

  .commit-table {
    width: 100%;
    border-collapse: collapse;
  }
  .commit-table th,
  .commit-table td {
    padding: 8px 10px;
    border-bottom: 1px solid var(--c-border-muted);
    text-align: left;
    vertical-align: middle;
  }
  .commit-table thead th {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--c-text-muted);
    background: var(--c-bg-inset);
    font-weight: 750;
  }
  .commit-table tbody tr:last-child td {
    border-bottom: 0;
  }
  .commit-table tbody tr:hover td {
    background: var(--c-row-hover);
  }
  .commit-table tr.is-baseline td {
    background: color-mix(in srgb, var(--c-accent) 8%, transparent);
  }
  .commit-table tr.is-contender td {
    background: color-mix(in srgb, var(--c-trend-mean) 10%, transparent);
  }
  .commit-sha {
    font-weight: 700;
  }
  .commit-table .pick {
    width: 16px;
    height: 16px;
    cursor: pointer;
  }
  .commit-table .pick.base {
    accent-color: var(--c-accent);
  }
  .commit-table .pick.cont {
    accent-color: var(--c-trend-mean);
  }
  .commit-table th.num,
  .commit-table td.num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .compare-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 14px;
  }

  .advanced {
    padding: 0;
  }
  .disclosure {
    width: 100%;
    padding: 11px 14px;
    border: 0;
    background: transparent;
    color: var(--c-text-muted);
    text-align: left;
    font-weight: 650;
    font-size: 0.8rem;
    cursor: pointer;
  }
  .disclosure:hover {
    color: var(--c-accent);
  }
  .advanced .result-inputs {
    padding: 0 14px 14px;
  }
  .result-inputs {
    display: grid;
    grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr) max-content;
    gap: 10px;
    align-items: end;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    color: var(--c-text-muted);
    font-size: 0.72rem;
    font-weight: 750;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .field .text-input {
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
  }

  /* loaded comparison view */
  .compare-subtitle {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .header-actions {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
  }
  .verdict-panel,
  .threshold-panel,
  .side-panel,
  .chart-panel {
    padding: 12px;
  }
  .verdict {
    display: flex;
    gap: 1rem;
    align-items: baseline;
    margin: 0.75rem 0;
  }
  .verdicts {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.2rem 1rem;
    font-size: 0.85rem;
    margin: 0;
  }
  .verdicts dt {
    color: var(--c-text-muted);
  }
  .verdicts dd {
    margin: 0;
    font-variant-numeric: tabular-nums;
  }
  .controls {
    display: flex;
    gap: 1rem;
    align-items: end;
    margin: 0.75rem 0;
    flex-wrap: wrap;
  }
  .controls label {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    font-size: 0.72rem;
    color: var(--c-text-muted);
    text-transform: uppercase;
    letter-spacing: 0;
  }
  .controls input {
    font-size: 0.85rem;
    padding: 0.25rem 0.4rem;
    width: 5rem;
    border: 1px solid var(--c-border);
    border-radius: 4px;
    background: var(--c-bg-inset);
    color: var(--c-text);
  }
  .sides-list {
    max-width: 100%;
  }
  .sides {
    border-collapse: collapse;
    margin: 0.75rem 0 1rem;
    font-size: 0.85rem;
  }
  .sides th,
  .sides td {
    text-align: left;
    padding: 0.3rem 0.8rem 0.3rem 0;
    border-bottom: 1px solid var(--c-border);
    overflow-wrap: anywhere;
  }
  .sides thead th {
    color: var(--c-text-muted);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0;
  }
  .sides tbody th {
    color: var(--c-text-muted);
    font-weight: 400;
  }
  .sides a {
    color: inherit;
    font-weight: 600;
    text-decoration: none;
  }
  .sides a:hover {
    color: var(--c-accent);
  }
  .cell-value {
    display: block;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .msg {
    display: block;
    color: var(--c-text-faint);
    font-size: 0.72rem;
  }
  .num {
    font-variant-numeric: tabular-nums;
  }

  @media (max-width: 760px) {
    .result-inputs {
      grid-template-columns: 1fr;
    }
    .selected-benchmark {
      flex-direction: column;
      align-items: stretch;
    }
    .commit-table,
    .commit-table thead,
    .commit-table tbody,
    .commit-table tr,
    .commit-table th,
    .commit-table td {
      display: block;
    }
    .commit-table thead {
      display: none;
    }
    .commit-table tr {
      padding: 8px;
      border-bottom: 1px solid var(--c-border-muted);
    }
    .commit-table td {
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr);
      gap: 8px;
      padding: 4px 0;
      border-bottom: 0;
    }
    .commit-table td::before {
      content: attr(data-label);
      color: var(--c-text-muted);
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      font-weight: 750;
    }
    .commit-table td.num {
      text-align: left;
    }
    .sides,
    .sides thead,
    .sides tbody,
    .sides tr,
    .sides th,
    .sides td {
      display: block;
    }
    .sides thead {
      display: none;
    }
    .sides tr {
      padding: 0.55rem 0;
      border-bottom: 1px solid var(--c-border);
    }
    .sides th,
    .sides td {
      border-bottom: 0;
      padding: 0.15rem 0;
    }
    .sides tbody th {
      color: var(--c-text);
      font-weight: 600;
    }
    .sides td {
      display: grid;
      grid-template-columns: minmax(5.5rem, 34%) 1fr;
      gap: 0.65rem;
    }
    .sides td::before {
      content: attr(data-label);
      color: var(--c-text-muted);
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0;
    }
  }
</style>
