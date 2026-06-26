<script lang="ts">
  import { onMount } from "svelte";

  import AccountPage from "./lib/components/AccountPage.svelte";
  import BatchPage from "./lib/components/BatchPage.svelte";
  import CIReportPage from "./lib/components/CIReportPage.svelte";
  import ComparePage from "./lib/components/ComparePage.svelte";
  import RecentRunsHome from "./lib/components/RecentRunsHome.svelte";
  import ResultPage from "./lib/components/ResultPage.svelte";
  import ResultsPage from "./lib/components/ResultsPage.svelte";
  import RunPage from "./lib/components/RunPage.svelte";
  import SeriesBrowse from "./lib/components/SeriesBrowse.svelte";
  import TopBar from "./lib/components/TopBar.svelte";
  import TrendPage from "./lib/components/TrendPage.svelte";
  import { matchRoute, NAVIGATE_EVENT, type Route } from "./lib/router";

  function currentRoute(): Route {
    return matchRoute(window.location.pathname, window.location.search);
  }

  let route = $state<Route>(currentRoute());

  // Re-resolve on browser back/forward and on in-app navigate() pushes.
  onMount(() => {
    const resolve = () => {
      route = currentRoute();
    };
    window.addEventListener("popstate", resolve);
    window.addEventListener(NAVIGATE_EVENT, resolve);
    return () => {
      window.removeEventListener("popstate", resolve);
      window.removeEventListener(NAVIGATE_EVENT, resolve);
    };
  });
</script>

<div class="app-shell">
  <TopBar initialQ={route.name === "browse" ? route.query.q : ""} routeName={route.name} />

  <div class="app-content">
    {#if route.name === "home"}
      {#key route.query.repository}
        <RecentRunsHome query={route.query} />
      {/key}
    {:else if route.name === "browse"}
      <SeriesBrowse query={route.query} />
    {:else if route.name === "series-leaf"}
      {#key route.resultId}
        <TrendPage source={{ kind: "result", resultId: route.resultId }} query={route.query} />
      {/key}
    {:else if route.name === "trend"}
      {#key route.fingerprint}
        <TrendPage source={{ kind: "fingerprint", fingerprint: route.fingerprint }} query={route.query} />
      {/key}
    {:else if route.name === "result"}
      {#key route.resultId}
        <ResultPage resultId={route.resultId} />
      {/key}
    {:else if route.name === "results-list"}
      {#key `${route.query.runID}|${route.query.batchID}|${route.query.runReason}|${route.query.earliestTimestamp}|${route.query.latestTimestamp}`}
        <ResultsPage query={route.query} />
      {/key}
    {:else if route.name === "run"}
      {#key route.runId}
        <RunPage runId={route.runId} />
      {/key}
    {:else if route.name === "batch"}
      {#key route.batchId}
        <BatchPage batchId={route.batchId} />
      {/key}
    {:else if route.name === "compare"}
      {#key `${route.query.baseline}|${route.query.contender}`}
        <ComparePage query={route.query} />
      {/key}
    {:else if route.name === "ci-report"}
      {#key `${route.query.repository}|${route.query.commit}|${route.query.runIDs}|${route.query.baselineRunIDs}|${route.query.baseline}|${route.query.threshold}|${route.query.thresholdZ}`}
        <CIReportPage query={route.query} />
      {/key}
    {:else if route.name === "account"}
      <AccountPage />
    {:else}
      <main class="not-found">
        <h1>Not found</h1>
        <p>No page for <code>{window.location.pathname}</code>. <a href="/series">Browse all series</a>.</p>
      </main>
    {/if}
  </div>

  <footer class="status-bar">
    <span>Conbench</span>
    <span class="status-sep">·</span>
    <span>public reads</span>
    <span class="status-sep">·</span>
    <a href="/openapi.yaml">OpenAPI</a>
  </footer>
</div>
