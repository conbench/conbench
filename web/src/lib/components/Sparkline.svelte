<script lang="ts">
  import { sparklinePoints } from "../browse/transform";

  let {
    values,
    width = 96,
    height = 20,
  }: {
    values: number[];
    width?: number;
    height?: number;
  } = $props();

  const PAD = 2;
  let points = $derived(sparklinePoints(values, width, height, PAD));
  let label = $derived(`sparkline of ${values.length} point${values.length === 1 ? "" : "s"}`);
</script>

{#if values.length === 0}
  <span class="empty" aria-label="no sparkline">—</span>
{:else}
  <svg viewBox={`0 0 ${width} ${height}`} {width} {height} role="img" aria-label={label}>
    {#if values.length === 1}
      <circle cx={width / 2} cy={height / 2} r="2" fill="var(--c-accent)" />
    {:else}
      <polyline {points} fill="none" stroke="var(--c-accent)" stroke-width="1.5" />
    {/if}
  </svg>
{/if}

<style>
  .empty {
    color: var(--c-insufficient);
  }
  svg {
    display: block;
  }
</style>
