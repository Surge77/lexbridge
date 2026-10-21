import "@fontsource/sometype-mono/latin-400.css";
import "@fontsource/sometype-mono/latin-700.css";
import "@fontsource/rethink-sans/latin-400.css";
import "@fontsource/rethink-sans/latin-600.css";
import "@fontsource/rethink-sans/latin-800.css";
import "../styles/receipt.css";

import { codeFor, spokenDate } from "../date/clock";
import { SectionSheet } from "../notice/section-sheet";
import { Receipt } from "../receipt/receipt";
import { EXAMPLES, type LexBridge } from "../use-lexbridge";
import { ViewSwitch, type View } from "./view-switch";

interface ReceiptViewProps {
  lb: LexBridge;
  onView: (view: View) => void;
}

const CODE_NAME = { IPC: "the Indian Penal Code", BNS: "the Bharatiya Nyaya Sanhita" } as const;

// A court help-desk kiosk: type on the screen, and the answer feeds out of the printer slot
// as a thermal receipt. An opened section prints as a second slip stapled beneath it.
export function ReceiptView({ lb, onView }: ReceiptViewProps) {
  const { state, question, setQuestion, date, setDate, submit, open, close, openId, opened, openError } = lb;
  const code = codeFor(date);

  return (
    <div className="kiosk-page">
      <div className="stage">
        <section className="kiosk">
          <div className="kiosk-inner">
            <div className="kiosk-bar">
              <h1>LexBridge</h1>
              <ViewSwitch view="receipt" onView={onView} />
            </div>
            <form className="screen" onSubmit={submit} noValidate>
              <h2>Which section applies to what happened?</h2>
              <p>The law changed on 1 July 2024. LexBridge works out which code applies from the date, and every section on your receipt is checked against the Act.</p>
              <div>
                <label htmlFor="question">What happened</label>
                <textarea id="question" rows={3} maxLength={1000} value={question} onChange={(e) => setQuestion(e.target.value)} />
              </div>
              <div className="screen-row">
                <div>
                  <label htmlFor="offence-date">Date of the offence, if you know it</label>
                  <input id="offence-date" type="date" min="1860-01-01" value={date} onChange={(e) => setDate(e.target.value)} />
                  <p className="screen-hint" aria-live="polite">{code ? `${spokenDate(date)}: ${CODE_NAME[code]} applies.` : "No date set. The date in your question is used."}</p>
                </div>
                <button className="print" type="submit" disabled={state.phase === "asking"}>Print answer</button>
              </div>
              <div className="screen-examples" aria-label="Example questions">
                {EXAMPLES.map((ex) => (
                  <button type="button" key={ex.label} onClick={() => setQuestion(ex.question)}>{ex.label}</button>
                ))}
              </div>
            </form>
            <div className="kiosk-facts">
              <div><b>0/92</b><span>answers naming a section their sources do not support</span></div>
              <div><b>100%</b><span>right code for questions with a date</span></div>
              <div><b>8/8</b><span>out-of-scope questions declined</span></div>
            </div>
          </div>
        </section>

        <section className="printer" aria-label="Your answer">
          <div className="slot" aria-hidden="true" />
          <Receipt state={state} openId={openId} onOpen={open} />
          {openError && <p className="slip-error" role="alert">{openError}</p>}
          {opened && <SectionSheet variant="slip" section={opened[0]} map={opened[1]} onOpen={open} onClose={close} />}
        </section>
      </div>
      <footer className="kiosk-foot">General information about the Indian Penal Code and the Bharatiya Nyaya Sanhita, not legal advice. Do not include personal details in questions.</footer>
    </div>
  );
}
