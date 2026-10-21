import { useEffect, useRef } from "react";

import type { MapOut, SectionOut } from "../api";
import { reflow } from "./reflow";

interface SectionSheetProps {
  section: SectionOut;
  map: MapOut;
  onOpen: (id: string) => void;
  onClose: () => void;
}

export function SectionSheet({ section, map, onOpen, onClose }: SectionSheetProps) {
  const heading = useRef<HTMLHeadingElement>(null);
  // The sheet opens below the board, out of the reader's focus; take them to it.
  useEffect(() => heading.current?.focus(), [section.id]);

  const others = section.act === "BNS" ? map.replaces : map.replaced_by;
  const relation = section.act === "BNS" ? "Takes over" : "Replaced by";
  return (
    <article className="sheet" aria-labelledby="sheet-title">
      <div className="sheet-head">
        <h2 id="sheet-title" tabIndex={-1} ref={heading}>{`${section.act} ${section.number}. ${section.title}.`}</h2>
        <button type="button" className="text-button" onClick={onClose}>Close</button>
      </div>
      {section.chapter && <p className="fineprint">Chapter {section.chapter}</p>}
      <p className="sheet-map">
        {others.length === 0 ? "No counterpart listed in the correspondence table. That does not mean it was abolished." : `${relation} `}
        {others.map((id, i) => (
          <span key={id}>
            {i > 0 && ", "}
            <button type="button" className="link-button" onClick={() => onOpen(id)}>{id.replace(":", " ")}</button>
          </span>
        ))}
      </p>
      <pre className="sheet-text">{reflow(section.text)}</pre>
    </article>
  );
}
