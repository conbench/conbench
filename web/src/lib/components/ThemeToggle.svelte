<script lang="ts">
  import { cycleTheme, themeChoice, type ThemeChoice } from "../theme.svelte";

  const choiceLabel: Record<ThemeChoice, string> = {
    system: "System",
    light: "Light",
    dark: "Dark",
  };
  const nextChoice: Record<ThemeChoice, ThemeChoice> = {
    system: "light",
    light: "dark",
    dark: "system",
  };

  let choice = $derived(themeChoice());
  let label = $derived(
    `Theme: ${choiceLabel[choice]} (switch to ${choiceLabel[nextChoice[choice]]})`,
  );
</script>

<button type="button" class="theme-toggle" aria-label={label} title={label} onclick={cycleTheme}>
  {#if choice === "system"}
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <rect x="1.5" y="2.5" width="13" height="9" rx="1.2" />
      <line x1="5.5" y1="14" x2="10.5" y2="14" />
      <line x1="8" y1="11.5" x2="8" y2="14" />
    </svg>
  {:else if choice === "light"}
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <circle cx="8" cy="8" r="3" />
      <line x1="8" y1="1" x2="8" y2="2.5" />
      <line x1="8" y1="13.5" x2="8" y2="15" />
      <line x1="1" y1="8" x2="2.5" y2="8" />
      <line x1="13.5" y1="8" x2="15" y2="8" />
      <line x1="3.05" y1="3.05" x2="4.1" y2="4.1" />
      <line x1="11.9" y1="11.9" x2="12.95" y2="12.95" />
      <line x1="3.05" y1="12.95" x2="4.1" y2="11.9" />
      <line x1="11.9" y1="4.1" x2="12.95" y2="3.05" />
    </svg>
  {:else}
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d="M13.4 9.7A5.5 5.5 0 0 1 6.3 2.6 5.5 5.5 0 1 0 13.4 9.7Z" />
    </svg>
  {/if}
</button>

<style>
  .theme-toggle {
    width: 32px;
    height: 32px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
    padding: 0;
    border: 1px solid var(--c-border);
    border-radius: var(--radius-md);
    background: var(--c-surface);
    color: var(--c-text-muted);
    cursor: pointer;
    box-shadow: var(--shadow-hairline);
    transition:
      background-color 120ms ease,
      border-color 120ms ease,
      color 120ms ease;
  }

  .theme-toggle:hover {
    border-color: var(--c-accent);
    color: var(--c-accent);
    background: var(--c-accent-soft);
  }

  .theme-toggle svg {
    width: 16px;
    height: 16px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.5;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .theme-toggle :global(svg rect) {
    fill: none;
  }
</style>
