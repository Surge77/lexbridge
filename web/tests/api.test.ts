import { afterEach, describe, expect, it, vi } from "vitest";

import { ask, sendFeedback } from "../src/api";
import { answerOf, jsonResponse } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

describe("ask", () => {
  it("posts the question and the offence date", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, answerOf()));
    vi.stubGlobal("fetch", fetchMock);

    await ask("Cheated in August 2024", "2024-08-15");

    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/chat");
    expect(JSON.parse(String(init.body))).toEqual({ question: "Cheated in August 2024", offence_date: "2024-08-15" });
  });

  it("leaves the date out when none is set", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, answerOf()));
    vi.stubGlobal("fetch", fetchMock);

    await ask("Theft", "");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ question: "Theft" });
  });

  it("uses the server's message and wait time when it refuses", async () => {
    const body = { error: { code: "RATE_LIMITED", message: "Too many requests." } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(429, body, { "Retry-After": "12" })));

    await expect(ask("Theft", "")).rejects.toThrow("Too many requests. (try again in 12s)");
  });

  it("explains a reply that is not JSON, such as a proxy error page", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>", { status: 502 })));

    await expect(ask("Theft", "")).rejects.toThrow("The service is unavailable (HTTP 502).");
  });

  it("explains a network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(ask("Theft", "")).rejects.toThrow("Could not reach LexBridge");
  });
});

describe("timeouts", () => {
  it("explains a request that took too long", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("timed out", "TimeoutError")));

    await expect(ask("Theft", "")).rejects.toThrow("took too long");
  });

  it("ignores a Retry-After that is a date rather than seconds", async () => {
    const body = { error: { message: "Busy." } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(503, body, { "Retry-After": "Tue, 21 Oct 2026 10:00:00 GMT" })));

    await expect(ask("Theft", "")).rejects.toThrow(/^Busy\.$/);
  });
});

describe("sendFeedback", () => {
  it("accepts the empty 204 reply", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));

    await expect(sendFeedback("a".repeat(32), true)).resolves.toBeUndefined();
  });
});
