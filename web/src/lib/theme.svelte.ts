// Theme state: a user choice of system | light | dark, resolved to an applied
// light | dark and reflected on <html data-theme>. The inline script in
// index.html sets data-theme before first paint to avoid a flash; this module
// owns the choice afterwards and keeps it in sync with the OS when on "system".

export type ThemeChoice = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "conbench-theme";

// localStorage can throw (private mode, blocked third-party storage, quota), so
// every access is guarded. Persistence is best-effort: a failure must never stop
// the theme from being resolved and applied.
function readStored(): string | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStored(value: string | null): void {
  try {
    if (typeof localStorage === "undefined") return;
    if (value === null) {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, value);
    }
  } catch {
    // Ignore: the in-memory choice still drives the applied theme this session.
  }
}

function readStoredChoice(): ThemeChoice {
  const stored = readStored();
  return stored === "light" || stored === "dark" ? stored : "system";
}

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-color-scheme: dark)").matches
    : false;
}

let choice = $state<ThemeChoice>(readStoredChoice());
let systemDark = $state(systemPrefersDark());

function applyResolvedTheme(): void {
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", resolvedTheme());
  }
}

export function themeChoice(): ThemeChoice {
  return choice;
}

export function resolvedTheme(): ResolvedTheme {
  if (choice === "system") {
    return systemDark ? "dark" : "light";
  }
  return choice;
}

export function setTheme(next: ThemeChoice): void {
  choice = next;
  writeStored(next === "system" ? null : next);
  applyResolvedTheme();
}

const CYCLE: Record<ThemeChoice, ThemeChoice> = {
  system: "light",
  light: "dark",
  dark: "system",
};

export function cycleTheme(): void {
  setTheme(CYCLE[choice]);
}

if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (event) => {
    systemDark = event.matches;
    applyResolvedTheme();
  });
}
