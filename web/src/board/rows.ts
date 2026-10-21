import type { MapOut, SectionOut } from "../api";

export type RowMark = "cited" | "source" | "example";

export interface BoardRow {
  id: string;
  code: string;
  number: string;
  other: string;
  title: string;
  mark: RowMark;
}

// Before any question the board shows real correspondences, with the sub-section the
// official table names (the /map endpoint reports whole sections only).
export const EXAMPLE_ROWS: BoardRow[] = [
  { id: "BNS:318", code: "BNS", number: "318(4)", other: "IPC 420", title: "Cheating, inducing delivery", mark: "example" },
  { id: "BNS:103", code: "BNS", number: "103(1)", other: "IPC 302", title: "Murder", mark: "example" },
  { id: "BNS:303", code: "BNS", number: "303(2)", other: "IPC 379", title: "Theft", mark: "example" },
  { id: "BNS:318", code: "BNS", number: "318(1)", other: "IPC 415", title: "Cheating", mark: "example" },
];

export function orderSources(sources: string[], citations: string[]): string[] {
  return [...citations, ...sources.filter((id) => !citations.includes(id))];
}

const label = (id: string): string => id.replace(":", " ");

// The board's column is "Offence"; "Punishment for murder" is the murder row.
function offence(title: string): string {
  const rest = /^punishment for (.+)$/i.exec(title)?.[1];
  return rest ? rest.charAt(0).toUpperCase() + rest.slice(1) : title;
}

export function boardRow(section: SectionOut, map: MapOut, cited: boolean): BoardRow {
  const others = section.act === "BNS" ? map.replaces : map.replaced_by;
  const [first] = others;
  const other = first === undefined ? "NONE LISTED" : others.length > 1 ? `${label(first)} +${others.length - 1}` : label(first);
  return { id: section.id, code: section.act, number: section.number, other, title: offence(section.title), mark: cited ? "cited" : "source" };
}
