<script lang="ts">
  import { onMount } from "svelte";

  import { createConbenchClient } from "../api/client";
  import {
    listRecentRuns,
    type RecentRunAttentionViewModel,
    type RecentRunRepositoryViewModel,
    type RecentRunViewModel,
  } from "../home/loader";
  import { DEFAULT_HOME_QUERY, formatHomeQuery, interceptNavClick, navigate, type HomeQuery } from "../router";

  let {
    baseUrl = "",
    query = DEFAULT_HOME_QUERY,
  }: {
    baseUrl?: string;
    query?: HomeQuery;
  } = $props();

  const client = $derived(createConbenchClient(baseUrl));

  let runs = $state<RecentRunViewModel[]>([]);
  let repositories = $state<RecentRunRepositoryViewModel[]>([]);
  let loading = $state(true);
  let errorMsg = $state<string | null>(null);

  onMount(() => {
    void load();
  });

  async function load() {
    loading = true;
    errorMsg = null;
    try {
      const page = await listRecentRuns(client, query);
      runs = page.runs;
      repositories = page.repositories;
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
  const attentionRuns = $derived(runs.filter((run) => run.attention !== null));
  const ATTENTION_WINDOW = 5;
  const selectedRepositoryLabel = $derived(
    query.repository === ""
      ? "All projects"
      : repositories.find((repository) => repository.repository === query.repository)?.label ??
        formatRepositoryLabel(query.repository),
  );

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

  function formatRepositoryLabel(repository: string): string {
    if (repository === "") return "not set";
    try {
      const u = new URL(repository);
      const parts = u.pathname.split("/").filter(Boolean);
      return parts.length >= 2 ? `${parts[0]}/${parts[1]}` : repository;
    } catch {
      return repository;
    }
  }

  function projectHref(repository: string): string {
    return `/${formatHomeQuery({ repository })}`;
  }

  function setRepository(e: Event) {
    const repository = e.currentTarget instanceof HTMLSelectElement ? e.currentTarget.value : "";
    navigate(projectHref(repository));
  }

  function attentionStatusLabel(attention: RecentRunAttentionViewModel): string {
    return attention.status === "failure" ? "Regression" : "Action required";
  }

  function reportLabel(run: RecentRunViewModel): string {
    if (run.attention === null) return "Report";
    return attentionStatusLabel(run.attention);
  }
</script>

<main class="page home-page">
  <header class="page-header">
    <div>
      <p class="eyebrow">{selectedRepositoryLabel}</p>
      <h1>CI runs</h1>
    </div>
    <div class="header-controls">
      {#if repositories.length > 0}
        <label class="project-selector">
          Project
          <select value={query.repository} onchange={setRepository}>
            <option value="">All projects</option>
            {#each repositories as repository (repository.repository)}
              <option value={repository.repository}>{repository.label}</option>
            {/each}
          </select>
        </label>
      {/if}
      <div class="page-meta">
        {#if query.repository !== ""}
          <span>{selectedRepositoryLabel}</span>
        {:else if repositoryLabels.length === 1}
          <span>{repositoryLabels[0]}</span>
        {:else if repositoryLabels.length > 1}
          <span>{plural(repositoryLabels.length, "repository", "repositories")}</span>
        {/if}
        <span>Newest first</span>
      </div>
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
      {#if totalErrors > 0}
        <span class="summary-item alert">{plural(totalErrors, "error")}</span>
      {/if}
      <span class="summary-item">attention checked: newest {ATTENTION_WINDOW} runs</span>
      <span class="summary-item">{repositorySummary(repositoryLabels)}</span>
    </p>

    {#if attentionRuns.length > 0}
      <section class="attention-panel" aria-labelledby="home-attention-heading">
        <div class="attention-heading">
          <h2 id="home-attention-heading">Needs attention <span>newest {ATTENTION_WINDOW}</span></h2>
          <span>{plural(attentionRuns.length, "run")}</span>
        </div>
        <div class="attention-list">
          {#each attentionRuns as run (run.runId)}
            {@const attention = run.attention!}
            <a
              class={`attention-link ${attention.status}`}
              href={attention.reportHref}
              aria-label={`Review CI report for run ${run.runId}`}
              onclick={(e) => go(e, attention.reportHref)}
            >
              <span class={`attention-status ${attention.status}`}>{attentionStatusLabel(attention)}</span>
              <strong>{run.primaryLabel}</strong>
              <span>{attention.summaryText}</span>
              <span class="attention-reason">{attention.statusReason}</span>
            </a>
          {/each}
        </div>
      </section>
    {/if}

    <section class="panel table-panel" aria-label="CI runs">
      <table class="data-table stacked-table runs-table">
        <colgroup>
          <col class="time-col" />
          <col class="results-col" />
          {#if showReasonColumn}
            <col class="reason-col" />
          {/if}
          {#if showRepositoryColumn}
            <col class="repository-col" />
          {/if}
          <col class="author-col" />
          <col class="commit-col" />
          <col class="message-col" />
          <col class="report-col" />
        </colgroup>
        <thead>
          <tr>
            <th>Time</th>
            <th>Results</th>
            {#if showReasonColumn}
              <th>Reason</th>
            {/if}
            {#if showRepositoryColumn}
              <th>Repository</th>
            {/if}
            <th>Author</th>
            <th>Commit</th>
            <th>Message</th>
            <th>Report</th>
          </tr>
        </thead>
        <tbody>
          {#each runs as run (run.runId)}
            <tr class:error-row={run.errorCount > 0} class:attention-row={run.attention !== null}>
              <td data-label="Time">
                <a
                  class="time-link"
                  href={run.runHref}
                  aria-label={`Open run detail for ${run.runId}`}
                  title={run.runId}
                  onclick={(e) => go(e, run.runHref)}
                >{formatTime(run.lastResultAt)}</a>
                <div class="muted-detail">{run.secondaryLabel}</div>
              </td>
              <td data-label="Results">
                <div class="count-stack">
                  <strong>{run.resultCount.toLocaleString()}</strong>
                  <span>{plural(run.seriesCount, "series", "series")}</span>
                  {#if run.errorCount > 0}
                    <span class="status-badge warning">{plural(run.errorCount, "error")}</span>
                  {/if}
                  {#if run.attention}
                    <span class={`attention-mini ${run.attention.status}`}>{run.attention.summaryText}</span>
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
              <td data-label="Author">
                <div class="author-cell">
                  {#if run.authorAvatar}
                    <img src={run.authorAvatar} alt="" loading="lazy" referrerpolicy="no-referrer" />
                  {:else}
                    <span class="author-initial" aria-hidden="true">{run.authorLabel.slice(0, 1).toUpperCase()}</span>
                  {/if}
                  <div>
                    <div>{run.authorLabel}</div>
                    {#if run.authorLogin}
                      <div class="muted-detail">@{run.authorLogin}</div>
                    {/if}
                  </div>
                </div>
              </td>
              <td data-label="Commit">
                {#if run.commitHref && run.shortCommit}
                  <a
                    class="mono value-code"
                    href={run.commitHref}
                    aria-label={`Open commit ${run.shortCommit} on GitHub`}
                    target="_blank"
                    rel="noreferrer"
                  >{run.shortCommit}</a>
                {:else}
                  <span class="mono value-code">{run.shortCommit ?? "not set"}</span>
                {/if}
              </td>
              <td data-label="Message">
                <div class="message-cell">
                  <a
                    class="row-primary-link"
                    href={run.runHref}
                    aria-label={`Open run ${run.runId}`}
                    title={run.runId}
                    onclick={(e) => go(e, run.runHref)}
                  >{run.primaryLabel}</a>
                  <div class="meta-line">
                    <span class="muted-detail">{run.secondaryLabel}</span>
                    {#if run.latestBatchId}
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
                    {/if}
                    {#if run.batchCount > 1}
                      <span class="muted-detail">{run.batchCount - 1} earlier {run.batchCount === 2 ? "batch" : "batches"}</span>
                    {/if}
                  </div>
                </div>
              </td>
              <td data-label="Report">
                <div class="inline-actions table-actions">
                  {#if run.ciReportHref}
                    <a
                      class:status-badge={run.attention !== null}
                      class:failure={run.attention?.status === "failure"}
                      class:action_required={run.attention?.status === "action_required"}
                      class:inline-action-link={run.attention === null}
                      href={run.ciReportHref}
                      aria-label={`Open CI report for run ${run.runId}`}
                      onclick={(e) => go(e, run.ciReportHref!)}
                    >{reportLabel(run)}</a>
                  {/if}
                  <a
                    class="inline-action-link"
                    href={run.latestResultHref}
                    aria-label={`Open sample result for run ${run.runId}`}
                    onclick={(e) => go(e, run.latestResultHref)}
                  >Result</a>
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
    height: 100%;
    min-height: 0;
    max-height: 100%;
  }
  .home-page .table-panel {
    flex: 1;
    min-height: 0;
    overflow: auto;
  }
  .runs-table {
    --stacked-label-width: 88px;
  }
  .runs-table thead th {
    position: sticky;
    top: 0;
    z-index: 1;
  }
  .header-controls {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    align-items: flex-start;
    gap: 8px;
  }
  .project-selector {
    display: grid;
    gap: 4px;
    color: var(--c-text-muted);
    font-size: 0.68rem;
    font-weight: 750;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .project-selector select {
    min-height: 28px;
    min-width: 180px;
    max-width: min(48vw, 280px);
    padding: 0 28px 0 9px;
    border: 1px solid var(--c-border);
    border-radius: var(--radius-sm);
    background: var(--c-surface);
    color: var(--c-text);
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0;
    text-transform: none;
  }
  .runs-table .time-col {
    width: 10%;
  }
  .runs-table .results-col {
    width: 9%;
  }
  .runs-table .reason-col {
    width: 8%;
  }
  .runs-table .repository-col {
    width: 13%;
  }
  .runs-table .author-col {
    width: 14%;
  }
  .runs-table .commit-col {
    width: 8%;
  }
  .runs-table .message-col {
    width: auto;
  }
  .runs-table .report-col {
    width: 12%;
  }
  .message-cell,
  .count-stack {
    display: grid;
    gap: 4px;
    min-width: 0;
  }
  .count-stack strong {
    font-variant-numeric: tabular-nums;
  }
  .count-stack span:not(.status-badge):not(.attention-mini) {
    color: var(--c-text-muted);
    font-size: 0.76rem;
  }
  .meta-line,
  .table-actions {
    min-width: 0;
  }
  .attention-panel {
    display: grid;
    grid-template-columns: minmax(120px, auto) minmax(0, 1fr);
    align-items: stretch;
    gap: 0;
    border: 1px solid color-mix(in srgb, var(--c-error) 26%, var(--c-border-muted));
    border-radius: var(--radius-md);
    background: var(--c-surface);
    overflow: hidden;
  }
  .attention-heading {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
    padding: 9px 12px;
    border-right: 1px solid var(--c-border-muted);
    background: color-mix(in srgb, var(--c-error) 7%, var(--c-surface));
  }
  .attention-heading h2 {
    margin: 0;
    color: var(--c-text);
    font-size: 0.86rem;
    line-height: 1.2;
  }
  .attention-heading h2 span,
  .attention-heading > span {
    color: var(--c-text-muted);
    font-size: 0.74rem;
    font-weight: 500;
  }
  .attention-list {
    display: flex;
    flex-wrap: wrap;
    align-items: stretch;
    gap: 0;
  }
  .attention-link {
    min-width: min(100%, 340px);
    display: grid;
    grid-template-columns: auto auto minmax(0, 1fr);
    align-content: center;
    align-items: baseline;
    gap: 4px 8px;
    padding: 9px 12px;
    border-right: 1px solid var(--c-border-muted);
    color: var(--c-text);
    text-decoration: none;
  }
  .attention-link:hover {
    background: var(--c-row-hover);
    color: var(--c-text);
  }
  .attention-status {
    color: var(--c-error);
    font-size: 0.72rem;
    font-weight: 750;
    text-transform: uppercase;
  }
  .attention-status.action_required {
    color: var(--c-warning);
  }
  .attention-reason {
    grid-column: 1 / -1;
    min-width: 0;
    color: var(--c-text-muted);
    font-size: 0.76rem;
    overflow-wrap: anywhere;
  }
  .attention-mini {
    color: var(--c-error);
    font-size: 0.72rem;
    font-weight: 750;
  }
  .attention-mini.action_required {
    color: var(--c-warning);
  }
  .author-cell {
    min-width: 0;
    display: grid;
    grid-template-columns: 24px minmax(0, 1fr);
    align-items: center;
    gap: 8px;
  }
  .author-cell img,
  .author-initial {
    width: 24px;
    height: 24px;
    border-radius: 50%;
  }
  .author-cell img {
    display: block;
    background: var(--c-surface-subtle);
  }
  .author-initial {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--c-accent-soft);
    color: var(--c-accent-strong);
    font-size: 0.76rem;
    font-weight: 750;
  }
  .time-link {
    color: var(--c-accent);
    font-weight: 650;
    text-decoration: none;
    white-space: nowrap;
  }
  .time-link:hover {
    color: var(--c-accent-strong);
    text-decoration: underline;
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
  @media (max-width: 1120px) {
    .attention-panel {
      grid-template-columns: 1fr;
    }
    .attention-heading {
      border-right: 0;
      border-bottom: 1px solid var(--c-border-muted);
    }
    .attention-link {
      min-width: 100%;
      border-right: 0;
      border-bottom: 1px solid var(--c-border-muted);
    }
    .attention-link:last-child {
      border-bottom: 0;
    }
  }
</style>
