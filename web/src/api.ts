export type AnswerStatus = "answered" | "clarify" | "declined";

export interface ChatAnswer {
  trace_id: string | null;
  status: AnswerStatus;
  text: string;
  act: string | null;
  citations: string[];
  sources: string[];
  cached: boolean;
}

export interface SectionOut {
  id: string;
  act: string;
  number: string;
  title: string;
  text: string;
  chapter: string | null;
}

export interface MapOut {
  id: string;
  replaced_by: string[];
  replaces: string[];
}

// Errors this module writes for people to read; anything else is shown generically.
export class ApiFailure extends Error {}

// A model answer usually takes about a second, but the chain may fall back to a second
// model; lookups are bundle reads.
const ASK_TIMEOUT_MS = 60_000;
const LOOKUP_TIMEOUT_MS = 15_000;

const isStrings = (v: unknown): v is string[] => Array.isArray(v) && v.every((s) => typeof s === "string");

function isChatAnswer(v: unknown): v is ChatAnswer {
  const a = v as Partial<ChatAnswer> | null;
  return !!a && typeof a.text === "string" && ["answered", "clarify", "declined"].includes(String(a.status))
    && isStrings(a.citations) && isStrings(a.sources);
}

function isSection(v: unknown): v is SectionOut {
  const s = v as Partial<SectionOut> | null;
  return !!s && typeof s.id === "string" && typeof s.title === "string" && typeof s.text === "string";
}

function isMap(v: unknown): v is MapOut {
  const m = v as Partial<MapOut> | null;
  return !!m && isStrings(m.replaced_by) && isStrings(m.replaces);
}

function refusal(response: Response, body: unknown): ApiFailure {
  const message = (body as { error?: { message?: unknown } } | null)?.error?.message;
  const text = typeof message === "string" ? message : `The service is unavailable (HTTP ${response.status}).`;
  const wait = response.headers.get("Retry-After");
  return new ApiFailure(wait && /^\d+$/.test(wait) ? `${text} (try again in ${wait}s)` : text);
}

async function call(path: string, timeoutMs: number, init?: RequestInit): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(path, { ...init, signal: AbortSignal.timeout(timeoutMs) });
  } catch (e) {
    if (e instanceof DOMException && e.name === "TimeoutError") throw new ApiFailure("LexBridge took too long to reply. Please ask again.");
    throw new ApiFailure("Could not reach LexBridge. Check your connection and try again.");
  }
  if (response.status === 204) return undefined;
  // A proxy in front of the app can answer with an HTML error page, not our JSON.
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok || body === null) throw refusal(response, body);
  return body;
}

const JSON_HEADERS = { "Content-Type": "application/json" };
const UNEXPECTED = "LexBridge sent a reply this page does not understand. Please reload and ask again.";

export async function ask(question: string, offenceDate: string): Promise<ChatAnswer> {
  const body: { question: string; offence_date?: string } = { question };
  if (offenceDate) body.offence_date = offenceDate;
  const answer = await call("/chat", ASK_TIMEOUT_MS, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body) });
  if (!isChatAnswer(answer)) throw new ApiFailure(UNEXPECTED);
  return answer;
}

export async function lookup(id: string): Promise<[SectionOut, MapOut]> {
  const key = encodeURIComponent(id);
  const [section, map] = await Promise.all([call(`/section/${key}`, LOOKUP_TIMEOUT_MS), call(`/map/${key}`, LOOKUP_TIMEOUT_MS)]);
  if (!isSection(section) || !isMap(map)) throw new ApiFailure(UNEXPECTED);
  return [section, map];
}

export async function sendFeedback(traceId: string, helpful: boolean): Promise<void> {
  await call("/feedback", LOOKUP_TIMEOUT_MS, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ trace_id: traceId, helpful }) });
}
