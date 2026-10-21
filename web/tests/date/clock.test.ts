import { describe, expect, it } from "vitest";

import { clockFace, codeFor, spokenDate } from "../../src/date/clock";

describe("spokenDate", () => {
  it("writes the month in sentence case", () => {
    expect(spokenDate("2024-06-30")).toBe("30 Jun 2024");
  });

  it("is empty without a date", () => {
    expect(spokenDate("")).toBe("");
  });
});

describe("clockFace", () => {
  it("reads an ISO date as day, month and year flaps", () => {
    expect(clockFace("2024-08-15")).toBe("15 AUG 2024");
  });

  it("shows dashes when no date is set", () => {
    expect(clockFace("")).toBe("-- --- ----");
  });

  it("shows dashes for a malformed value", () => {
    expect(clockFace("2024-13-40")).toBe("-- --- ----");
  });
});

describe("codeFor", () => {
  it("is the IPC the day before the changeover", () => {
    expect(codeFor("2024-06-30")).toBe("IPC");
  });

  it("is the BNS on the day of the changeover", () => {
    expect(codeFor("2024-07-01")).toBe("BNS");
  });

  it("is unknown without a date", () => {
    expect(codeFor("")).toBeNull();
  });
});
