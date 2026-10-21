import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../src/app";
import { answerOf, jsonResponse, mapOf, sectionOf } from "../fixtures";

const SECTIONS: Record<string, [ReturnType<typeof sectionOf>, ReturnType<typeof mapOf>]> = {
  "BNS:318": [sectionOf("BNS:318", "Cheating"), mapOf("BNS:318", [], ["IPC:415", "IPC:420"])],
  "BNS:316": [sectionOf("BNS:316", "Criminal breach of trust"), mapOf("BNS:316", [], ["IPC:405"])],
};

function serve(body: unknown, status = 200) {
  vi.stubGlobal("fetch", vi.fn(async (path: string) => {
    if (path === "/chat") return jsonResponse(status, body);
    if (path === "/feedback") return new Response(null, { status: 204 });
    const [, kind = "", id = ""] = path.split("/");
    const found = SECTIONS[decodeURIComponent(id)];
    if (!found) return jsonResponse(404, { error: { message: "No such section in this bundle." } });
    return jsonResponse(200, kind === "section" ? found[0] : found[1]);
  }));
}

function receiptView() {
  const user = userEvent.setup();
  render(<App />);
  return user;
}

beforeEach(() => {
  vi.stubGlobal("matchMedia", undefined);
  window.history.replaceState(null, "", "/");
  window.localStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

describe("receipt view", () => {
  it("is the main view, opening on a labelled sample receipt", () => {
    serve(answerOf());
    receiptView();
    expect(screen.getByText("SAMPLE RECEIPT")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Receipt", pressed: true })).toBeTruthy();
    expect(document.documentElement.dataset.view).toBe("receipt");
  });

  it("opens the board when the reader chose it before", async () => {
    serve(answerOf());
    window.localStorage.setItem("lexbridge.view", "board");
    render(<App />);
    expect(await screen.findByRole("button", { name: "Ask" }, { timeout: 15_000 })).toBeTruthy();
  });

  it("prints the answer with its citation, related sections and a barcode", async () => {
    serve(answerOf());
    const user = receiptView();
    await user.click(screen.getByRole("button", { name: "Print answer" }));

    const printer = screen.getByRole("region", { name: "Your answer" });
    expect(await within(printer).findByText(/BNS section 318 applies/)).toBeTruthy();
    expect(within(printer).getByText("CITED, CHECKED AGAINST THE ACT")).toBeTruthy();
    expect(within(printer).getByText("Criminal breach of trust")).toBeTruthy();
    expect(within(printer).getByRole("img", { name: /Barcode of trace/ })).toBeTruthy();
    expect(await within(printer).findByRole("heading", { name: "BNS 318. Cheating." })).toBeTruthy();
  });

  it("prints a slip for a related section", async () => {
    serve(answerOf());
    const user = receiptView();
    await user.click(screen.getByRole("button", { name: "Print answer" }));
    await user.click(await screen.findByRole("button", { name: /BNS 316/ }));
    expect(await screen.findByRole("heading", { name: "BNS 316. Criminal breach of trust." })).toBeTruthy();
  });

  it("prints why a question was not answered", async () => {
    serve({ error: { message: "Too many requests; please wait a minute." } }, 429);
    const user = receiptView();
    await user.click(screen.getByRole("button", { name: "Print answer" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Too many requests");
  });

  it("names the code in force for the date entered", async () => {
    serve(answerOf());
    const user = receiptView();
    await user.type(screen.getByLabelText("Date of the offence, if you know it"), "2024-05-02");
    expect(screen.getByText("2 May 2024: the Indian Penal Code applies.")).toBeTruthy();
  });

  it("switches to the board, remembers it, and comes back", async () => {
    serve(answerOf());
    const user = receiptView();
    await user.click(screen.getByRole("button", { name: "Board" }));
    expect(await screen.findByRole("button", { name: "Ask" }, { timeout: 15_000 })).toBeTruthy();
    expect(window.localStorage.getItem("lexbridge.view")).toBe("board");
    expect(window.location.search).toBe("?view=board");

    await user.click(screen.getByRole("button", { name: "Receipt" }));
    expect(screen.getByRole("button", { name: "Print answer" })).toBeTruthy();
    expect(window.location.search).toBe("");
  });
});
