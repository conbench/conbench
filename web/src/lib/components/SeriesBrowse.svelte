<script lang="ts">
  import { createConbenchClient } from "../api/client";
  import { listSeries } from "../browse/loader";
  import { sortRows, type BrowseRow, type SortKey, type SortSpec } from "../browse/transform";
  import { formatBrowseQuery, interceptNavClick, navigate, type BrowseQuery, type BrowseWindow } from "../router";
  import BrowseTable from "./BrowseTable.svelte";

  let {
    query,
    baseUrl = "",
  }: {
    query: BrowseQuery;
    baseUrl?: string;
  } = $props();

  // baseUrl is a fixed prop; $derived rebuilds the client only if it ever
  // changes, which silences Svelte's "captures the initial value" warning. The
  // load effect also tracks `client`, but it is referentially stable (fixed
  // `baseUrl` prop), so it never triggers a refetch.
  const client = $derived(createConbenchClient(baseUrl));

  let rows = $state<BrowseRow[]>([]);
  let nextCursor = $state<string | null>(null);
  let loading = $state(true);
  let loadingMore = $state(false);
  let errorMsg = $state<string | null>(null);
  let moreErrorMsg = $state<string | null>(null);
  let sort = $state<SortSpec | null>(null);
  let hardwareFilter = $state("");
  let repositoryFilter = $state("");
  let exactFiltersOpen = $state(false);
  // Monotonic token: a stale response (filters changed mid-flight) must not
  // overwrite a newer page.
  let reqToken = 0;

  $effect(() => {
    hardwareFilter = query.hardware;
    repositoryFilter = query.repository;
    void load(query);
  });

  async function load(q: BrowseQuery) {
    const token = ++reqToken;
    loading = true;
    rows = [];
    nextCursor = null;
    // A fresh page load supersedes any in-flight load-more, whose guarded
    // finally will then skip its cleanup — clear the flag here so the new
    // page's Load more cannot start out wedged disabled.
    loadingMore = false;
    errorMsg = null;
    moreErrorMsg = null;
    try {
      const page = await listSeries(client, q);
      if (token !== reqToken) return;
      rows = page.rows;
      nextCursor = page.nextCursor;
    } catch (err) {
      if (token !== reqToken) return;
      errorMsg = err instanceof Error ? err.message : String(err);
    } finally {
      if (token === reqToken) loading = false;
    }
  }

  async function loadMore() {
    if (nextCursor === null || loadingMore) return;
    const token = reqToken;
    loadingMore = true;
    moreErrorMsg = null;
    try {
      const page = await listSeries(client, query, nextCursor);
      if (token !== reqToken) return;
      rows = [...rows, ...page.rows];
      nextCursor = page.nextCursor;
    } catch (err) {
      if (token !== reqToken) return;
      moreErrorMsg = err instanceof Error ? err.message : String(err);
    } finally {
      if (token === reqToken) loadingMore = false;
    }
  }

  function setFilter(patch: Partial<BrowseQuery>) {
    navigate(`/series${formatBrowseQuery({ ...query, ...patch })}`);
  }

  function clearFilter(patch: Partial<BrowseQuery>) {
    setFilter(patch);
  }

  function submitExactFilters(e: SubmitEvent) {
    e.preventDefault();
    setFilter({
      hardware: hardwareFilter.trim(),
      repository: repositoryFilter.trim(),
    });
  }

  function toggleSort(key: SortKey) {
    if (sort?.key !== key) {
      sort = { key, dir: "asc" };
    } else if (sort.dir === "asc") {
      sort = { key, dir: "desc" };
    } else {
      sort = null;
    }
  }

  function open(row: BrowseRow) {
    navigate(`/series/${row.fingerprint}`);
  }

  function go(e: MouseEvent, href: string) {
    if (!interceptNavClick(e)) return;
    e.preventDefault();
    navigate(href);
  }

  let visible = $derived(sortRows(rows, sort));
  const windowLabel: Record<BrowseWindow, string> = {
    all: "all time",
    "30d": "last 30 days",
    "3mo": "last 3 months",
    "1y": "last year",
  };
  const windowOptions: { value: BrowseWindow; label: string }[] = [
    { value: "all", label: "All time" },
    { value: "30d", label: "Last 30 days" },
    { value: "3mo", label: "Last 3 months" },
    { value: "1y", label: "Last year" },
  ];
  let activeFilters = $derived([
    ...(query.q !== ""
      ? [{ label: "query", value: query.q, clear: { q: "" }, aria: `Remove query filter ${query.q}` }]
      : []),
    ...(query.hardware !== ""
      ? [{ label: "hardware", value: query.hardware, clear: { hardware: "" }, aria: `Remove hardware filter ${query.hardware}` }]
      : []),
    ...(query.repository !== ""
      ? [{
          label: "repository",
          value: query.repository,
          clear: { repository: "" },
          aria: `Remove repository filter ${query.repository}`,
        }]
      : []),
    ...(query.window !== "all"
      ? [{
          label: "window",
          value: windowLabel[query.window],
          clear: { window: "all" as const },
          aria: `Remove window filter ${windowLabel[query.window]}`,
        }]
      : []),
  ]);
  let loadedSummary = $derived(
    `Showing ${visible.length} loaded ${visible.length === 1 ? "series" : "series"}`,
  );
  let familySummary = $derived(query.q.trim() === "" || visible.length === 0 ? null : summarizeFamily(visible));

  interface FamilyCase {
    key: string;
    name: string;
    paramsText: string;
    seriesCount: number;
    hardwareCount: number;
    contextCount: number;
    pointCount: number;
    latestMs: number;
    latestDateText: string;
    sampleFingerprint: string;
  }

  interface FamilySummary {
    caseCount: number;
    hardwareCount: number;
    contextCount: number;
    regressedCount: number;
    improvedCount: number;
    totalPoints: number;
    cases: FamilyCase[];
    triageRows: BrowseRow[];
  }

  function summarizeFamily(sourceRows: BrowseRow[]): FamilySummary {
    const hardware = new Set<string>();
    const context = new Set<string>();
    const cases = new Map<string, FamilyCase>();
    let regressedCount = 0;
    let improvedCount = 0;
    let totalPoints = 0;

    for (const row of sourceRows) {
      hardware.add(row.hardwareKey);
      context.add(row.contextText || "default");
      totalPoints += row.pointCount;
      if (row.status === "regressed") regressedCount += 1;
      if (row.status === "improved") improvedCount += 1;

      const key = `${row.name}\u0000${row.paramsText}`;
      const existing = cases.get(key);
      if (existing === undefined) {
        cases.set(key, {
          key,
          name: row.name,
          paramsText: row.paramsText || "default case",
          seriesCount: 1,
          hardwareCount: 1,
          contextCount: 1,
          pointCount: row.pointCount,
          latestMs: row.commitTimestampMs,
          latestDateText: row.commitDateText,
          sampleFingerprint: row.fingerprint,
        });
        continue;
      }
      existing.seriesCount += 1;
      existing.pointCount += row.pointCount;
      if (row.commitTimestampMs > existing.latestMs) {
        existing.latestMs = row.commitTimestampMs;
        existing.latestDateText = row.commitDateText;
        existing.sampleFingerprint = row.fingerprint;
      }
    }

    const caseHardware = new Map<string, Set<string>>();
    const caseContext = new Map<string, Set<string>>();
    for (const row of sourceRows) {
      const key = `${row.name}\u0000${row.paramsText}`;
      if (!caseHardware.has(key)) caseHardware.set(key, new Set());
      if (!caseContext.has(key)) caseContext.set(key, new Set());
      caseHardware.get(key)?.add(row.hardwareKey);
      caseContext.get(key)?.add(row.contextText || "default");
    }
    for (const c of cases.values()) {
      c.hardwareCount = caseHardware.get(c.key)?.size ?? 0;
      c.contextCount = caseContext.get(c.key)?.size ?? 0;
    }

    return {
      caseCount: cases.size,
      hardwareCount: hardware.size,
      contextCount: context.size,
      regressedCount,
      improvedCount,
      totalPoints,
      cases: [...cases.values()].sort((a, b) => b.seriesCount - a.seriesCount || b.latestMs - a.latestMs).slice(0, 8),
      triageRows: sourceRows
        .filter((row) => row.status === "regressed" || row.status === "improved")
        .sort((a, b) => b.commitTimestampMs - a.commitTimestampMs)
        .slice(0, 8),
    };
  }
</script>

<main class="page series-page">
  <header class="page-header">
    <div>
      <p class="eyebrow">Benchmark Explorer</p>
      <h1>Benchmark series</h1>
      <p class="page-subtitle">
        Scan benchmark families, current status, recent history, and default-branch coverage.
      </p>
    </div>
    <div class="page-meta">
      <span>{loadedSummary}</span>
      {#if nextCursor !== null}<span>More available</span>{/if}
    </div>
  </header>

  <div class="panel browse-filters">
    <div class="filter-row" role="group" aria-label="Series time window">
      <span class="filter-row-label">Window</span>
      <div class="segmented-control">
        {#each windowOptions as option}
          <button
            type="button"
            class:active={query.window === option.value}
            aria-pressed={query.window === option.value}
            onclick={() => setFilter({ window: option.value })}
          >
            {option.label}
          </button>
        {/each}
      </div>
    </div>
    {#if activeFilters.length > 0}
      <button type="button" class="button-pill secondary" onclick={() => navigate("/series")}>Clear filters</button>
    {/if}
  </div>

  <div class="filter-toolbar">
    <button
      type="button"
      class="button-pill secondary"
      aria-expanded={exactFiltersOpen}
      onclick={() => (exactFiltersOpen = !exactFiltersOpen)}
    >
      Exact metadata filters
    </button>
  </div>

  {#if exactFiltersOpen}
    <section class="panel filter-disclosure" aria-label="Exact metadata filters">
      <form class="exact-filter-form" onsubmit={submitExactFilters}>
        <label class="filter-label">
          Hardware name
          <input
            type="text"
            bind:value={hardwareFilter}
            placeholder="for example m5"
            autocomplete="off"
          />
        </label>
        <label class="filter-label">
          Repository URL
          <input
            type="url"
            bind:value={repositoryFilter}
            placeholder="https://github.com/apache/arrow"
            autocomplete="off"
          />
        </label>
        <div class="filter-actions">
          <button type="submit" class="button-pill">Apply exact filters</button>
          <a class="button-pill secondary" href="/series" onclick={(e) => go(e, "/series")}>Clear</a>
        </div>
      </form>
    </section>
  {/if}

  {#if activeFilters.length > 0}
    <div class="active-filters" role="group" aria-label="Active filters">
      {#each activeFilters as filter (filter)}
        <button type="button" class="filter-chip" aria-label={filter.aria} onclick={() => clearFilter(filter.clear)}>
          <span class="chip-label">{filter.label}</span>
          <span class="chip-value">{filter.value}</span>
          <span class="chip-x" aria-hidden="true">&times;</span>
        </button>
      {/each}
    </div>
  {/if}

  {#if familySummary !== null}
    <section class="panel family-drilldown" aria-label="Loaded benchmark family drilldown">
      <header>
        <div>
          <p class="eyebrow">Family Drilldown</p>
          <h2>{query.q}</h2>
        </div>
        <span>{loadedSummary}</span>
      </header>
      <div class="family-metrics" aria-label="Loaded family summary">
        <div>
          <strong>{familySummary.caseCount.toLocaleString()}</strong>
          <span>case variants</span>
        </div>
        <div>
          <strong>{familySummary.hardwareCount.toLocaleString()}</strong>
          <span>hardware targets</span>
        </div>
        <div>
          <strong>{familySummary.contextCount.toLocaleString()}</strong>
          <span>context shapes</span>
        </div>
        <div>
          <strong>{familySummary.totalPoints.toLocaleString()}</strong>
          <span>history points</span>
        </div>
        <div>
          <strong>{familySummary.regressedCount.toLocaleString()}</strong>
          <span>regressed</span>
        </div>
        <div>
          <strong>{familySummary.improvedCount.toLocaleString()}</strong>
          <span>improved</span>
        </div>
      </div>
      <div class="family-sections">
        <section aria-label="Loaded case variants">
          <h3>Case variants</h3>
          <div class="case-list">
            {#each familySummary.cases as c (c.key)}
              <a href={`/series/${c.sampleFingerprint}`} onclick={(e) => go(e, `/series/${c.sampleFingerprint}`)}>
                <strong>{c.paramsText}</strong>
                <span>{c.seriesCount.toLocaleString()} series · {c.hardwareCount.toLocaleString()} hardware · {c.contextCount.toLocaleString()} context · {c.pointCount.toLocaleString()} points</span>
                <span>latest {c.latestDateText}</span>
              </a>
            {/each}
          </div>
        </section>
        <section aria-label="Loaded trend triage">
          <h3>Trend triage</h3>
          {#if familySummary.triageRows.length === 0}
            <p class="muted">No loaded regressed or improved series.</p>
          {:else}
            <div class="triage-list">
              {#each familySummary.triageRows as row (row.fingerprint)}
                <a class={`triage-row ${row.status}`} href={`/series/${row.fingerprint}`} onclick={(e) => go(e, `/series/${row.fingerprint}`)}>
                  <span>{row.status}</span>
                  <strong>{row.name}</strong>
                  <span>{row.paramsText || "default case"}</span>
                  <span>{row.hardwareName} · {row.svsText}</span>
                </a>
              {/each}
            </div>
          {/if}
        </section>
      </div>
    </section>
  {/if}

  {#if errorMsg}
    <section class="panel state-panel error-panel" role="alert">
      <h2>Failed to load series</h2>
      <p>{errorMsg}</p>
    </section>
  {:else if loading}
    <section class="panel state-panel loading-panel" aria-live="polite">
      <h2>Loading benchmark series</h2>
      <p>Loading...</p>
    </section>
  {:else if visible.length === 0}
    <section class="panel state-panel empty-panel" aria-label="No matching benchmark series">
      <h2>No series match the current filters</h2>
      <p>Clear active filters or use the global search to open a benchmark family.</p>
    </section>
  {:else}
    <BrowseTable rows={visible} {sort} onsort={toggleSort} onopen={open} />
    {#if sort !== null}
      <p class="scope-note">Sorting applies to loaded rows. Load more for a broader local sort.</p>
    {/if}
    {#if moreErrorMsg}
      <section class="panel state-panel error-panel" role="alert">
        <h2>Failed to load more</h2>
        <p>{moreErrorMsg}</p>
      </section>
    {/if}
    {#if nextCursor !== null}
      <button type="button" class="button-pill more" onclick={loadMore} disabled={loadingMore}>
        {loadingMore ? "Loading…" : "Load more"}
      </button>
    {/if}
  {/if}
</main>

<style>
  .series-page {
    gap: 12px;
  }
  .browse-filters {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 12px;
  }

  .filter-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .filter-row-label {
    color: var(--c-text-muted);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .segmented-control {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 2px;
    border: 1px solid var(--c-border-muted);
    border-radius: var(--radius-md);
    background: var(--c-bg-inset);
  }

  .segmented-control button {
    min-height: 26px;
    padding: 0 9px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--c-text-muted);
    cursor: pointer;
  }

  .segmented-control button:hover {
    background: var(--c-surface-hover);
    color: var(--c-text);
  }

  .segmented-control button.active {
    background: var(--c-accent);
    color: var(--c-on-accent);
  }

  .filter-toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .filter-disclosure {
    padding: 0;
  }

  .exact-filter-form {
    display: grid;
    grid-template-columns: repeat(2, minmax(180px, 1fr)) auto;
    gap: 10px;
    align-items: end;
    padding: 0 12px 12px;
  }

  .error-panel h2 {
    color: var(--c-error);
  }

  .muted { color: var(--c-text-muted); margin: 0; }
  .family-drilldown {
    display: grid;
    gap: 10px;
    padding: 12px;
  }
  .family-drilldown header {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: start;
  }
  .family-drilldown h2 {
    margin: 0;
    font-size: 1.05rem;
  }
  .family-drilldown header > span {
    color: var(--c-text-muted);
    font-size: 0.78rem;
    white-space: nowrap;
  }
  .family-metrics {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 8px;
  }
  .family-metrics div {
    display: grid;
    gap: 2px;
    padding: 8px;
    border: 1px solid var(--c-border-muted);
    border-radius: var(--radius-sm);
    background: var(--c-bg-inset);
  }
  .family-metrics strong {
    font-size: 1rem;
    font-variant-numeric: tabular-nums;
  }
  .family-metrics span {
    color: var(--c-text-muted);
    font-size: 0.72rem;
  }
  .family-sections {
    display: grid;
    grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
    gap: 12px;
  }
  .family-sections h3 {
    margin: 0 0 6px;
    color: var(--c-text-muted);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .case-list, .triage-list {
    display: grid;
    gap: 6px;
  }
  .case-list a, .triage-row {
    display: grid;
    gap: 3px;
    min-width: 0;
    padding: 8px;
    border: 1px solid var(--c-border-muted);
    border-radius: var(--radius-sm);
    color: var(--c-text-muted);
    text-decoration: none;
  }
  .case-list a:hover, .triage-row:hover {
    border-color: var(--c-accent);
  }
  .case-list strong, .triage-row strong {
    min-width: 0;
    color: var(--c-text);
    overflow-wrap: anywhere;
  }
  .case-list span, .triage-row span {
    overflow-wrap: anywhere;
    font-size: 0.76rem;
  }
  .triage-row {
    border-left: 4px solid var(--c-success);
  }
  .triage-row.regressed {
    border-left-color: var(--c-error);
  }
  .triage-row > span:first-child {
    color: var(--c-accent);
    font-weight: 700;
  }
  .scope-note {
    color: var(--c-text-muted);
    font-size: 0.78rem;
    margin: -2px 0 0;
  }
  .more {
    width: fit-content;
    margin-top: 0.25rem;
  }
  @media (max-width: 760px) {
    .family-drilldown header {
      flex-direction: column;
    }
    .family-drilldown header > span {
      white-space: normal;
    }
    .family-metrics {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .family-sections {
      grid-template-columns: 1fr;
    }
    .browse-filters {
      align-items: stretch;
      flex-direction: column;
    }

    .exact-filter-form {
      grid-template-columns: 1fr;
    }
  }
</style>
