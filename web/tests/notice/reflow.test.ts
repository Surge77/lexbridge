import { describe, expect, it } from "vitest";

import { reflow } from "../../src/notice/reflow";

describe("reflow", () => {
  it("joins lines the PDF broke mid-sentence", () => {
    expect(reflow("Whoever, by deceiving any person, fraudulently induces the\nperson so deceived")).toBe(
      "Whoever, by deceiving any person, fraudulently induces the person so deceived",
    );
  });

  it("keeps a break before a numbered sub-section", () => {
    expect(reflow("is said to cheat.\n(2) Whoever cheats")).toBe("is said to cheat.\n(2) Whoever cheats");
  });

  it("keeps a break before an explanation or the illustrations", () => {
    expect(reflow("to cheat.\nExplanation. A dishonest\nconcealment.\nIllustrations.\n(a) A, by")).toBe(
      "to cheat.\nExplanation. A dishonest concealment.\nIllustrations.\n(a) A, by",
    );
  });
});
