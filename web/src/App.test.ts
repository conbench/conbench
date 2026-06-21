import { render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.hoisted(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

import App from "./App.svelte";

describe("App shell", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ runs: [] }), { status: 200 })),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses product-facing status text", () => {
    render(App);

    const footer = screen.getByRole("contentinfo");
    expect(footer).toHaveTextContent("Conbench");
    expect(footer).toHaveTextContent("public reads");
    expect(footer).not.toHaveTextContent(/rewrite/i);
  });
});
