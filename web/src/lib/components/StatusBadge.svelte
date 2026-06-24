<script lang="ts">
  import type { SeriesStatus } from "../browse/transform";

  let { status }: { status: SeriesStatus } = $props();
</script>

<span class={`badge ${status}`}>
  <span class="dot" aria-hidden="true"></span>
  {status}
</span>

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    width: fit-content;
    max-width: 100%;
    padding: 0.12rem 0.5rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--c-text-muted);
    background: var(--c-badge-bg);
    border: 1px solid var(--c-border-muted);
    white-space: nowrap;
  }
  .dot {
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 999px;
    background: var(--c-unknown);
  }
  .regressed .dot {
    background: var(--c-error);
  }
  .improved .dot {
    background: var(--c-success);
  }
  .stable .dot {
    background: var(--c-stable);
  }
  .insufficient .dot {
    background: var(--c-insufficient);
  }
</style>
