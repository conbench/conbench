import { describe, expect, it } from "vitest";

import { compactAxisValue } from "./chart-format";

describe("compactAxisValue", () => {
  it("formats large throughput values without long clipped labels", () => {
    expect(compactAxisValue(607_822_601.56)).toBe("608M");
    expect(compactAxisValue(1_397_000_000)).toBe("1.4B");
  });

  it("keeps small values readable", () => {
    expect(compactAxisValue(0)).toBe("0");
    expect(compactAxisValue(0.01234)).toBe("0.012");
    expect(compactAxisValue(-42.4)).toBe("-42.4");
  });
});
