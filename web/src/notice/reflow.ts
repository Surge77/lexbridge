// Section text comes from the gazette PDFs with the printed line breaks still in it. A break
// is kept only where the statute starts a new unit: a sub-section or clause like "(2)" or
// "(a)", an Explanation, an Exception or the Illustrations.
const NEW_UNIT = /^(\([0-9a-z]+\)|Explanation|Exception|Illustrations?\b)/;

export function reflow(text: string): string {
  return text
    .split("\n")
    .reduce<string[]>((paragraphs, line) => {
      const last = paragraphs.length - 1;
      if (last < 0 || NEW_UNIT.test(line.trim())) return [...paragraphs, line.trim()];
      return [...paragraphs.slice(0, last), `${paragraphs[last]} ${line.trim()}`.trim()];
    }, [])
    .join("\n");
}
