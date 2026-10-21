import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SplitFlap } from "../../src/board/split-flap";

const face = (container: HTMLElement): string =>
  Array.from(container.querySelectorAll(".flap"), (cell) => cell.textContent ?? "").join("");

function motion(reduce: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: reduce && query.includes("reduce"), media: query }));
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("SplitFlap", () => {
  it("turns from blank to the text and then stops", () => {
    motion(false);
    const { container } = render(<SplitFlap text="BNS" width={3} />);
    expect(face(container)).toBe("   ");

    act(() => vi.advanceTimersByTime(5_000));
    expect(face(container)).toBe("BNS");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("moves only the cells whose value changed", () => {
    motion(false);
    const { container, rerender } = render(<SplitFlap text="318" width={3} />);
    act(() => vi.advanceTimersByTime(5_000));

    rerender(<SplitFlap text="319" width={3} />);
    act(() => vi.advanceTimersByTime(32));
    expect(face(container).slice(0, 2)).toBe("31");
    act(() => vi.advanceTimersByTime(5_000));
    expect(face(container)).toBe("319");
  });

  it("keeps scrambling while spinning", () => {
    motion(false);
    render(<SplitFlap text="CHECKING" width={8} spinning />);
    act(() => vi.advanceTimersByTime(5_000));
    expect(vi.getTimerCount()).toBe(1);
  });

  it("shows the text at once when motion is reduced", () => {
    motion(true);
    const { container } = render(<SplitFlap text="IPC" width={3} spinning />);
    expect(face(container)).toBe("IPC");
    expect(vi.getTimerCount()).toBe(0);
  });
});
