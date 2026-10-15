import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useResourcePolling } from "@/lib/hooks/useResourcePolling";

const message = () => "Service unavailable";
function pending<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
async function flush() { await act(async () => {}); }
async function advance(ms: number) { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); }
function visibility(hidden: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, value: hidden });
  act(() => document.dispatchEvent(new Event("visibilitychange")));
}

describe("scoped resource polling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); });

  it("loads immediately, polls healthy resources at 20s, and retains stale success on failure", async () => {
    const loader = vi.fn().mockResolvedValueOnce(12).mockRejectedValueOnce({ status: 503 }).mockResolvedValue(14);
    const { result } = renderHook(() => useResourcePolling(loader, "a", message));
    expect(result.current.loading).toBe(true);
    await flush();
    const timestamp = result.current.lastSuccess;
    expect(result.current.data).toBe(12);
    await advance(19_999);
    expect(loader).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(result.current).toMatchObject({ data: 12, lastSuccess: timestamp, retrying: true, error: "Service unavailable" });
    await advance(2_000);
    expect(result.current).toMatchObject({ data: 14, retrying: false, error: "" });
    expect(result.current.lastSuccess).toBeGreaterThan(timestamp!);
  });

  it("backs off 2,4,8,16,30,30s and resets after success", async () => {
    const loader = vi.fn().mockRejectedValue({ status: 502 });
    const { result } = renderHook(() => useResourcePolling(loader, "a", message));
    await flush();
    for (const [index, delay] of [2_000, 4_000, 8_000, 16_000, 30_000, 30_000].entries()) {
      await advance(delay - 1);
      expect(loader).toHaveBeenCalledTimes(index + 1);
      await advance(1);
      expect(loader).toHaveBeenCalledTimes(index + 2);
    }
    loader.mockResolvedValueOnce(0).mockRejectedValue({ status: 504 });
    await advance(30_000);
    expect(result.current.data).toBe(0);
    await advance(20_000);
    const calls = loader.mock.calls.length;
    await advance(2_000);
    expect(loader).toHaveBeenCalledTimes(calls + 1);
  });

  it.each([0, 1])("jitters retry delays within ±20%% (random=%s)", async (random) => {
    vi.mocked(Math.random).mockReturnValue(random);
    const loader = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    renderHook(() => useResourcePolling(loader, "a", message));
    await flush();
    const delay = 2_000 * (0.8 + random * 0.4);
    await advance(delay - 1);
    expect(loader).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(loader).toHaveBeenCalledTimes(2);
  });

  it.each([400, 401, 403, 404, 422, 429, 500])("does not retry HTTP %s", async (status) => {
    const loader = vi.fn().mockRejectedValue({ status });
    const { result } = renderHook(() => useResourcePolling(loader, "a", message));
    await flush();
    expect(result.current.retrying).toBe(false);
    await advance(120_000);
    expect(loader).toHaveBeenCalledTimes(1);
  });

  it("allows one in-flight request and bounds a stalled read before retrying", async () => {
    const loader = vi.fn((signal: AbortSignal) => new Promise<number>((_, reject) => {
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }));
    const { result } = renderHook(() => useResourcePolling(loader, "a", message));
    await advance(19_999);
    expect(loader).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(result.current).toMatchObject({ error: "Request timed out. Please try again.", retrying: true });
    await advance(2_000);
    expect(loader).toHaveBeenCalledTimes(2);
  });

  it("pauses hidden timers and refreshes on visibility", async () => {
    visibility(true);
    const loader = vi.fn().mockResolvedValue(3);
    renderHook(() => useResourcePolling(loader, "a", message));
    await advance(60_000);
    expect(loader).not.toHaveBeenCalled();
    visibility(false);
    await flush();
    expect(loader).toHaveBeenCalledTimes(1);
    visibility(true);
    await advance(60_000);
    expect(loader).toHaveBeenCalledTimes(1);
    visibility(false);
    await flush();
    expect(loader).toHaveBeenCalledTimes(2);
  });

  it("cancels an active hidden read, waits for settlement, then refreshes exactly once", async () => {
    const first = pending<number>();
    const loader = vi.fn().mockImplementationOnce(() => first.promise).mockResolvedValue(8);
    const { result } = renderHook(() => useResourcePolling(loader, "a", message));
    const signal = loader.mock.calls[0][0] as AbortSignal;
    visibility(true);
    expect(signal.aborted).toBe(true);
    visibility(false);
    expect(loader).toHaveBeenCalledTimes(1);
    await act(async () => first.resolve(99));
    expect(loader).toHaveBeenCalledTimes(2);
    expect(result.current.data).toBe(8);
  });

  it("clears values on range change and ignores late completion from the previous range", async () => {
    const old = pending<number>();
    const fresh = pending<number>();
    const loader = vi.fn().mockResolvedValueOnce(4).mockImplementationOnce(() => old.promise).mockImplementationOnce(() => fresh.promise);
    const { result, rerender } = renderHook(({ scope }) => useResourcePolling(loader, scope, message), { initialProps: { scope: "old" } });
    await flush();
    await advance(20_000);
    const signal = loader.mock.calls[1][0] as AbortSignal;
    rerender({ scope: "new" });
    expect(signal.aborted).toBe(true);
    expect(result.current).toMatchObject({ data: null, lastSuccess: null, loading: true, error: "" });
    await act(async () => old.resolve(99));
    expect(result.current.data).toBeNull();
    await act(async () => fresh.resolve(7));
    expect(result.current.data).toBe(7);
  });

  it("does not resurrect old data when returning to a range before the intervening read completes", async () => {
    const loader = vi.fn().mockResolvedValueOnce(4).mockImplementation(() => new Promise(() => {}));
    const { result, rerender } = renderHook(({ scope }) => useResourcePolling(loader, scope, message), { initialProps: { scope: "a" } });
    await flush();
    expect(result.current.data).toBe(4);
    rerender({ scope: "b" });
    expect(result.current.data).toBeNull();
    rerender({ scope: "a" });
    expect(result.current.data).toBeNull();
    expect(result.current.lastSuccess).toBeNull();
  });

  it("cancels requests and timers on unmount without rendering abort errors", async () => {
    const first = pending<number>();
    const loader = vi.fn((signal: AbortSignal) => { void signal; return first.promise; });
    const { unmount } = renderHook(() => useResourcePolling(loader, "a", message));
    const signal = loader.mock.calls[0][0] as AbortSignal;
    unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => first.reject(new DOMException("Aborted", "AbortError")));
    await advance(120_000);
    expect(loader).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });
});
