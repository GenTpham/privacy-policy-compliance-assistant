import { describe, test, expect, vi, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useSSEChat } from "./useSSEChat";

global.fetch = vi.fn();

function createStream(chunks: string[]) {
  let i = 0;
  return {
    getReader: () => ({
      read: async () => {
        if (i >= chunks.length) return { done: true, value: undefined };
        const value = new TextEncoder().encode(chunks[i++]);
        return { done: false, value };
      },
      releaseLock: vi.fn(),
    }),
  };
}

describe("useSSEChat retry", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("retry resubmits the last user message after an error", async () => {
    const { result } = renderHook(() => useSSEChat());

    // First submit fails with a network error
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    await act(async () => {
      await result.current.submit("What data does Google collect?", vi.fn());
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1].isError).toBe(true);

    // Retry succeeds
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      body: createStream([
        `data: {"type":"delta","content":"Answer"}\n\n`,
        `data: {"type":"done","answer":"Answer.","citations":[]}\n\n`,
      ]),
    });

    await act(async () => {
      await result.current.retry(vi.fn());
    });

    await waitFor(() =>
      expect(result.current.messages.some((m) => m.content === "Answer.")).toBe(true)
    );
    expect(result.current.isStreaming).toBe(false);
  });

  test("retry does not create a duplicate user message", async () => {
    const { result } = renderHook(() => useSSEChat());

    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    await act(async () => {
      await result.current.submit("What data does Google collect?", vi.fn());
    });

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      body: createStream([
        `data: {"type":"done","answer":"Answer.","citations":[]}\n\n`,
      ]),
    });

    await act(async () => {
      await result.current.retry(vi.fn());
    });

    const userMessages = result.current.messages.filter((m) => m.role === "user");
    expect(userMessages).toHaveLength(1);
    expect(userMessages[0].content).toBe("What data does Google collect?");
  });
});
