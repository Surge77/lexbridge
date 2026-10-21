import type { ChatAnswer } from "../api";
import { useVote } from "./use-vote";

interface NoticeProps {
  answer: ChatAnswer;
  onOpen: (id: string) => void;
}

const HEADING = { answered: "Answer", clarify: "One more detail", declined: "Not covered" } as const;

// The printed sheet pinned under the board: the answer in full, its citations, one vote.
// Model output is rendered as text, never as markup.
export function Notice({ answer, onOpen }: NoticeProps) {
  const [vote, cast] = useVote(answer.trace_id);

  return (
    <article className="notice">
      <h2>{HEADING[answer.status]}</h2>
      <p className="notice-text">{answer.text}</p>
      {answer.citations.length > 0 && (
        <div className="cites">
          <span>Cited</span>
          {answer.citations.map((id) => (
            <button type="button" key={id} className="cite" onClick={() => onOpen(id)}>{id.replace(":", " ")}</button>
          ))}
          <span className="checked">Checked against the Act's text before it was shown.</span>
        </div>
      )}
      {answer.trace_id && (
        <div className="vote" role="group" aria-label="Was this useful?">
          <span aria-hidden="true">Was this useful?</span>
          <button type="button" disabled={vote === "sending" || vote === "sent"} onClick={() => cast(true)}>Yes</button>
          <button type="button" disabled={vote === "sending" || vote === "sent"} onClick={() => cast(false)}>No</button>
          <span role="status">
            {vote === "sent" && "Thanks."}
            {vote === "failed" && "The vote did not reach LexBridge. Try again."}
          </span>
        </div>
      )}
      {answer.cached && <p className="fineprint">Answered before; served from the cache.</p>}
    </article>
  );
}
