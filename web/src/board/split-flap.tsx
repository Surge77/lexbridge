import { useEffect, useRef, useState } from "react";

import { ALPHABET, fit, fitWords, flapPath } from "./flap";

export type FlapTone = "plain" | "code" | "go" | "wait" | "stop" | "dim";

interface SplitFlapProps {
  text: string;
  width: number;
  tone?: FlapTone;
  spinning?: boolean;
  // Shorten at a whole word, for names; codes and numbers are cut exactly.
  words?: boolean;
}

const STEP_MS = 32;
// Scrambling only has to look busy; a slower tick keeps a whole board of strips cheap.
const SPIN_MS = 90;

function prefersStill(): boolean {
  return typeof window.matchMedia !== "function" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function scramble(face: string): string {
  return Array.from(face, (ch, i) => (i % 3 === 0 ? ALPHABET[Math.floor(Math.random() * ALPHABET.length)] ?? ch : ch)).join("");
}

// One timer per strip: each tick turns every unsettled flap one character forward, so only
// the cells whose value changed move. A full turn of the drum is about 1.4 s; most changes
// settle well before that. While `spinning`, the strip scrambles: the board's loading state.
export function SplitFlap({ text, width, tone = "plain", spinning = false, words = false }: SplitFlapProps) {
  const target = words ? fitWords(text, width) : fit(text, width);
  const [still] = useState(prefersStill);
  const face = useRef(still ? target : " ".repeat(width));
  const [shown, setShown] = useState(face.current);

  useEffect(() => {
    if (still) {
      face.current = target;
      setShown(target);
      return undefined;
    }
    face.current = fit(face.current, width);
    let queues: string[][] | null = null;
    const timer = window.setInterval(() => {
      let next: string;
      if (spinning) {
        next = scramble(face.current);
      } else {
        queues ??= Array.from(target, (ch, i) => flapPath(face.current[i] ?? " ", ch));
        const pending = queues;
        next = Array.from(face.current, (ch, i) => pending[i]?.shift() ?? ch).join("");
        if (pending.every((q) => q.length === 0)) window.clearInterval(timer);
      }
      face.current = next;
      setShown(next);
    }, spinning ? SPIN_MS : STEP_MS);
    return () => window.clearInterval(timer);
  }, [target, width, spinning, still]);

  return (
    <span className={`flaps tone-${tone}`} aria-hidden="true">
      {Array.from(shown, (ch, i) => (
        <span className="flap" key={i}>{ch}</span>
      ))}
    </span>
  );
}
