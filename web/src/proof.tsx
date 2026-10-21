import { SplitFlap } from "./board/split-flap";

// Results of record from the README (92-question stratified evaluation, ADR 0004).
const FIGURES = [
  { value: "0/92", label: "answers naming a section their sources do not support" },
  { value: "100%", label: "right code for questions with a date" },
  { value: "100%", label: "asks for the date when the question has none" },
  { value: "8/8", label: "out-of-scope questions declined" },
] as const;

export function Proof() {
  return (
    <section className="proof" aria-labelledby="proof-title">
      <h2 id="proof-title">How the answers are checked</h2>
      <p>Every section number an answer names must appear in the sources it was given. If one does not, the answer is retried once and the sentence is then cut. The figures come from a fixed set of 92 questions.</p>
      <ul>
        {FIGURES.map((f) => (
          <li key={f.label}>
            <SplitFlap text={f.value} width={4} tone="code" />
            <span className="sr-only">{f.value}</span>
            <span>{f.label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
