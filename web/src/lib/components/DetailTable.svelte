<script lang="ts">
  import { formatMeasurement } from "../format";
  import { interceptNavClick } from "../router";
  import type { TableRow } from "../series/transform";

  let {
    rows,
    selectedIndex = null,
    onselect,
    onopen,
  }: {
    rows: TableRow[];
    selectedIndex?: number | null;
    onselect?: (index: number) => void;
    onopen?: (row: TableRow) => void;
  } = $props();

  function z(value: number | null): string {
    return value === null ? "—" : value.toFixed(2);
  }
</script>

<div class="detail-list">
  <table class="detail">
    <thead>
      <tr>
        <th>commit</th>
        <th>SVS</th>
        <th>z</th>
        <th>flags</th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row (row.index)}
        <!-- Rows are a pointer convenience for selection; the commit link is the
             keyboard/screen-reader affordance and opens the result. -->
        <tr class:selected={row.index === selectedIndex} onclick={() => onselect?.(row.index)}>
          <td class="commit" data-label="commit">
            <span class="cell-value">
              <a
                href={`/results/${row.resultId}`}
                onclick={(e) => {
                  if (!onopen || !interceptNavClick(e)) return;
                  e.preventDefault();
                  e.stopPropagation();
                  onopen(row);
                }}
              >{row.commitHash}</a>
              <span class="msg">{row.commitMessage}</span>
            </span>
          </td>
          <td class="num" data-label="SVS">{formatMeasurement(row.svs, row.unit)}</td>
          <td class="num" data-label="z">{z(row.z)}</td>
          <td class="flags" data-label="flags">{row.flags}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .detail-list { max-width: 100%; }
  .detail { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
  .detail th, .detail td { text-align: left; padding: 0.3rem 0.6rem; border-bottom: 1px solid var(--c-border); overflow-wrap: anywhere; }
  .detail th { color: var(--c-text-muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0; }
  .detail tbody tr { cursor: pointer; }
  .detail tbody tr.selected { background: var(--c-row-hover); }
  .commit a { color: inherit; font-weight: 600; text-decoration: none; }
  .commit a:hover { color: var(--c-accent); }
  .cell-value {
    display: block;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .commit a, .msg { overflow-wrap: anywhere; }
  .msg { display: block; color: var(--c-text-faint); font-size: 0.72rem; }
  .num { font-variant-numeric: tabular-nums; }
  .flags { color: var(--c-text-muted); font-size: 0.78rem; }
  @media (max-width: 760px) {
    .detail, .detail thead, .detail tbody, .detail tr, .detail td {
      display: block;
    }
    .detail thead {
      display: none;
    }
    .detail tr {
      padding: 0.55rem 0;
      border-bottom: 1px solid var(--c-border);
    }
    .detail td {
      display: grid;
      grid-template-columns: minmax(4.5rem, 28%) 1fr;
      gap: 0.65rem;
      border-bottom: 0;
      padding: 0.16rem 0;
    }
    .detail td::before {
      content: attr(data-label);
      color: var(--c-text-muted);
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0;
    }
  }
</style>
