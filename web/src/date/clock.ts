export const CHANGEOVER = "2024-07-01";

const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
const BLANK = "-- --- ----";
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function clockFace(iso: string): string {
  const match = ISO_DATE.exec(iso);
  if (!match) return BLANK;
  const [, year = "", month = "", day = ""] = match;
  const name = MONTHS[Number(month) - 1];
  if (!name || Number(day) < 1 || Number(day) > 31) return BLANK;
  return `${day} ${name} ${year}`;
}

export function spokenDate(iso: string): string {
  const face = clockFace(iso);
  if (face === BLANK) return "";
  const [day, month = "", year] = face.split(" ");
  return `${Number(day)} ${month.charAt(0)}${month.slice(1).toLowerCase()} ${year}`;
}

// ISO dates compare correctly as strings.
export function codeFor(iso: string): "IPC" | "BNS" | null {
  if (!ISO_DATE.test(iso)) return null;
  return iso < CHANGEOVER ? "IPC" : "BNS";
}
