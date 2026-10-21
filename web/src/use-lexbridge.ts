import { useReducer, useRef, useState, type FormEvent } from "react";

import { ApiFailure, ask, lookup, type ChatAnswer, type MapOut, type SectionOut } from "./api";
import { boardRow, orderSources, type BoardRow } from "./board/rows";

export type Looked = Record<string, [SectionOut, MapOut]>;

export type State =
  | { phase: "idle" }
  | { phase: "asking" }
  | { phase: "shown"; answer: ChatAnswer; rows: BoardRow[]; missing: number }
  | { phase: "failed"; message: string };

type Action =
  | { type: "ask" }
  | { type: "answer"; answer: ChatAnswer; rows: BoardRow[]; missing: number }
  | { type: "fail"; message: string };

function reduce(_state: State, action: Action): State {
  switch (action.type) {
    case "ask": return { phase: "asking" };
    case "answer": return { phase: "shown", answer: action.answer, rows: action.rows, missing: action.missing };
    case "fail": return { phase: "failed", message: action.message };
  }
}

export const EXAMPLES = [
  { label: "Cheating, Aug 2024", question: "Someone cheated me of money in August 2024. Which section applies?" },
  { label: "IPC 302 to BNS", question: "What is the BNS equivalent of IPC section 302?" },
  { label: "Theft, no date", question: "What is the punishment for theft?" },
];

// More than this many rows would not fit the board; the notice still lists every citation.
const MAX_LOOKUPS = 5;

const reason = (e: unknown): string => (e instanceof ApiFailure ? e.message : "Something went wrong. Please ask again.");
const has = (looked: Looked, id: string): boolean => Object.hasOwn(looked, id);

export interface LexBridge {
  state: State;
  question: string;
  setQuestion: (q: string) => void;
  date: string;
  setDate: (iso: string) => void;
  submit: (event: FormEvent) => Promise<void>;
  open: (id: string) => Promise<void>;
  close: () => void;
  openId: string | null;
  opened: [SectionOut, MapOut] | undefined;
  openError: string | null;
}

// Everything a view needs: asking, the sections fetched for an answer, and the one section
// open for reading. Views only decide how it looks.
export function useLexBridge(): LexBridge {
  const [state, dispatch] = useReducer(reduce, { phase: "idle" });
  const [question, setQuestion] = useState(EXAMPLES[0]?.question ?? "");
  const [date, setDate] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [openError, setOpenError] = useState<string | null>(null);
  // Sections already fetched, kept across answers: opening a row never asks twice.
  const [looked, setLooked] = useState<Looked>({});
  // The section the reader asked for last; a slower, older request must not overwrite it.
  const wanted = useRef<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (state.phase === "asking") return;
    if (!text) {
      dispatch({ type: "fail", message: "Write what happened before asking." });
      return;
    }
    dispatch({ type: "ask" });
    wanted.current = null;
    setOpenId(null);
    setOpenError(null);
    try {
      const answer = await ask(text, date);
      const cited = new Set(answer.citations);
      const ids = orderSources(answer.sources, answer.citations).slice(0, MAX_LOOKUPS);
      // A section that fails to load drops off the board; the answer itself still stands.
      const settled = await Promise.allSettled(ids.map(lookup));
      const found: Looked = {};
      const rows: BoardRow[] = [];
      settled.forEach((result, i) => {
        const id = ids[i];
        if (result.status !== "fulfilled" || id === undefined) return;
        found[id] = result.value;
        rows.push(boardRow(result.value[0], result.value[1], cited.has(id)));
      });
      setLooked((prev) => ({ ...prev, ...found }));
      dispatch({ type: "answer", answer, rows, missing: ids.length - rows.length });
      const first = answer.citations.find((id) => has(found, id)) ?? null;
      wanted.current = first;
      setOpenId(first);
    } catch (e) {
      dispatch({ type: "fail", message: reason(e) });
    }
  }

  async function open(id: string) {
    wanted.current = id;
    setOpenError(null);
    setOpenId(id);
    if (has(looked, id)) return;
    try {
      const found = await lookup(id);
      setLooked((prev) => ({ ...prev, [id]: found }));
    } catch (e) {
      if (wanted.current !== id) return;
      setOpenError(reason(e));
      setOpenId(null);
    }
  }

  function close() {
    wanted.current = null;
    setOpenId(null);
  }

  const opened = openId ? looked[openId] : undefined;
  return { state, question, setQuestion, date, setDate, submit, open, close, openId, opened, openError };
}
