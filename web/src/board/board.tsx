import type { BoardRow } from "./rows";
import { SplitFlap, type FlapTone } from "./split-flap";

export interface BoardMessage {
  text: string;
  tone: FlapTone;
}

interface BoardProps {
  rows: BoardRow[];
  message: BoardMessage;
  busy: boolean;
  openId: string | null;
  onOpen: (id: string) => void;
}

const ROWS = 5;
// A real board shortens long names at its width; the full title is in each row's label.
const TITLE_WIDTH = 20;
const MARK_TEXT = { cited: "CITED", source: "RELATED", example: "" } as const;
const MARK_TONE = { cited: "go", source: "dim", example: "dim" } as const;
const EMPTY_WIDTHS = [3, 6, 11, TITLE_WIDTH, 7];

function spoken(row: BoardRow): string {
  const more = /^(.*) \+(\d+)$/.exec(row.other);
  const was = row.other === "NONE LISTED" ? "no listed counterpart" : more ? `was ${more[1]} and ${more[2]} more` : `was ${row.other}`;
  const mark = row.mark === "cited" ? ", cited in the answer" : row.mark === "source" ? ", related source" : "";
  return `${row.code} ${row.number}, ${was}, ${row.title}${mark}`;
}

// Rows are buttons: every line on the board opens that section's text. The flaps are
// decoration for sighted readers; each row carries its own plain-text name.
export function Board({ rows, message, busy, openId, onOpen }: BoardProps) {
  const slots = Array.from({ length: ROWS }, (_, i) => rows[i]);
  return (
    <section className="board" aria-label="Sections for this answer">
      <div className="board-head" aria-hidden="true">
        <span>Code</span><span>Section</span><span>Previously / now</span><span>Offence</span><span>Status</span>
      </div>
      <ol className="board-rows" aria-busy={busy}>
        {slots.map((row, i) =>
          row ? (
            <li key={i}>
              <button type="button" className={`board-row is-${row.mark}`} aria-current={openId === row.id ? "true" : undefined}
                aria-label={spoken(row)} onClick={() => onOpen(row.id)}>
                <SplitFlap text={row.code} width={3} tone="code" spinning={busy} />
                <SplitFlap text={row.number} width={6} spinning={busy} />
                <SplitFlap text={row.other} width={11} tone="dim" spinning={busy} />
                <SplitFlap text={row.title} width={TITLE_WIDTH} words spinning={busy} />
                <SplitFlap text={MARK_TEXT[row.mark]} width={7} tone={MARK_TONE[row.mark]} spinning={busy} />
              </button>
            </li>
          ) : (
            <li key={i} className="board-row is-empty" aria-hidden="true">
              {EMPTY_WIDTHS.map((w, k) => <SplitFlap key={k} text="" width={w} spinning={busy} />)}
            </li>
          ),
        )}
      </ol>
      <div className="board-message">
        <SplitFlap text={message.text} width={34} tone={message.tone} spinning={busy} />
        <p className="sr-only" aria-live="polite">{busy ? "Checking the sources." : message.text}</p>
      </div>
      <p className="board-legend">Cited: named in the answer and checked against the Act. Related: retrieved with it, not named. Select a row to read the section.</p>
    </section>
  );
}
