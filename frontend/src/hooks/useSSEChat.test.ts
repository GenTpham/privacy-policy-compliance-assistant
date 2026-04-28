import { describe, test, expect, vi, beforeEach } from "vitest";
import React from "react";
import { renderHook, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useSSEChat } from "@/hooks/useSSEChat";

// .ts file — no JSX allowed; use React.createElement for wrapper
const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(MemoryRouter, null, children);

// Helper: create a mock SSE Response from an array of event payloads
function makeMockSSEResponse(events: object[]): Response {
  const lines = events
    .map((ev) => `data: ${JSON.stringify(ev)}\n\n`)
    .join("");
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(lines));
      controller.close();
    },
  });
  return new Response(stream, { status: 200 });
}

describe("useSSEChat (UI-03)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.setItem("access_token", "test-token");
  });

  test("initial state: messages=[], isStreaming=false", () => {
    const { result } = renderHook(() => useSSEChat(), { wrapper });
    expect(result.current.messages).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
  });

  test("isStreaming is false after done event", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      makeMockSSEResponse([
        { type: "delta", content: "Hello" },
        {
          type: "done",
          answer: "Hello",
          citations: [
            { id: 1, qdrant_id: "abc", title: "Doc A", text: "Full text" },
          ],
        },
      ])
    );
    vi.stubGlobal("fetch", mockFetch);

    const { result } = renderHook(() => useSSEChat(), { wrapper });

    await act(async () => {
      await result.current.submit("test question", vi.fn());
    });

    expect(result.current.isStreaming).toBe(false);
    expect(result.current.messages).toHaveLength(2); // user + assistant
  });

  test("tokens are appended to message content on delta events", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      makeMockSSEResponse([
        { type: "delta", content: "Hello" },
        { type: "delta", content: " world" },
        {
          type: "done",
          answer: "Hello world",
          citations: [{ id: 1, qdrant_id: "x", title: "T", text: "Full" }],
        },
      ])
    );
    vi.stubGlobal("fetch", mockFetch);

    const { result } = renderHook(() => useSSEChat(), { wrapper });

    await act(async () => {
      await result.current.submit("question", vi.fn());
    });

    const assistant = result.current.messages.find((m) => m.role === "assistant");
    // Final content set by done event answer
    expect(assistant?.content).toBe("Hello world");
  });

  test("citations are set on done event", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      makeMockSSEResponse([
        {
          type: "done",
          answer: "The policy states...",
          citations: [
            {
              id: 1,
              qdrant_id: "abc",
              title: "Privacy Policy",
              text: "Verbatim excerpt",
            },
          ],
        },
      ])
    );
    vi.stubGlobal("fetch", mockFetch);

    const { result } = renderHook(() => useSSEChat(), { wrapper });

    await act(async () => {
      await result.current.submit("policy question", vi.fn());
    });

    const assistant = result.current.messages.find((m) => m.role === "assistant");
    expect(assistant?.citations).toHaveLength(1);
    expect(assistant?.citations?.[0].title).toBe("Privacy Policy");
  });

  test("detects no-match when done event has citations=[]", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      makeMockSSEResponse([
        { type: "done", answer: "No matching policy found.", citations: [] },
      ])
    );
    vi.stubGlobal("fetch", mockFetch);

    const { result } = renderHook(() => useSSEChat(), { wrapper });

    await act(async () => {
      await result.current.submit("unknown question", vi.fn());
    });

    const assistant = result.current.messages.find((m) => m.role === "assistant");
    expect(assistant?.isNoMatch).toBe(true);
    expect(assistant?.citations).toHaveLength(0);
  });
});
