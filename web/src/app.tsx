import { lazy, Suspense, useEffect, useState } from "react";

import { useLexBridge } from "./use-lexbridge";
import { ReceiptView } from "./views/receipt-view";
import { VIEWS, type View } from "./views/view-switch";

// The board brings its own fonts and flap machinery; receipt readers never download them.
const BoardView = lazy(() => import("./views/board-view").then((m) => ({ default: m.BoardView })));

const STORE_KEY = "lexbridge.view";
const MAIN_VIEW: View = "receipt";

function initialView(): View {
  const asked = new URLSearchParams(window.location.search).get("view");
  if (VIEWS.includes(asked as View)) return asked as View;
  try {
    const kept = window.localStorage.getItem(STORE_KEY);
    if (VIEWS.includes(kept as View)) return kept as View;
  } catch {
    // Storage can be blocked; the main view is the default.
  }
  return MAIN_VIEW;
}

export function App() {
  const lb = useLexBridge();
  const [view, setView] = useState<View>(initialView);

  useEffect(() => {
    document.documentElement.dataset.view = view;
  }, [view]);

  function choose(next: View) {
    setView(next);
    try {
      window.localStorage.setItem(STORE_KEY, next);
    } catch {
      // Not remembered; the choice still applies now.
    }
    const url = new URL(window.location.href);
    if (next === MAIN_VIEW) url.searchParams.delete("view");
    else url.searchParams.set("view", next);
    window.history.replaceState(null, "", url);
  }

  if (view === "receipt") return <ReceiptView lb={lb} onView={choose} />;
  return (
    <Suspense fallback={<p className="loading-view">Loading the departures board.</p>}>
      <BoardView lb={lb} onView={choose} />
    </Suspense>
  );
}
