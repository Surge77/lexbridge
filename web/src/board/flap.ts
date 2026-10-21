// The characters printed on a flap drum, in the order the drum turns.
export const ALPHABET = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789()+-./:";

export function fit(text: string, width: number): string {
  return text.toUpperCase().slice(0, width).padEnd(width, " ");
}

const DANGLING = new Set(["a", "an", "and", "by", "for", "in", "of", "on", "or", "the", "to", "with"]);

// Boards shorten names at a word, not inside one, and never leave "OF" or "BY" hanging.
export function fitWords(text: string, width: number): string {
  if (text.length <= width) return fit(text, width);
  const words = text.slice(0, width + 1).split(" ").slice(0, -1);
  while (words.length > 1 && DANGLING.has((words.at(-1) ?? "").toLowerCase())) words.pop();
  return fit(words.length ? words.join(" ") : text, width);
}

// A real flap can only turn forward, so reaching a letter "behind" the current one wraps
// round the drum. Characters the drum does not carry are shown at once.
export function flapPath(from: string, to: string): string[] {
  if (from === to) return [];
  const start = ALPHABET.indexOf(from);
  const end = ALPHABET.indexOf(to);
  if (start < 0 || end < 0) return [to];
  const path: string[] = [];
  for (let i = start; i !== end; ) {
    i = (i + 1) % ALPHABET.length;
    path.push(ALPHABET[i] ?? to);
  }
  return path;
}
