<script lang="ts">
  // Test-only stand-in: uPlot requires a real canvas 2D context, which jsdom
  // lacks. TrendPage.test.ts vi.mocks SeriesChart.svelte with this stub so the
  // page's states, controls, and wiring are testable.
  import type { SeriesPoint } from "../series/transform";

  let {
    points,
    currentResultId = null,
  }: {
    points: SeriesPoint[];
    currentResultId?: string | null;
  } = $props();

  let currentIndex = $derived(
    currentResultId === null ? -1 : points.findIndex((p) => p.resultId === currentResultId),
  );
</script>

<div class="chart-stub" data-points={points.length} data-current-index={currentIndex}></div>
