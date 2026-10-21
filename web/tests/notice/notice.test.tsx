import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Notice } from "../../src/notice/notice";
import { answerOf } from "../fixtures";

afterEach(() => vi.unstubAllGlobals());

describe("Notice", () => {
  it("lets the reader vote again when the vote does not arrive", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    const user = userEvent.setup();
    render(<Notice answer={answerOf()} onOpen={() => undefined} />);

    await user.click(screen.getByRole("button", { name: "No" }));

    expect(await screen.findByText("The vote did not reach LexBridge. Try again.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "No" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("offers no vote when the answer has no trace", () => {
    render(<Notice answer={answerOf({ trace_id: null })} onOpen={() => undefined} />);
    expect(screen.queryByRole("group", { name: "Was this useful?" })).toBeNull();
  });

  it("says when an answer came from the cache", () => {
    render(<Notice answer={answerOf({ cached: true })} onOpen={() => undefined} />);
    expect(screen.getByText("Answered before; served from the cache.")).toBeTruthy();
  });

  it("opens a cited section", async () => {
    const onOpen = vi.fn();
    const user = userEvent.setup();
    render(<Notice answer={answerOf()} onOpen={onOpen} />);
    await user.click(screen.getByRole("button", { name: "BNS 318" }));
    expect(onOpen).toHaveBeenCalledWith("BNS:318");
  });
});
