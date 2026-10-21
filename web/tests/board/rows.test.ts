import { describe, expect, it } from "vitest";

import { boardRow, orderSources } from "../../src/board/rows";
import { mapOf, sectionOf } from "../fixtures";

describe("orderSources", () => {
  it("puts cited sections first and keeps the rest in source order", () => {
    expect(orderSources(["BNS:316", "BNS:318", "BNS:319"], ["BNS:318"])).toEqual(["BNS:318", "BNS:316", "BNS:319"]);
  });

  it("adds a cited section the sources did not list", () => {
    expect(orderSources(["BNS:316"], ["BNS:318"])).toEqual(["BNS:318", "BNS:316"]);
  });
});

describe("boardRow", () => {
  it("shows the IPC sections a BNS section took over", () => {
    const row = boardRow(sectionOf("BNS:318", "Cheating"), mapOf("BNS:318", [], ["IPC:415", "IPC:420"]), true);
    expect(row).toEqual({ id: "BNS:318", code: "BNS", number: "318", other: "IPC 415 +1", title: "Cheating", mark: "cited" });
  });

  it("shows the BNS section an IPC section became", () => {
    const row = boardRow(sectionOf("IPC:420", "Cheating and dishonestly inducing delivery of property"), mapOf("IPC:420", ["BNS:318"], []), false);
    expect(row.other).toBe("BNS 318");
    expect(row.mark).toBe("source");
  });

  it("names the offence, not the word punishment", () => {
    const row = boardRow(sectionOf("BNS:103", "Punishment for murder"), mapOf("BNS:103", [], ["IPC:302"]), true);
    expect(row.title).toBe("Murder");
  });

  it("says when a section has no listed counterpart", () => {
    const row = boardRow(sectionOf("BNS:48", "Abetment outside India"), mapOf("BNS:48", [], []), false);
    expect(row.other).toBe("NONE LISTED");
  });
});
