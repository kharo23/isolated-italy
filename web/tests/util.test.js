import { describe, expect, it } from "vitest";
import { esc, formatCompact, formatInt } from "../src/util.js";

describe("esc", () => {
  it("escapes HTML special characters", () => {
    expect(esc('<a href="x">&\'</a>')).toBe("&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;");
  });
  it("tolerates null and numbers", () => {
    expect(esc(null)).toBe("");
    expect(esc(42)).toBe("42");
  });
});

describe("formatting", () => {
  it("formats compact counts", () => {
    expect(formatCompact(4513824)).toBe("4.5 M");
    expect(formatCompact(159193)).toBe("159k");
  });
  it("groups thousands", () => {
    expect(formatInt(1234567)).toBe("1,234,567");
  });
});
