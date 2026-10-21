import { useState } from "react";

import { sendFeedback } from "../api";

export type Vote = "open" | "sending" | "sent" | "failed";

// One vote per answer; a vote that fails to arrive can be cast again.
export function useVote(traceId: string | null): [Vote, (helpful: boolean) => Promise<void>] {
  const [vote, setVote] = useState<Vote>("open");

  async function cast(helpful: boolean) {
    if (!traceId) return;
    setVote("sending");
    try {
      await sendFeedback(traceId, helpful);
      setVote("sent");
    } catch {
      setVote("failed");
    }
  }

  return [vote, cast];
}
