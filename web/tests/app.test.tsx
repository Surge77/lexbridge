import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatAnswer } from "../src/api";
import { App } from "../src/app";
import { answerOf, jsonResponse, mapOf, sectionOf } from "./fixtures";

const SECTIONS = {
  "BNS:318": [sectionOf("BNS:318", "Cheating", "318. Cheating. (1) Whoever, by deceiving any person, is said to cheat."), mapOf("BNS:318", [], ["IPC:415", "IPC:420"])],
  "BNS:316": [sectionOf("BNS:316", "Criminal breach of trust"), mapOf("BNS:316", [], ["IPC:405"])],
} as const;

function serve(answer: ChatAnswer | { status: number; body: unknown }) {
  const fetchMock = vi.fn(async (path: string) => {
    if (path === "/chat") return "trace_id" in answer ? jsonResponse(200, answer) : jsonResponse(answer.status, answer.body);
    if (path === "/feedback") return new Response(null, { status: 204 });
    const [, kind = "", id = ""] = path.split("/");
    const found = SECTIONS[decodeURIComponent(id) as keyof typeof SECTIONS];
    if (!found) return jsonResponse(404, { error: { message: "No such section in this bundle." } });
    return jsonResponse(200, kind === "section" ? found[0] : found[1]);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

// The board is lazy-loaded; the first load is slow under coverage.
async function boardView() {
  render(<App />);
  await screen.findByRole("button", { name: "Ask" }, { timeout: 15_000 });
}

async function askQuestion(question = "Someone cheated me of money in August 2024.") {
  const user = userEvent.setup();
  await boardView();
  const box = screen.getByLabelText("What happened");
  await user.clear(box);
  await user.type(box, question);
  await user.click(screen.getByRole("button", { name: "Ask" }));
  return user;
}

beforeEach(() => {
  vi.stubGlobal("matchMedia", undefined);
  window.history.replaceState(null, "", "/?view=board");
  window.localStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

describe("board view", () => {
  it("opens on real correspondences before any question", async () => {
    serve(answerOf());
    await boardView();
    expect(screen.getByRole("button", { name: /BNS 318\(4\), was IPC 420/ })).toBeTruthy();
    expect(screen.getByText("Ask a question")).toBeTruthy();
  });

  it("shows the answer, the board rows and the cited section's text", async () => {
    serve(answerOf());
    await askQuestion();

    expect(await screen.findByText(/BNS section 318 applies/)).toBeTruthy();
    expect(await screen.findByRole("button", { name: /BNS 318, was IPC 415 and 1 more, Cheating, cited in the answer/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /BNS 316, was IPC 405, Criminal breach of trust, related source/ })).toBeTruthy();
    expect(await screen.findByText(/Whoever, by deceiving any person/)).toBeTruthy();
    expect(screen.getByText("Answered: BNS 318")).toBeTruthy();
  });

  it("opens another section from its row", async () => {
    serve(answerOf());
    const user = await askQuestion();
    await user.click(await screen.findByRole("button", { name: /BNS 316, was IPC 405/ }));
    expect(await screen.findByRole("heading", { name: "BNS 316. Criminal breach of trust." })).toBeTruthy();
  });

  it("asks for the date when the answer needs one", async () => {
    serve(answerOf({ status: "clarify", text: "When did this happen?", act: null, citations: [], sources: [] }));
    await askQuestion("What is the punishment for theft?");
    expect(await screen.findByText("Needs the date of the offence")).toBeTruthy();
    expect(screen.getByText("When did this happen?")).toBeTruthy();
  });

  it("says when a question is outside both codes", async () => {
    serve(answerOf({ status: "declined", text: "This is outside the IPC and the BNS.", act: null, citations: [], sources: [] }));
    await askQuestion("How do I file taxes?");
    expect(await screen.findByText("Outside the IPC and the BNS")).toBeTruthy();
  });

  it("shows the server's reason when a question is refused", async () => {
    serve({ status: 429, body: { error: { message: "Too many requests; please wait a minute." } } });
    await askQuestion();
    expect((await screen.findByRole("alert")).textContent).toContain("Too many requests; please wait a minute.");
  });

  it("takes one vote per answer", async () => {
    const fetchMock = serve(answerOf());
    const user = await askQuestion();
    const vote = await screen.findByRole("group", { name: "Was this useful?" });
    await user.click(within(vote).getByRole("button", { name: "Yes" }));

    expect(await within(vote).findByText("Thanks.")).toBeTruthy();
    expect((within(vote).getByRole("button", { name: "No" }) as HTMLButtonElement).disabled).toBe(true);
    expect(fetchMock.mock.calls.filter(([path]) => path === "/feedback")).toHaveLength(1);
  });

  it("opens an example row's section before any question", async () => {
    serve(answerOf());
    const user = userEvent.setup();
    await boardView();
    await user.click(screen.getByRole("button", { name: /BNS 318\(4\), was IPC 420/ }));
    expect(await screen.findByRole("heading", { name: "BNS 318. Cheating." })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("heading", { name: "BNS 318. Cheating." })).toBeNull();
  });

  it("says when a section cannot be opened", async () => {
    serve(answerOf());
    const user = userEvent.setup();
    await boardView();
    await user.click(screen.getByRole("button", { name: /BNS 103\(1\), was IPC 302/ }));
    expect((await screen.findByRole("alert")).textContent).toContain("No such section");
  });

  it("tells the reader when related sections could not be loaded", async () => {
    serve(answerOf({ sources: ["BNS:318", "BNS:999"] }));
    await askQuestion();
    expect((await screen.findByRole("alert")).textContent).toContain("One related section could not be loaded.");
  });

  it("asks for a question before sending an empty one", async () => {
    const fetchMock = serve(answerOf());
    const user = userEvent.setup();
    await boardView();
    await user.clear(screen.getByLabelText("What happened"));
    await user.click(screen.getByRole("button", { name: "Ask" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Write what happened");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("explains a reply it does not understand", async () => {
    serve({ status: 200, body: { unexpected: true } });
    await askQuestion();
    expect((await screen.findByRole("alert")).textContent).toContain("does not understand");
  });

  it("fills the question from an example", async () => {
    serve(answerOf());
    const user = userEvent.setup();
    await boardView();
    await user.click(screen.getByRole("button", { name: "IPC 302 to BNS" }));
    expect((screen.getByLabelText("What happened") as HTMLTextAreaElement).value).toBe("What is the BNS equivalent of IPC section 302?");
  });

  it("reads the code in force from the date on the clock", async () => {
    serve(answerOf());
    const user = userEvent.setup();
    await boardView();
    await user.type(screen.getByLabelText(/Date of the offence/), "2024-06-30");
    expect(screen.getByText("30 Jun 2024: Indian Penal Code")).toBeTruthy();
  });
});
