export type View = "receipt" | "board";

// The first view is the main one: what / shows with no choice made.
export const VIEWS: View[] = ["receipt", "board"];

interface ViewSwitchProps {
  view: View;
  onView: (view: View) => void;
}

const LABEL: Record<View, string> = { board: "Board", receipt: "Receipt" };

export function ViewSwitch({ view, onView }: ViewSwitchProps) {
  return (
    <div className="view-switch" role="group" aria-label="Page style">
      {VIEWS.map((v) => (
        <button type="button" key={v} aria-pressed={v === view} onClick={() => onView(v)}>{LABEL[v]}</button>
      ))}
    </div>
  );
}
