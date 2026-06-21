import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import StatusBadge from "./StatusBadge.svelte";

describe("StatusBadge", () => {
  it.each(["regressed", "improved", "stable", "insufficient"] as const)(
    "renders the %s status with its class",
    (status) => {
      render(StatusBadge, { props: { status } });
      const badge = screen.getByText(status);
      expect(badge).toHaveClass("badge", status);
    },
  );
});
