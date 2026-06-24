import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import Sparkline from "./Sparkline.svelte";

describe("Sparkline", () => {
  it("renders a polyline for 2+ values", () => {
    render(Sparkline, { props: { values: [1, 2, 1.5] } });
    const svg = screen.getByRole("img", { name: /sparkline of 3 points/ });
    expect(svg.querySelector("polyline")).not.toBeNull();
  });

  it("renders a dot for a single value", () => {
    render(Sparkline, { props: { values: [1] } });
    const svg = screen.getByRole("img", { name: /sparkline of 1 point/ });
    expect(svg.querySelector("circle")).not.toBeNull();
  });

  it("renders a placeholder for no values", () => {
    render(Sparkline, { props: { values: [] } });
    expect(screen.getByLabelText("no sparkline")).toHaveTextContent("—");
  });
});
