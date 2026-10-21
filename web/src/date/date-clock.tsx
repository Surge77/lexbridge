import { SplitFlap } from "../board/split-flap";
import { clockFace, codeFor, spokenDate } from "./clock";

interface DateClockProps {
  value: string;
  onChange: (iso: string) => void;
}

const CODE_NAME = { IPC: "Indian Penal Code", BNS: "Bharatiya Nyaya Sanhita" } as const;

// The reader's own calendar day, not UTC: in India the UTC date lags until 05:30.
function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// The native date input is the real control: it sits transparent over the flaps, so typing,
// the browser's picker and screen readers all work, while the flaps show the value.
export function DateClock({ value, onChange }: DateClockProps) {
  const code = codeFor(value);
  const reading = code ? `${spokenDate(value)}: ${CODE_NAME[code]}` : "No date set. The date in your question is used.";
  return (
    <div className="clock">
      <label htmlFor="offence-date" className="field-label">Date of the offence <span>optional</span></label>
      <div className="clock-face">
        <SplitFlap text={clockFace(value)} width={11} />
        <SplitFlap text={code ?? "---"} width={3} tone={code ? "code" : "dim"} />
        <input
          id="offence-date"
          type="date"
          value={value}
          min="1860-01-01"
          max={localToday()}
          onChange={(e) => onChange(e.target.value)}
          onClick={(e) => {
            try { e.currentTarget.showPicker(); } catch { /* the field still takes typed dates */ }
          }}
        />
      </div>
      <p className="clock-reading" aria-live="polite">{reading}</p>
      {value && <button type="button" className="text-button" onClick={() => onChange("")}>Clear date</button>}
    </div>
  );
}
