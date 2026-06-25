<script lang="ts">
  import { onMount } from "svelte";

  import { createConbenchClient } from "../api/client";
  import { loadResult, resultViewModelFromDetail, type ResultViewModel } from "../result/loader";
  import { interceptNavClick, navigate } from "../router";

  let {
    resultId,
    baseUrl = "",
  }: {
    resultId: string;
    baseUrl?: string;
  } = $props();

  const client = $derived(createConbenchClient(baseUrl));

  let vm = $state<ResultViewModel | null>(null);
  let errorMsg = $state<string | null>(null);
  let actionMsg = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let busyAction = $state<"annotation" | "delete" | null>(null);
  let canWrite = $state(false);
  let deleted = $state(false);

  onMount(async () => {
    void loadWriteCapability();
    try {
      vm = await loadResult(client, resultId);
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : String(err);
    }
  });

  async function loadWriteCapability() {
    try {
      const res = await client.GET("/api/auth/capabilities");
      canWrite = !res.error && res.data?.can_write_results === true;
    } catch {
      canWrite = false;
    }
  }

  async function setDistributionChange(value: boolean) {
    if (vm === null || busyAction !== null) return;
    actionMsg = null;
    actionError = null;
    busyAction = "annotation";
    try {
      const res = await client.PUT("/api/benchmark-results/{id}", {
        params: { path: { id: vm.id } },
        body: {
          change_annotations: {
            begins_distribution_change: value ? true : null,
          },
        },
      });
      if (res.error || !res.data) {
        actionError = detailOf(res.error, "failed to update annotations");
        return;
      }
      vm = resultViewModelFromDetail(res.data);
      actionMsg = "annotation updated";
    } catch (err) {
      actionError = err instanceof Error ? err.message : String(err);
    } finally {
      busyAction = null;
    }
  }

  async function deleteResult() {
    if (vm === null || busyAction !== null) return;
    if (!window.confirm(`Delete result ${vm.id}?`)) return;
    actionMsg = null;
    actionError = null;
    busyAction = "delete";
    try {
      const res = await client.DELETE("/api/benchmark-results/{id}", {
        params: { path: { id: vm.id } },
      });
      if (res.error) {
        actionError = detailOf(res.error, "failed to delete result");
        return;
      }
      deleted = true;
      vm = null;
      actionMsg = "result deleted";
    } catch (err) {
      actionError = err instanceof Error ? err.message : String(err);
    } finally {
      busyAction = null;
    }
  }

  function detailOf(error: unknown, fallback: string): string {
    if (error && typeof error === "object" && "detail" in error && typeof error.detail === "string") {
      return error.detail;
    }
    return fallback;
  }

  function go(e: MouseEvent, href: string) {
    if (!interceptNavClick(e)) return;
    e.preventDefault();
    navigate(href);
  }
</script>

{#if errorMsg}
  <main class="page result-page">
    <section class="panel state-panel">
      <h1>Result unavailable</h1>
      <p class="error">Failed to load result: {errorMsg}</p>
    </section>
  </main>
{:else if deleted}
  <main class="page result-page">
    <section class="panel state-panel">
      <h1>Result deleted</h1>
      {#if actionMsg}<p>{actionMsg}</p>{/if}
      <div class="action-row">
        <a class="button-pill primary" href="/series" onclick={(e) => go(e, "/series")}>Browse series</a>
      </div>
    </section>
  </main>
{:else if !vm}
  <main class="page result-page">
    <section class="panel state-panel">
      <h1>Loading result</h1>
      <p>Loading...</p>
    </section>
  </main>
{:else}
  <main class="page result-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Benchmark result</p>
        <h1>{vm.name}</h1>
        <p class="page-subtitle result-subtitle">
          {#if vm.paramsText}<span>{vm.paramsText}</span>{:else}<span>No benchmark parameters</span>{/if}
          {#if vm.contextText}<span>{vm.contextText}</span>{/if}
        </p>
      </div>
      <div class="header-actions">
        <div class="page-meta">
          <span>SVS {vm.svsText}</span>
          <span>{vm.hardwareName} ({vm.hardwareType})</span>
          <span title={vm.runId}>run {vm.displayRunId}</span>
        </div>
        <div class="action-row">
          <a
            class="button-pill primary"
            href={`/benchmarks/history/${resultId}`}
            onclick={(e) => go(e, `/benchmarks/history/${resultId}`)}
          >View trend</a>
          <a class="button-pill" href={vm.historyExportHref} download={`conbench-history-${vm.id}.json`}>
            Export history JSON
          </a>
        </div>
      </div>
    </header>

    {#if canWrite}
      <section class="panel action-panel" aria-label="Result actions">
        <h2>Actions</h2>
        <div class="action-row">
          {#if vm.beginsDistributionChange}
            <button
              type="button"
              class="button-pill"
              onclick={() => setDistributionChange(false)}
              disabled={busyAction !== null}
            >
              {busyAction === "annotation" ? "Saving..." : "Unmark distribution change"}
            </button>
          {:else}
            <button
              type="button"
              class="button-pill"
              onclick={() => setDistributionChange(true)}
              disabled={busyAction !== null}
            >
              {busyAction === "annotation" ? "Saving..." : "Mark distribution change"}
            </button>
          {/if}
          <button type="button" class="button-pill danger" onclick={deleteResult} disabled={busyAction !== null}>
            {busyAction === "delete" ? "Deleting..." : "Delete result"}
          </button>
        </div>
        {#if actionMsg}<p class="ok">{actionMsg}</p>{/if}
        {#if actionError}<p class="error">{actionError}</p>{/if}
      </section>
    {/if}

    <section class="panel result-section" aria-label="Result measurement">
      <h2>Measurement</h2>
      <dl class="compact-dl">
        <dt>SVS ({vm.svsType})</dt>
        <dd>{vm.svsText}</dd>
        {#if vm.iterations !== null}
          <dt>iterations</dt>
          <dd>{vm.iterations}</dd>
        {/if}
        {#each vm.aggregates as agg (agg.label)}
          <dt>{agg.label}</dt>
          <dd>{agg.value}</dd>
        {/each}
        <dt>less is better</dt>
        <dd>{vm.lessIsBetterText}</dd>
        <dt>time unit</dt>
        <dd>{vm.timeUnitText}</dd>
        <dt>raw data</dt>
        <dd>{vm.dataCountText}</dd>
        <dt>raw times</dt>
        <dd>{vm.timesCountText}</dd>
      </dl>
      {#if vm.error !== null}
        <div class="errbox" role="alert">
          <h3>error</h3>
          <pre>{JSON.stringify(vm.error, null, 2)}</pre>
        </div>
      {/if}
    </section>

    <section class="result-facts" aria-label="Result facts">
      <div class="panel result-section">
        <h2>Commit</h2>
        <dl class="compact-dl">
          {#if vm.commitSha !== null}
            <dt>sha</dt>
            <dd class="mono" title={vm.commitSha}>{vm.shortCommit}</dd>
          {/if}
          {#if vm.commitMessage !== null && vm.commitMessage !== ""}
            <dt>message</dt>
            <dd>{vm.commitMessage}</dd>
          {/if}
          {#if vm.commitDateText !== null}
            <dt>date</dt>
            <dd>{vm.commitDateText}</dd>
          {/if}
          <dt>repository</dt>
          <dd title={vm.repository}>{vm.repositoryLabel}</dd>
        </dl>
      </div>

      <div class="panel result-section">
        <h2>Run</h2>
        <dl class="compact-dl">
          <dt>run id</dt>
          <dd class="mono" title={vm.runId}>{vm.displayRunId}</dd>
          {#if vm.runTagsText}
            <dt>run tags</dt>
            <dd>{vm.runTagsText}</dd>
          {/if}
          {#if vm.runReason !== null}
            <dt>reason</dt>
            <dd>{vm.runReason}</dd>
          {/if}
          {#if vm.batchId !== null}
            <dt>batch</dt>
            <dd class="mono" title={vm.batchId}>{vm.displayBatchId}</dd>
          {/if}
          <dt>result time</dt>
          <dd>{vm.resultDateText}</dd>
          <dt>result id</dt>
          <dd class="mono" title={vm.id}>{vm.displayResultId}</dd>
        </dl>
      </div>

      <div class="panel result-section">
        <h2>Hardware</h2>
        <dl class="compact-dl">
          <dt>name</dt>
          <dd>{vm.hardwareName} ({vm.hardwareType})</dd>
          <dt>hardware hash</dt>
          <dd class="mono" title={vm.hardwareHash}>{vm.displayHardwareHash}</dd>
          <dt>history fingerprint</dt>
          <dd class="mono" title={vm.fingerprint}>{vm.displayFingerprint}</dd>
        </dl>
      </div>
    </section>

    <section class="result-metadata" aria-label="Result metadata">
      <h2>Metadata</h2>
      <div class="json-grid">
        {#each vm.jsonBlocks as block (block.label)}
          <details class="json-panel" open>
            <summary>{block.label}</summary>
            <pre>{block.value}</pre>
          </details>
        {/each}
      </div>
    </section>
</main>
{/if}

<style>
  .result-page {
    max-width: 1400px;
  }
  .header-actions {
    display: grid;
    justify-items: end;
    gap: 8px;
    min-width: min(100%, 420px);
  }
  .result-subtitle {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .action-panel,
  .result-section {
    padding: 12px;
  }
  .action-panel h2,
  .result-section h2,
  .result-metadata h2 {
    margin: 0 0 8px;
    font-size: 0.95rem;
  }
  .result-facts {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }
  .compact-dl {
    display: grid;
    grid-template-columns: minmax(7rem, max-content) minmax(0, 1fr);
    align-items: baseline;
    gap: 0.25rem 1rem;
    font-size: 0.85rem;
    margin: 0;
  }
  dt { color: var(--c-text-muted); }
  dd { margin: 0; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
  .ok { color: var(--c-success); }
  .result-metadata {
    min-width: 0;
  }
  .json-grid {
    min-width: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
  }
  summary {
    margin: -10px -10px 0;
    padding: 0.45rem 0.6rem;
    border-bottom: 1px solid var(--c-border-muted);
    color: var(--c-text-muted);
    font-size: 0.78rem;
    font-weight: 700;
    cursor: pointer;
  }
  pre {
    max-width: 100%;
    max-height: 340px;
    margin: 0;
    padding: 0.55rem 0.6rem;
    overflow: auto;
    background: var(--c-bg-inset);
    font-size: 0.74rem;
    line-height: 1.4;
  }
  .errbox { margin-top: 0.6rem; padding: 0.5rem 0.7rem; border: 1px solid var(--c-error);
            border-radius: 4px; background: var(--c-warn-bg); font-size: 0.8rem; }
  .errbox h3 { margin: 0 0 0.3rem; font-size: 0.8rem; color: var(--c-error); }
  .errbox pre { margin: 0; white-space: pre-wrap; }
  .error { color: var(--c-error); }
  .state-panel h1 {
    margin-bottom: 6px;
  }
  @media (max-width: 760px) {
    .header-actions {
      justify-items: stretch;
    }
    .result-facts,
    .json-grid { grid-template-columns: 1fr; }
    .compact-dl {
      grid-template-columns: minmax(6.5rem, 9rem) minmax(0, 1fr);
      column-gap: 0.75rem;
    }
  }
</style>
