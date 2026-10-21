export type View = "board" | "receipt";

export const VIEWS: View[] = ["board", "receipt"];

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
