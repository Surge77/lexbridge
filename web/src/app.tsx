import { useReducer, useRef, useState, type FormEvent } from "react";

import { ApiFailure, ask, lookup, type ChatAnswer, type MapOut, type SectionOut } from "./api";
import { Board, type BoardMessage } from "./board/board";
import { EXAMPLE_ROWS, boardRow, orderSources, type BoardRow } from "./board/rows";
import { SplitFlap } from "./board/split-flap";
import { DateClock } from "./date/date-clock";
import { Notice } from "./notice/notice";
import { SectionSheet } from "./notice/section-sheet";
import { Proof } from "./proof";

type Looked = Record<string, [SectionOut, MapOut]>;

type State =
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

const EXAMPLES = [
  { label: "Cheating, Aug 2024", question: "Someone cheated me of money in August 2024. Which section applies?" },
  { label: "IPC 302 to BNS", question: "What is the BNS equivalent of IPC section 302?" },
  { label: "Theft, no date", question: "What is the punishment for theft?" },
];

// More than this many rows would not fit the board; the notice still lists every citation.
const MAX_LOOKUPS = 5;

function messageFor(state: State): BoardMessage {
  if (state.phase === "idle") return { text: "Ask a question", tone: "plain" };
  if (state.phase === "asking") return { text: "Checking the sources", tone: "plain" };
  if (state.phase === "failed") return { text: "Not answered. See below", tone: "stop" };
  const { answer } = state;
  if (answer.status === "clarify") return { text: "Needs the date of the offence", tone: "wait" };
  if (answer.status === "declined") return { text: "Outside the IPC and the BNS", tone: "stop" };
  const [first] = answer.citations;
  return { text: first ? `Answered: ${first.replace(":", " ")}` : `Answered: ${answer.act ?? ""}`, tone: "go" };
}

const reason = (e: unknown): string => (e instanceof ApiFailure ? e.message : "Something went wrong. Please ask again.");
const has = (looked: Looked, id: string): boolean => Object.hasOwn(looked, id);

export function App() {
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

  const rows = state.phase === "shown" ? state.rows : state.phase === "idle" ? EXAMPLE_ROWS : [];
  const opened = openId ? looked[openId] : undefined;

  return (
    <div className="page">
      <div className="panel">
        <header className="housing">
          <h1>LexBridge</h1>
          <div className="changeover" aria-label="Changeover date: 1 July 2024">
            <span aria-hidden="true">IPC</span>
            <SplitFlap text="01 JUL 2024" width={11} tone="code" />
            <span aria-hidden="true">BNS</span>
          </div>
          <p>Every section number in India's criminal law changed on 1 July 2024. Offences before that day fall under the Indian Penal Code; from that day, the Bharatiya Nyaya Sanhita.</p>
        </header>

        <form className="console" onSubmit={submit} noValidate>
          <div className="question">
            <label htmlFor="question" className="field-label">What happened</label>
            <textarea id="question" rows={2} maxLength={1000} value={question} onChange={(e) => setQuestion(e.target.value)} />
            <div className="examples" aria-label="Example questions">
              {EXAMPLES.map((ex) => (
                <button type="button" key={ex.label} onClick={() => setQuestion(ex.question)}>{ex.label}</button>
              ))}
            </div>
          </div>
          <DateClock value={date} onChange={setDate} />
          <button type="submit" className="ask-key" disabled={state.phase === "asking"}>Ask</button>
        </form>
      </div>

      <Board rows={rows} message={messageFor(state)} busy={state.phase === "asking"} openId={openId} onOpen={open} />

      {state.phase === "failed" && <p className="error" role="alert">{state.message}</p>}
      {state.phase === "shown" && state.missing > 0 && (
        <p className="error" role="alert">{state.missing === 1 ? "One related section could not be loaded." : `${state.missing} related sections could not be loaded.`} The answer below is complete; ask again in a minute to see them on the board.</p>
      )}
      {openError && <p className="error" role="alert">{openError}</p>}

      {(state.phase === "shown" || opened) && (
        <div className="papers">
          {state.phase === "shown" && <Notice key={state.answer.trace_id ?? state.answer.text} answer={state.answer} onOpen={open} />}
          {opened && <SectionSheet section={opened[0]} map={opened[1]} onOpen={open} onClose={() => { wanted.current = null; setOpenId(null); }} />}
        </div>
      )}

      <Proof />

      <footer className="fineprint">General information about the Indian Penal Code and the Bharatiya Nyaya Sanhita, not legal advice. Do not include personal details in questions.</footer>
    </div>
  );
}
