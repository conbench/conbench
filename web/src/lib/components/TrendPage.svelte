<script lang="ts">
  import { onMount, tick } from "svelte";

  import { createConbenchClient } from "../api/client";
  import { formatMeasurement } from "../format";
  import { loadTrend, type TrendSource, type TrendViewModel } from "../series/loader";
  import {
    flagsText,
    type SeriesPoint,
    type TableRow,
    windowAnchorDate,
    windowPoints,
  } from "../series/transform";
  import {
    formatCompareQuery,
    formatTrendQuery,
    interceptNavClick,
    navigate,
    type BrowseWindow,
    type TrendAxis,
    type TrendQuery,
    type TrendSigma,
  } from "../router";
  import { tagsText } from "../browse/transform";
  import DetailTable from "./DetailTable.svelte";
  import SeriesChart from "./SeriesChart.svelte";

  let {
    source,
    query,
    baseUrl = "",
  }: {
    source: TrendSource;
    query: TrendQuery;
    baseUrl?: string;
  } = $props();

  const RANGE_LABEL: Record<BrowseWindow, string> = {
    all: "all time",
    "30d": "30 days",
    "3mo": "3 months",
    "1y": "year",
  };
  const TREND_TABLE_INITIAL_ROWS = 200;
  const TREND_TABLE_ROW_CHUNK = 200;
  type TrendFilter = "all" | "outliers" | "steps";
  type FlagTarget = {
    filter: Exclude<TrendFilter, "all">;
    label: string;
    count: number;
    index: number;
    point: SeriesPoint;
  };

  let vm = $state<TrendViewModel | null>(null);
  let errorMsg = $state<string | null>(null);
  let selectedIndex = $state<number | null>(null);
  let rowLimit = $state(TREND_TABLE_INITIAL_ROWS);
  let trendFilter = $state<TrendFilter>("all");
  let exportCopied = $state(false);

  onMount(async () => {
    try {
      vm = await loadTrend(createConbenchClient(baseUrl), source);
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : String(err);
    }
  });

  let all = $derived(vm?.points ?? []);
  let rangeAnchor = $derived(windowAnchorDate(all, new Date()));
  let visible = $derived(windowPoints(all, query.range, rangeAnchor));
  let outlierCount = $derived(visible.filter((p) => p.stats.isOutlier).length);
  let stepCount = $derived(visible.filter((p) => p.stats.isStep || p.stats.beginsChange).length);
  let flagTargets = $derived(flaggedPointTargets(visible));
  let rows = $derived(filteredTableRows(visible, trendFilter));
  let displayedRows = $derived(rows.slice(Math.max(0, rows.length - rowLimit)));
  let hiddenRowCount = $derived(Math.max(0, rows.length - displayedRows.length));
  let selected = $derived(selectedIndex === null ? null : (visible[selectedIndex] ?? null));
  let exportResultID = $derived(
    selected?.resultId ??
      (source.kind === "result" ? source.resultId : (visible[visible.length - 1]?.resultId ?? null)),
  );
  let exportServerURL = $derived(baseUrl !== "" ? baseUrl : browserOrigin());
  let exportCommand = $derived(
    exportResultID === null
      ? null
      : `conbench history export ${exportResultID} --server ${exportServerURL} --output history.csv`,
  );

  // Compare picks are page-local workflow state: the shareable artifact is the
  // /compare URL the bar produces, not the picking session. Picks reference
  // result ids, so range/axis/sigma changes never invalidate them.
  let baselinePick = $state<{ id: string; sha: string } | null>(null);
  let contenderPick = $state<{ id: string; sha: string } | null>(null);

  let compareHref = $derived(
    baselinePick !== null && contenderPick !== null
      ? `/compare${formatCompareQuery({
          baseline: baselinePick.id,
          contender: contenderPick.id,
          threshold: null,
          thresholdZ: null,
        })}`
      : null,
  );

  function clearPicks() {
    baselinePick = null;
    contenderPick = null;
  }

  // Range and table-filter changes re-window the selectable row set, so stale
  // indices would point at the wrong commit: reset the selection. Axis/sigma
  // keep indices stable.
  $effect(() => {
    void query.range;
    void trendFilter;
    selectedIndex = null;
    rowLimit = TREND_TABLE_INITIAL_ROWS;
    exportCopied = false;
  });

  $effect(() => {
    void exportCommand;
    exportCopied = false;
  });

  function basePath(): string {
    return source.kind === "fingerprint"
      ? `/series/${source.fingerprint}`
      : `/benchmarks/history/${source.resultId}`;
  }

  function setControl(patch: Partial<TrendQuery>) {
    navigate(`${basePath()}${formatTrendQuery({ ...query, ...patch })}`);
  }

  function select(index: number) {
    selectedIndex = index;
  }

  function openResult(resultId: string) {
    navigate(`/results/${resultId}`);
  }

  function browserOrigin(): string {
    if (typeof window === "undefined") return "";
    return window.location.origin;
  }

  function pointMatchesFilter(point: SeriesPoint, filter: TrendFilter): boolean {
    if (filter === "outliers") return point.stats.isOutlier;
    if (filter === "steps") return point.stats.isStep || point.stats.beginsChange;
    return true;
  }

  function filteredTableRows(points: SeriesPoint[], filter: TrendFilter): TableRow[] {
    return points.flatMap((point, index) => {
      if (!pointMatchesFilter(point, filter)) return [];
      return [
        {
          index,
          resultId: point.resultId,
          commitHash: point.commitHash,
          commitMessage: point.commitMessage,
          svs: point.svs,
          unit: point.unit,
          z: point.stats.z,
          flags: flagsText(point.stats),
        },
      ];
    });
  }

  function flaggedPointTargets(points: SeriesPoint[]): FlagTarget[] {
    const outliers = points
      .map((point, index) => ({ point, index }))
      .filter((entry) => entry.point.stats.isOutlier);
    const steps = points
      .map((point, index) => ({ point, index }))
      .filter((entry) => entry.point.stats.isStep || entry.point.stats.beginsChange);
    return [
      targetFor("outliers", "outlier", outliers),
      targetFor("steps", "step", steps),
    ].filter((target): target is FlagTarget => target !== null);
  }

  function targetFor(
    filter: Exclude<TrendFilter, "all">,
    label: string,
    entries: { point: SeriesPoint; index: number }[],
  ): FlagTarget | null {
    const first = entries[0];
    if (first === undefined) return null;
    return { filter, label, count: entries.length, index: first.index, point: first.point };
  }

  function zText(value: number | null): string {
    return value === null ? "z —" : `z ${value.toFixed(2)}`;
  }

  function rowCountText(): string {
    if (trendFilter === "all") {
      return `showing ${displayedRows.length} of ${rows.length} points`;
    }
    return `showing ${displayedRows.length} of ${rows.length} filtered points`;
  }

  async function copyExportCommand() {
    const command = exportCommand;
    if (command === null || navigator.clipboard === undefined) return;
    try {
      await navigator.clipboard.writeText(command);
      if (exportCommand === command) {
        exportCopied = true;
      }
    } catch {
      if (exportCommand === command) {
        exportCopied = false;
      }
    }
  }

  async function jumpToFlag(target: FlagTarget) {
    trendFilter = target.filter;
    rowLimit = TREND_TABLE_INITIAL_ROWS;
    await tick();
    selectedIndex = target.index;
  }

  function orientation(lessIsBetter: boolean | null): string | null {
    if (lessIsBetter === null) return null;
    return lessIsBetter ? "lower is better" : "higher is better";
  }
</script>

{#if errorMsg}
  <main class="page trend-page">
    <section class="panel state-panel">
      <h1>Trend unavailable</h1>
      <p class="error">Failed to load series: {errorMsg}</p>
    </section>
  </main>
{:else if !vm}
  <main class="page trend-page">
    <section class="panel state-panel">
      <h1>Loading trend</h1>
      <p>Loading...</p>
    </section>
  </main>
{:else}
  <main class="page trend-page">
    <section class="trend-context panel" aria-label="Trend context">
      <header class="page-header">
        <div>
          <p class="eyebrow">Trend detail</p>
          <h1>{vm.identity.benchmarkName}</h1>
          <div class="ident page-subtitle">
            {#if tagsText(vm.identity.caseTags) !== ""}<span>{tagsText(vm.identity.caseTags)}</span>{/if}
            {#if tagsText(vm.identity.context) !== ""}<span>{tagsText(vm.identity.context)}</span>{/if}
            <span>hardware: {vm.identity.hardwareName}</span>
            <span title={vm.identity.repository}>repo: {vm.identity.repositoryLabel}</span>
            {#if vm.identity.unit !== null}
              <span>
                unit: {vm.identity.unit}{orientation(vm.identity.lessIsBetter) !== null
                  ? ` (${orientation(vm.identity.lessIsBetter)})`
                  : ""}
              </span>
            {/if}
          </div>
        </div>
        <div class="page-meta">
          <span title={vm.identity.fingerprint}>series {vm.identity.displayFingerprint}</span>
          <span title={vm.identity.hardwareHash}>hardware {vm.identity.displayHardwareHash}</span>
        </div>
      </header>
      {#if !vm.unitConsistent}
        <div class="integrity" role="alert">
          data integrity: this series mixes units ({vm.units.join(", ")}) — values are
          not directly comparable
        </div>
      {/if}

    {#if all.length > 0}
    <div class="toolbar controls">
      <label class="filter-label">
        range
        <select
          value={query.range}
          onchange={(e) => setControl({ range: e.currentTarget.value as BrowseWindow })}
        >
          <option value="30d">last 30 days</option>
          <option value="3mo">last 3 months</option>
          <option value="1y">last year</option>
          <option value="all">all time</option>
        </select>
      </label>
      <label class="filter-label">
        band
        <select
          value={String(query.sigma)}
          onchange={(e) => setControl({ sigma: Number(e.currentTarget.value) as TrendSigma })}
        >
          <option value="1">±1σ</option>
          <option value="2">±2σ</option>
          <option value="3">±3σ</option>
          <option value="5">±5σ</option>
        </select>
      </label>
      <label class="filter-label">
        x-axis
        <select
          value={query.axis}
          onchange={(e) => setControl({ axis: e.currentTarget.value as TrendAxis })}
        >
          <option value="commit">commit order</option>
          <option value="time">time</option>
        </select>
      </label>
    </div>

    <p class="summary-line" aria-label="Trend summary">
      <span class="summary-item">{visible.length} {visible.length === 1 ? "point" : "points"}</span>
      <span class="summary-item">{outlierCount} {outlierCount === 1 ? "outlier" : "outliers"}</span>
      <span class="summary-item">{stepCount} {stepCount === 1 ? "step" : "steps"}</span>
    </p>

    {#if flagTargets.length > 0}
      <section class="flag-queue" aria-label="Flagged point shortcuts">
        {#each flagTargets as target}
          <button type="button" class="flag-card" onclick={() => jumpToFlag(target)}>
            <span>{target.count} {target.count === 1 ? target.label : `${target.label}s`}</span>
            <strong>{target.point.commitHash}</strong>
            <span class="numeric-text">{formatMeasurement(target.point.svs, target.point.unit)} · {zText(target.point.stats.z)}</span>
            <span class="jump">Jump to first {target.label}</span>
          </button>
        {/each}
      </section>
    {/if}

    <!-- The bar lives outside the windowed branch: picks are id-based and
         survive range changes, so switching to an empty window must not
         strand a pending comparison. -->
    {#if baselinePick !== null || contenderPick !== null}
      <div class="compare-bar">
        <span>baseline: {baselinePick?.sha ?? "—"}</span>
        <span>contender: {contenderPick?.sha ?? "—"}</span>
        {#if compareHref !== null}
          {@const href = compareHref}
          <a
            class="button-pill primary"
            {href}
            onclick={(e) => {
              if (!interceptNavClick(e)) return;
              e.preventDefault();
              navigate(href);
            }}
          >Compare</a>
        {:else}
          <span class="faint">pick both points to compare</span>
        {/if}
        <button type="button" class="button-pill" onclick={clearPicks}>clear</button>
      </div>
    {/if}

      {#if visible.length > 0}
        <div class="filter-bar" aria-label="Trend point filters">
          <button
          type="button"
          class="button-pill"
          class:active={trendFilter === "all"}
          aria-pressed={trendFilter === "all"}
          onclick={() => (trendFilter = "all")}
        >All {visible.length}</button>
        <button
          type="button"
          class="button-pill"
          class:active={trendFilter === "outliers"}
          aria-pressed={trendFilter === "outliers"}
          onclick={() => (trendFilter = "outliers")}
        >Outliers {outlierCount}</button>
        <button
          type="button"
          class="button-pill"
          class:active={trendFilter === "steps"}
          aria-pressed={trendFilter === "steps"}
          onclick={() => (trendFilter = "steps")}
        >Steps {stepCount}</button>
        </div>
      {/if}
    {/if}
  </section>

  {#if all.length === 0}
    <p class="empty">This series has no default-branch history.</p>
  {:else}
    {#if visible.length === 0}
      <p class="empty">
        No points in the last {RANGE_LABEL[query.range]} —
        <button type="button" class="link" onclick={() => setControl({ range: "all" })}>
          show all {all.length} points
        </button>
      </p>
    {:else}
      <SeriesChart points={visible} axis={query.axis} sigma={query.sigma} {selectedIndex} onselect={select} />
      {#if selected !== null}
        <!-- @const pins the narrowed point: TS narrowing on the nullable $derived
             does not survive into the onclick closure. -->
        {@const sel = selected}
        <section class="selected-panel panel" aria-label="Selected point">
          <div>
            <span class="eyebrow">selected point</span>
            <strong>{sel.commitHash}</strong>
            <span class="faint numeric-text">{formatMeasurement(sel.svs, sel.unit)}</span>
          </div>
          <dl class="point-meta">
            <div>
              <dt>result</dt>
              <dd>{sel.resultId}</dd>
            </div>
            <div>
              <dt>z-score</dt>
              <dd>{zText(sel.stats.z)}</dd>
            </div>
            <div>
              <dt>flags</dt>
              <dd>{flagsText(sel.stats) || "none"}</dd>
            </div>
          </dl>
          <div class="actions">
            <a
              class="button-pill"
              href={`/results/${sel.resultId}`}
              onclick={(e) => {
                if (!interceptNavClick(e)) return;
                e.preventDefault();
                openResult(sel.resultId);
              }}
            >Open result</a>
            <button
              type="button"
              class="button-pill"
              onclick={() => (baselinePick = { id: sel.resultId, sha: sel.commitHash })}
            >set baseline</button>
            <button
              type="button"
              class="button-pill"
              onclick={() => (contenderPick = { id: sel.resultId, sha: sel.commitHash })}
            >set contender</button>
          </div>
        </section>
      {/if}
      {#if exportCommand !== null}
        <section class="export-panel panel" aria-label="History export">
          <span class="eyebrow">history export</span>
          <code>{exportCommand}</code>
          <button type="button" class="button-pill" onclick={copyExportCommand}>Copy export command</button>
          {#if exportCopied}<span class="copied">copied</span>{/if}
        </section>
      {/if}
      <section class="panel table-panel history-table-panel" aria-label="Trend history">
        <p class="row-count">{rowCountText()}</p>
        <DetailTable
          rows={displayedRows}
          {selectedIndex}
          onselect={select}
          onopen={(row) => openResult(row.resultId)}
        />
      </section>
      {#if hiddenRowCount > 0}
        <button type="button" class="button-pill more" onclick={() => (rowLimit += TREND_TABLE_ROW_CHUNK)}>
          Show more
        </button>
      {/if}
    {/if}
  {/if}
  </main>
{/if}

<style>
  .trend-page {
    max-width: 1600px;
  }
  .trend-context {
    position: sticky;
    top: var(--app-header-height);
    z-index: 4;
    display: grid;
    gap: 10px;
    padding: 12px;
    background: color-mix(in srgb, var(--c-surface) 94%, transparent);
    backdrop-filter: blur(8px);
  }
  .ident {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    overflow-wrap: anywhere;
  }
  .faint { color: var(--c-text-faint); }
  .integrity {
    padding: 7px 9px;
    border-radius: var(--radius-sm);
    background: var(--c-warn-bg);
    border: 1px solid var(--c-warning);
    color: var(--c-warn-text);
    font-size: 0.8rem;
  }
  .error { color: var(--c-error); }
  .empty { color: var(--c-text-muted); }
  .controls {
    align-items: end;
  }
  .controls label {
    min-width: 120px;
  }
  .flag-queue {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    margin: 0.5rem 0 0.65rem;
  }
  .flag-card {
    display: grid;
    gap: 3px;
    min-width: 0;
    padding: 0.55rem 0.65rem;
    border: 1px solid var(--c-border-muted);
    border-left: 4px solid var(--c-warning);
    border-radius: var(--radius-sm);
    background: var(--c-surface);
    color: var(--c-text-muted);
    cursor: pointer;
    font: inherit;
    font-size: 0.78rem;
    text-align: left;
  }
  .flag-card:hover {
    border-color: var(--c-accent);
  }
  .flag-card strong {
    color: var(--c-text);
    overflow-wrap: anywhere;
  }
  .flag-card .jump {
    color: var(--c-accent);
    font-weight: 700;
  }
  .filter-bar { display: flex; gap: 0.45rem; flex-wrap: wrap; margin: 0.25rem 0 0.6rem; }
  .selected-panel, .export-panel {
    margin: 0.65rem 0;
    padding: 0.65rem 0.75rem;
  }
  .selected-panel {
    display: grid;
    grid-template-columns: minmax(10rem, 1.2fr) minmax(12rem, 2fr) auto;
    gap: 0.9rem;
    align-items: center;
  }
  .selected-panel strong, .selected-panel .faint { display: block; overflow-wrap: anywhere; }
  .eyebrow {
    display: block;
    color: var(--c-text-muted);
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0;
    margin-bottom: 0.15rem;
  }
  .point-meta {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.6rem;
    margin: 0;
  }
  .point-meta div { min-width: 0; }
  .point-meta dt {
    color: var(--c-text-muted);
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0;
  }
  .point-meta dd { margin: 0.08rem 0 0; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
  .actions { display: flex; gap: 0.65rem; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
  .export-panel { display: flex; gap: 0.55rem; align-items: center; flex-wrap: wrap; }
  .export-panel code {
    overflow-wrap: anywhere;
    font-size: 0.78rem;
    padding: 0.16rem 0.28rem;
    background: var(--c-bg-inset);
    border-radius: 4px;
  }
  .copied { color: var(--c-success); font-size: 0.78rem; }
  .compare-bar {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
    padding: 8px;
    border: 1px solid var(--c-border-muted);
    border-radius: var(--radius-sm);
    background: var(--c-bg-inset);
    font-size: 0.8rem;
    color: var(--c-text-muted);
  }
  .history-table-panel {
    overflow: hidden;
  }
  .row-count { color: var(--c-text-muted); font-size: 0.8rem; margin: 0; padding: 9px 10px; }
  .more {
    margin-top: 0.6rem;
  }
  .link { background: none; border: none; padding: 0; font: inherit;
          color: var(--c-accent); cursor: pointer; text-decoration: underline; }
  @media (max-width: 1120px) {
    .trend-context {
      position: static;
      top: auto;
    }
  }
  @media (max-width: 760px) {
    .page-header {
      display: grid;
    }
    .page-meta {
      justify-content: flex-start;
    }
    .flag-queue { grid-template-columns: 1fr; }
    .selected-panel { grid-template-columns: 1fr; align-items: start; }
    .point-meta { grid-template-columns: 1fr; }
    .actions { justify-content: flex-start; }
  }
</style>
