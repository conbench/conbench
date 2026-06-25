<script lang="ts">
  import type { BrowseRow, SortKey, SortSpec } from "../browse/transform";
  import { interceptNavClick } from "../router";
  import Sparkline from "./Sparkline.svelte";
  import StatusBadge from "./StatusBadge.svelte";

  let {
    rows,
    sort = null,
    onsort,
    onopen,
  }: {
    rows: BrowseRow[];
    sort?: SortSpec | null;
    onsort?: (key: SortKey) => void;
    onopen?: (row: BrowseRow) => void;
  } = $props();

  const HEADERS: { key: SortKey | null; label: string }[] = [
    { key: "name", label: "benchmark" },
    { key: null, label: "context" },
    { key: null, label: "hardware" },
    { key: "svs", label: "last value" },
    { key: "points", label: "points" },
    { key: null, label: "trend" },
    { key: null, label: "status" },
    { key: "commit", label: "last commit" },
  ];

  function arrow(key: SortKey): string {
    if (sort?.key !== key) return "";
    return sort.dir === "asc" ? " ^" : " v";
  }

  function ariaSort(key: SortKey | null): "ascending" | "descending" | undefined {
    if (key === null) return undefined;
    if (sort?.key !== key) return undefined;
    return sort.dir === "asc" ? "ascending" : "descending";
  }
</script>

<div class="table-panel browse-table-panel">
  <table class="data-table stacked-table browse-table">
    <colgroup>
      <col class="benchmark-col" />
      <col class="context-col" />
      <col class="hardware-col" />
      <col class="value-col" />
      <col class="points-col" />
      <col class="trend-col" />
      <col class="status-col" />
      <col class="commit-col" />
    </colgroup>
    <thead>
      <tr>
        {#each HEADERS as h (h.label)}
          <th aria-sort={ariaSort(h.key)}>
            {#if h.key !== null}
              {@const key = h.key}
              <button
                type="button"
                class="sort"
                aria-label={`Sort by ${h.label}`}
                aria-pressed={sort?.key === key}
                class:active={sort?.key === key}
                onclick={() => onsort?.(key)}
              >
                <span>{h.label}</span><span aria-hidden="true">{arrow(key)}</span>
              </button>
            {:else}
              {h.label}
            {/if}
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each rows as row (row.fingerprint)}
        <!-- The whole row is a click target as a pointer convenience. role="link"
             plus tabindex={-1} satisfy the a11y lint without adding a redundant
             tab stop; the name <a> below is the keyboard/screen-reader affordance. -->
        <tr
          role="link"
          aria-label={`Open series ${row.name}`}
          tabindex={-1}
          onclick={(e) => interceptNavClick(e) && onopen?.(row)}>
          <td class="name-cell" data-label="benchmark">
            <span class="identity-stack">
              <a
                class="row-primary-link"
                href={`/series/${row.fingerprint}`}
                onclick={(e) => {
                  if (!onopen || !interceptNavClick(e)) return;
                  e.preventDefault();
                  e.stopPropagation();
                  onopen(row);
                }}>{row.name}</a>
              {#if row.paramsText}<span class="metadata-line">{row.paramsText}</span>{/if}
            </span>
          </td>
          <td class="muted wrap-anywhere" data-label="context">{row.contextText}</td>
          <td class="wrap-anywhere" data-label="hardware">{row.hardwareName}</td>
          <td class="num-cell" data-label="last value">{row.svsText}</td>
          <td class="num-cell" data-label="points">{row.pointCount}</td>
          <td class="trend-cell" data-label="trend"><Sparkline values={row.sparkline} /></td>
          <td class="status-cell" data-label="status"><StatusBadge status={row.status} /></td>
          <td class="muted commit-cell" data-label="last commit">{row.commitSha} · {row.commitDateText}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .browse-table-panel {
    --stacked-label-width: 92px;
  }

  .browse-table {
    min-width: 980px;
  }

  .benchmark-col {
    width: 27%;
  }

  .context-col {
    width: 17%;
  }

  .hardware-col {
    width: 15%;
  }

  .value-col {
    width: 11%;
  }

  .points-col {
    width: 6%;
  }

  .trend-col {
    width: 8%;
  }

  .status-col {
    width: 7%;
  }

  .commit-col {
    width: 9%;
  }

  .browse-table tbody tr {
    cursor: pointer;
  }

  .name-cell {
    min-width: 0;
  }

  .identity-stack {
    display: grid;
    gap: 3px;
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .metadata-line {
    display: block;
    color: var(--c-text-faint);
    font-size: 0.74rem;
    line-height: 1.3;
    overflow-wrap: anywhere;
  }

  .muted {
    color: var(--c-text-muted);
  }

  .num-cell,
  .trend-cell,
  .status-cell {
    white-space: nowrap;
  }

  .commit-cell {
    white-space: normal;
  }

  .num-cell {
    font-variant-numeric: tabular-nums;
  }

  .trend-cell {
    padding-top: 9px;
  }

  .sort {
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    color: inherit;
    text-transform: inherit;
    letter-spacing: inherit;
    cursor: pointer;
    text-align: left;
  }

  .sort.active {
    color: var(--c-accent);
  }

  @media (max-width: 1120px) {
    .browse-table {
      min-width: 0;
    }

    .num-cell,
    .trend-cell,
    .status-cell,
    .commit-cell {
      white-space: normal;
    }
  }
</style>
