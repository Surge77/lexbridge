import { lazy, Suspense, useEffect, useState } from "react";

import { useLexBridge } from "./use-lexbridge";
import { BoardView } from "./views/board-view";
import { VIEWS, type View } from "./views/view-switch";

// The receipt brings its own fonts and a barcode library; board readers never download them.
const ReceiptView = lazy(() => import("./views/receipt-view").then((m) => ({ default: m.ReceiptView })));

const STORE_KEY = "lexbridge.view";

function initialView(): View {
  const asked = new URLSearchParams(window.location.search).get("view");
  if (VIEWS.includes(asked as View)) return asked as View;
  try {
    const kept = window.localStorage.getItem(STORE_KEY);
    if (VIEWS.includes(kept as View)) return kept as View;
  } catch {
    // Storage can be blocked; the board is the default.
  }
  return "board";
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
    if (next === "board") url.searchParams.delete("view");
    else url.searchParams.set("view", next);
    window.history.replaceState(null, "", url);
  }

  if (view === "board") return <BoardView lb={lb} onView={choose} />;
  return (
    <Suspense fallback={<p className="loading-view">Loading the receipt printer.</p>}>
      <ReceiptView lb={lb} onView={choose} />
    </Suspense>
  );
}
