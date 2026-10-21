import type { ChatAnswer, MapOut, SectionOut } from "../src/api";

export function sectionOf(id: string, title: string, text = `${id.split(":")[1]}. ${title}. Text of the section.`): SectionOut {
  const [act = "", number = ""] = id.split(":");
  return { id, act, number, title, text, chapter: null };
}

export function mapOf(id: string, replacedBy: string[], replaces: string[]): MapOut {
  return { id, replaced_by: replacedBy, replaces };
}

export function answerOf(overrides: Partial<ChatAnswer> = {}): ChatAnswer {
  return {
    trace_id: "7f3a9c21e04b4d8a9b61c5f2d0e8a734",
    status: "answered",
    text: "Assuming the offence was committed in August 2024, the Bharatiya Nyaya Sanhita (BNS) applies. BNS section 318 applies.",
    act: "BNS",
    citations: ["BNS:318"],
    sources: ["BNS:318", "BNS:316"],
    cached: false,
    ...overrides,
  };
}

export function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
}
