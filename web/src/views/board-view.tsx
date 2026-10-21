import "@fontsource/barlow-condensed/latin-600.css";
import "@fontsource/barlow-condensed/latin-700.css";
import "@fontsource/barlow/latin-400.css";
import "@fontsource/barlow/latin-500.css";
import "@fontsource/barlow/latin-600.css";
import "../styles/board.css";

import { Board, type BoardMessage } from "../board/board";
import { EXAMPLE_ROWS } from "../board/rows";
import { SplitFlap } from "../board/split-flap";
import { DateClock } from "../date/date-clock";
import { Notice } from "../notice/notice";
import { SectionSheet } from "../notice/section-sheet";
import { Proof } from "../proof";
import { EXAMPLES, type LexBridge, type State } from "../use-lexbridge";
import { ViewSwitch, type View } from "./view-switch";

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

interface BoardViewProps {
  lb: LexBridge;
  onView: (view: View) => void;
}

export function BoardView({ lb, onView }: BoardViewProps) {
  const { state, question, setQuestion, date, setDate, submit, open, close, openId, opened, openError } = lb;
  const rows = state.phase === "shown" ? state.rows : state.phase === "idle" ? EXAMPLE_ROWS : [];

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
          <ViewSwitch view="board" onView={onView} />
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
          {opened && <SectionSheet section={opened[0]} map={opened[1]} onOpen={open} onClose={close} />}
        </div>
      )}

      <Proof />

      <footer className="fineprint">General information about the Indian Penal Code and the Bharatiya Nyaya Sanhita, not legal advice. Do not include personal details in questions.</footer>
    </div>
  );
}
