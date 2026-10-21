import { describe, expect, it } from "vitest";

import { flapPath, fit, fitWords } from "../../src/board/flap";

describe("fit", () => {
  it("uppercases and pads text to the board width", () => {
    expect(fit("bns", 5)).toBe("BNS  ");
  });

  it("cuts text that is wider than the board", () => {
    expect(fit("Punishment for murder", 10)).toBe("PUNISHMENT");
  });
});

describe("fitWords", () => {
  it("cuts a long name at the last whole word", () => {
    expect(fitWords("Criminal breach of trust", 20)).toBe("CRIMINAL BREACH".padEnd(20, " "));
  });

  it("cuts mid-word only when the first word alone is too long", () => {
    expect(fitWords("Counterfeiting", 6)).toBe("COUNTE");
  });

  it("never ends on a dangling short word", () => {
    expect(fitWords("Cheating by personation", 20)).toBe("CHEATING".padEnd(20, " "));
  });

  it("leaves a name that fits", () => {
    expect(fitWords("Cheating", 10)).toBe("CHEATING  ");
  });
});

describe("flapPath", () => {
  it("is empty when the flap already shows the target", () => {
    expect(flapPath("A", "A")).toEqual([]);
  });

  it("steps forward through the alphabet to the target", () => {
    expect(flapPath("A", "D")).toEqual(["B", "C", "D"]);
  });

  it("wraps around the end of the alphabet", () => {
    const path = flapPath("9", "B");
    expect(path.at(-1)).toBe("B");
    expect(path).toContain(" ");
  });

  it("jumps straight to a character the flaps do not carry", () => {
    expect(flapPath("A", "é")).toEqual(["é"]);
  });
});
