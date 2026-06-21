import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import TopBar from "./TopBar.svelte";

// Modified clicks fall through to the anchor's default action; jsdom does not
// implement navigation and would log to stderr. Swallow the default here so the
// component's behavior is unchanged but test output stays clean.
const swallowAnchorNavigation = (e: Event) => {
  const target = e.target;
  if (target instanceof Element && target.closest("a")) {
    e.preventDefault();
  }
};
beforeEach(() => {
  document.addEventListener("click", swallowAnchorNavigation);
  window.history.replaceState(null, "", "/");
});
afterEach(() => document.removeEventListener("click", swallowAnchorNavigation));

describe("TopBar", () => {
  it("renders the brand as a home link", () => {
    render(TopBar, { props: {} });
    expect(screen.getByRole("link", { name: "Conbench" })).toHaveAttribute("href", "/");
  });

  it("exposes primary product navigation", () => {
    render(TopBar, { props: { routeName: "compare" } });
    const nav = screen.getByRole("navigation", { name: "Primary navigation" });
    expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
    expect(within(nav).getByRole("link", { name: "Browse" })).toHaveAttribute("href", "/series");
    expect(within(nav).getByRole("link", { name: "Results" })).toHaveAttribute("href", "/results");
    expect(within(nav).getByRole("link", { name: "Compare" })).toHaveAttribute("href", "/compare");
    expect(within(nav).getByRole("link", { name: "CI Reports" })).toHaveAttribute("href", "/ci/report");
    expect(within(nav).getByRole("link", { name: "Account" })).toHaveAttribute("href", "/account");
    expect(within(nav).getByRole("link", { name: "API Docs" })).toHaveAttribute("href", "/docs");
    expect(within(nav).getByRole("link", { name: "Compare" })).toHaveAttribute("aria-current", "page");
  });

  it("exposes global series search with stable role and label", () => {
    render(TopBar, { props: {} });
    const search = screen.getByRole("search", { name: "Global series search" });
    expect(within(search).getByRole("searchbox", { name: "Series search query" })).toBeInTheDocument();
    expect(within(search).getByRole("button", { name: "Search series" })).toBeInTheDocument();
  });

  it("navigates to series with q and default filters on search submit", async () => {
    render(TopBar, { props: {} });
    const box = screen.getByRole("searchbox", { name: "Series search query" });
    await fireEvent.input(box, { target: { value: "tpch " } });
    await fireEvent.submit(box.closest("form")!);
    expect(window.location.pathname).toBe("/series");
    expect(window.location.search).toBe("?q=tpch");
  });

  it("navigates to series when the explicit search control is clicked", async () => {
    render(TopBar, { props: {} });
    const box = screen.getByRole("searchbox", { name: "Series search query" });
    await fireEvent.input(box, { target: { value: "arrow " } });
    await fireEvent.click(screen.getByRole("button", { name: "Search series" }));
    expect(window.location.pathname).toBe("/series");
    expect(window.location.search).toBe("?q=arrow");
  });

  it("seeds the box from the route's q", () => {
    render(TopBar, { props: { initialQ: "demo" } });
    expect(screen.getByRole("searchbox", { name: "Series search query" })).toHaveValue("demo");
  });

  it("marks active deep-route navigation as a current location, not the current page", () => {
    render(TopBar, { props: { routeName: "series-leaf" } });
    const nav = screen.getByRole("navigation", { name: "Primary navigation" });
    const activeLink = within(nav).getByRole("link", { name: "Browse", current: "location" });
    expect(activeLink).toHaveAttribute("href", "/series");
    expect(activeLink).toHaveTextContent("Browse");
    expect(within(nav).queryByRole("link", { name: "Browse", current: "page" })).not.toBeInTheDocument();
  });

  it("leaves modified brand clicks to the browser", async () => {
    window.history.replaceState(null, "", "/?q=x");
    render(TopBar, { props: {} });
    await fireEvent.click(screen.getByRole("link", { name: "Conbench" }), { metaKey: true });
    // navigate() was not called: the URL still carries the original search.
    expect(window.location.search).toBe("?q=x");
  });
});
