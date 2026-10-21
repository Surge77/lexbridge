import type { CSSProperties, ReactNode } from "react";

import type { BoardRow } from "../board/rows";
import { useVote } from "../notice/use-vote";
import type { State } from "../use-lexbridge";
import { Barcode } from "./barcode";

interface ReceiptProps {
  state: State;
  openId: string | null;
  onOpen: (id: string) => void;
}

const STATUS = { answered: "ANSWERED", clarify: "NEEDS DATE", declined: "NOT COVERED" } as const;
const label = (id: string): string => id.replace(":", " ");

const Kv = ({ k, v }: { k: string; v: ReactNode }) => <p className="kv"><span>{k}</span><span>{v}</span></p>;
const Rule = () => <div className="rule" aria-hidden="true" />;

// Each child is one printed line; the feed animation staggers them by position.
function Paper({ lines, live }: { lines: ReactNode[]; live?: boolean }) {
  return (
    <div className="receipt" aria-live={live ? "polite" : undefined}>
      {lines.map((line, i) => (
        <div className="ln" key={i} style={{ "--i": i } as CSSProperties}>{line}</div>
      ))}
    </div>
  );
}

const HEAD = [<p className="c big">LEXBRIDGE</p>, <p className="c faint">IPC 1860 / BNS 2023</p>, <Rule />];

function ItemLine({ row, openId, onOpen }: { row: BoardRow; openId: string | null; onOpen: (id: string) => void }) {
  return (
    <button type="button" className="item" aria-current={openId === row.id ? "true" : undefined} onClick={() => onOpen(row.id)}>
      <span>{`${row.code} ${row.number}`}</span>
      <span className="item-title">{row.title}</span>
      <span className="faint">{row.other === "NONE LISTED" ? "no counterpart listed" : `was ${row.other}`}</span>
    </button>
  );
}

function AnswerReceipt({ state, openId, onOpen }: { state: Extract<State, { phase: "shown" }> } & Omit<ReceiptProps, "state">) {
  const { answer, rows, missing } = state;
  const [vote, cast] = useVote(answer.trace_id);
  const cited = rows.filter((r) => r.mark === "cited");
  const related = rows.filter((r) => r.mark === "source");
  const [lead] = cited;

  const lines: ReactNode[] = [
    ...HEAD,
    <Kv k="STATUS" v={STATUS[answer.status]} />,
    <Kv k="CODE" v={answer.act ?? "NOT SET"} />,
    <Kv k="BNS FROM" v="01.07.2024" />,
    <Rule />,
  ];
  if (lead) {
    lines.push(<p className="c huge">{`${lead.code} ${lead.number}`}</p>, <p className="c">{lead.title.toUpperCase()}</p>,
      <p className="c faint">{lead.other === "NONE LISTED" ? "no counterpart listed" : `was ${lead.other}`}</p>, <Rule />);
  }
  lines.push(<p className="prose">{answer.text}</p>, <Rule />);
  if (answer.citations.length) {
    lines.push(<p className="section-head">CITED, CHECKED AGAINST THE ACT</p>,
      ...answer.citations.map((id) => {
        const row = cited.find((r) => r.id === id);
        return row ? <ItemLine row={row} openId={openId} onOpen={onOpen} /> : <button type="button" className="item" onClick={() => onOpen(id)}><span>{label(id)}</span></button>;
      }));
  }
  if (related.length) {
    lines.push(<p className="section-head">RELATED, NOT NAMED</p>, ...related.map((row) => <ItemLine row={row} openId={openId} onOpen={onOpen} />));
  }
  if (missing) lines.push(<p className="faint">{`${missing} related section${missing > 1 ? "s" : ""} could not be printed. Ask again in a minute.`}</p>);
  if (answer.cached) lines.push(<p className="faint">Answered before; reprinted from the cache.</p>);
  lines.push(<Rule />);
  if (answer.trace_id) {
    lines.push(<Barcode value={answer.trace_id} />, <p className="c faint trace">{`trace ${answer.trace_id}`}</p>,
      <div className="c vote" role="group" aria-label="Was this useful?">
        <span aria-hidden="true">USEFUL?</span>
        <button type="button" disabled={vote === "sending" || vote === "sent"} onClick={() => cast(true)}>Yes</button>
        <button type="button" disabled={vote === "sending" || vote === "sent"} onClick={() => cast(false)}>No</button>
        <span role="status">{vote === "sent" ? "Thanks." : vote === "failed" ? "The vote did not reach LexBridge. Try again." : ""}</span>
      </div>);
  }
  lines.push(<p className="c faint tear">General information, not legal advice.</p>);
  return <Paper lines={lines} />;
}

export function Receipt({ state, openId, onOpen }: ReceiptProps) {
  if (state.phase === "shown") return <AnswerReceipt key={state.answer.trace_id ?? state.answer.text} state={state} openId={openId} onOpen={onOpen} />;
  if (state.phase === "asking") {
    return <Paper live lines={[...HEAD, <p className="c printing">CHECKING THE SOURCES</p>, <p className="c faint">Every section is checked against the Act before it prints.</p>]} />;
  }
  if (state.phase === "failed") {
    return <Paper lines={[...HEAD, <Kv k="STATUS" v="NOT ANSWERED" />, <Rule />, <p className="prose" role="alert">{state.message}</p>]} />;
  }
  return (
    <Paper lines={[
      ...HEAD,
      <p className="c sample">SAMPLE RECEIPT</p>,
      <Kv k="STATUS" v="ANSWERED" />,
      <Kv k="CODE" v="BNS" />,
      <Rule />,
      <p className="c huge">BNS 318(4)</p>,
      <p className="c">CHEATING, INDUCING DELIVERY</p>,
      <p className="c faint">was IPC 420</p>,
      <Rule />,
      <p className="prose">Your answer prints here: the code that applies on the date of the offence, the sections it cites, and the related sections retrieved with them.</p>,
    ]} />
  );
}
