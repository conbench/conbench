<script lang="ts">
  import { DEFAULT_BROWSE_QUERY, formatBrowseQuery, interceptNavClick, navigate, type Route } from "../router";
  import ThemeToggle from "./ThemeToggle.svelte";

  let { initialQ = "", routeName = "browse" }: { initialQ?: string; routeName?: Route["name"] } = $props();

  // term is writable (bind:value below), so it must be $state, not $derived.
  // Seeding it from the initialQ prop triggers state_referenced_locally
  // ("will never update"), but seeding once is exactly what we want — the
  // $effect below re-syncs term on later route changes.
  // svelte-ignore state_referenced_locally
  let term = $state(initialQ);

  // Keep the box in sync when the route's q changes underneath (back/forward).
  $effect(() => {
    term = initialQ;
  });

  // A global search is a fresh query: it intentionally resets the other filters.
  function submit(e: SubmitEvent) {
    e.preventDefault();
    navigate(`/series${formatBrowseQuery({ ...DEFAULT_BROWSE_QUERY, q: term.trim() })}`);
  }

  const nav: Array<{ label: string; href: string; route: Route["name"]; active: Array<Route["name"]> }> = [
    { label: "Home", href: "/", route: "home", active: ["home", "run", "batch"] },
    { label: "Browse", href: "/series", route: "browse", active: ["browse", "trend", "series-leaf"] },
    { label: "Results", href: "/results", route: "results-list", active: ["results-list", "result"] },
    { label: "Compare", href: "/compare", route: "compare", active: ["compare"] },
    { label: "CI Reports", href: "/ci/report", route: "ci-report", active: ["ci-report"] },
    { label: "Account", href: "/account", route: "account", active: ["account"] },
  ];

  function go(e: MouseEvent, href: string) {
    if (!interceptNavClick(e)) return;
    e.preventDefault();
    navigate(href);
  }

  function active(item: { active: Array<Route["name"]> }): boolean {
    return item.active.includes(routeName);
  }

  function ariaCurrent(item: { route: Route["name"]; active: Array<Route["name"]> }): "page" | "location" | undefined {
    if (!active(item)) return undefined;
    return routeName === item.route ? "page" : "location";
  }
</script>

<header class="topbar">
  <a class="brand" href="/" onclick={(e) => go(e, "/")}>
    <span class="brand-mark" aria-hidden="true">C</span>
    <span class="brand-name">Conbench</span>
  </a>
  <nav class="primary-nav" aria-label="Primary navigation">
    {#each nav as item (item.href)}
      <a
        class="nav-link"
        class:active={active(item)}
        aria-current={ariaCurrent(item)}
        href={item.href}
        onclick={(e) => go(e, item.href)}
      >{item.label}</a>
    {/each}
    <a class="nav-link docs-link" href="/docs">API Docs</a>
  </nav>
  <div class="header-end">
    <form class="search" role="search" aria-label="Global series search" onsubmit={submit}>
      <label class="sr-only" for="topbar-series-search">Series search query</label>
      <div class="search-control">
        <span class="search-prefix" aria-hidden="true">series</span>
        <input
          id="topbar-series-search"
          type="search"
          placeholder="name, tag, context"
          autocomplete="off"
          spellcheck="false"
          bind:value={term}
        />
        <button type="submit" class="search-submit" aria-label="Search series">Search</button>
      </div>
    </form>
    <ThemeToggle />
  </div>
</header>

<style>
  .topbar {
    min-height: var(--app-header-height);
    display: grid;
    grid-template-columns: auto minmax(320px, 1fr) minmax(280px, 420px);
    align-items: center;
    gap: 10px;
    padding: 7px 12px;
    background: var(--c-shell);
    border-bottom: 1px solid var(--c-border);
    box-shadow: 0 1px 0 rgba(16, 24, 40, 0.04), 0 8px 18px rgba(16, 24, 40, 0.04);
    flex-shrink: 0;
    position: sticky;
    top: 0;
    z-index: 20;
  }

  .brand {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-width: max-content;
    font-weight: 700;
    font-size: 0.95rem;
    color: var(--c-text);
    text-decoration: none;
    white-space: nowrap;
  }
  .brand-mark {
    width: 26px;
    height: 26px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid color-mix(in srgb, var(--c-accent) 42%, transparent);
    border-radius: var(--radius-md);
    background: var(--c-accent);
    color: var(--c-on-accent);
    font-size: 0.78rem;
    font-weight: 800;
  }

  .brand-name {
    letter-spacing: 0;
  }

  .primary-nav {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 2px;
    border: 1px solid var(--c-border-muted);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--c-bg-inset) 72%, var(--c-surface));
    overflow-x: auto;
    overscroll-behavior-x: contain;
    scrollbar-width: none;
  }

  .primary-nav::-webkit-scrollbar {
    display: none;
  }

  .nav-link {
    position: relative;
    height: 30px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0 10px;
    border-radius: var(--radius-sm);
    color: var(--c-text-muted);
    text-decoration: none;
    font-size: 0.78rem;
    font-weight: 650;
    letter-spacing: 0;
    white-space: nowrap;
    flex: 0 0 auto;
  }

  .nav-link:hover {
    background: var(--c-surface-hover);
    color: var(--c-text);
  }

  .nav-link.active {
    color: var(--c-text);
    background: var(--c-surface);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--c-accent) 25%, var(--c-border-muted));
  }

  .nav-link.active::after {
    content: "";
    position: absolute;
    right: 10px;
    bottom: 4px;
    left: 10px;
    height: 1px;
    border-radius: 999px;
    background: var(--c-accent);
  }

  .header-end {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .search {
    min-width: 0;
    flex: 1 1 auto;
  }

  .search-control {
    height: 32px;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 4px 0 9px;
    border: 1px solid var(--c-border);
    border-radius: var(--radius-md);
    background: var(--c-surface);
    color: var(--c-text-muted);
    box-shadow: var(--shadow-hairline);
  }

  .search-control:focus-within {
    border-color: var(--c-accent);
    box-shadow: 0 0 0 3px var(--c-focus-ring);
  }

  .search-prefix {
    color: var(--c-text-faint);
    font-size: 0.68rem;
    font-weight: 750;
    line-height: 1;
    text-transform: uppercase;
  }

  .search input {
    min-width: 0;
    width: 100%;
    height: 30px;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--c-text);
    font-size: 0.8rem;
  }

  .search input:focus-visible {
    outline: 2px solid var(--c-accent);
    outline-offset: 2px;
  }

  .search input::placeholder {
    color: var(--c-text-faint);
  }

  .search-submit {
    height: 24px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0 8px;
    border: 1px solid color-mix(in srgb, var(--c-accent) 40%, var(--c-border-muted));
    border-radius: var(--radius-sm);
    background: var(--c-accent);
    color: var(--c-on-accent);
    cursor: pointer;
    font-size: 0.72rem;
    font-weight: 750;
    line-height: 1;
    white-space: nowrap;
  }

  .search-submit:hover {
    background: var(--c-accent-strong);
  }

  .search-submit:focus-visible {
    outline: 2px solid var(--c-accent);
    outline-offset: 2px;
  }

  @media (forced-colors: active) {
    .search-control:focus-within {
      outline: 2px solid Highlight;
      outline-offset: 2px;
      box-shadow: none;
    }

    .search input:focus-visible {
      outline-color: Highlight;
    }
  }

  @media (max-width: 1120px) {
    .topbar {
      grid-template-columns: auto minmax(180px, 1fr);
      grid-template-areas:
        "brand search"
        "nav nav";
      align-items: center;
      padding: 7px 8px;
    }

    .brand {
      grid-area: brand;
    }

    .primary-nav {
      grid-area: nav;
      width: 100%;
      padding-bottom: 3px;
    }

    .header-end {
      grid-area: search;
    }
  }

  @media (max-width: 520px) {
    .topbar {
      grid-template-columns: minmax(0, 1fr);
      grid-template-areas:
        "brand"
        "search"
        "nav";
    }

    .brand,
    .header-end,
    .primary-nav {
      width: 100%;
    }

    .primary-nav {
      flex-wrap: wrap;
      row-gap: 4px;
      overflow-x: visible;
      padding: 2px 0 0;
    }

    .nav-link {
      min-height: 30px;
      padding: 0 9px;
      font-size: 0.74rem;
    }
  }
</style>
