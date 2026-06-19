import { useState, useCallback } from "react";
import { fetchWithAuth } from "../lib/api";

export interface Citation {
  id: number;
  qdrant_id: string;
  title: string;
  text: string;
  score: number;  // cosine similarity from Qdrant, 0–1, 4 decimal places max
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isNoMatch?: boolean;
  isError?: boolean;
}

export interface UseSSEChatReturn {
  messages: Message[];
  isStreaming: boolean;
  submit: (message: string, onUnauthorized: () => void, sourceFilter?: string | null) => Promise<void>;
  retry: (onUnauthorized: () => void, sourceFilter?: string | null) => Promise<void>;
}

/**
 * Custom SSE parser over fetch ReadableStream.
 * Required because EventSource does not support Authorization headers (CONTEXT.md Specifics).
 * Handles SSE buffer fragmentation: maintains buffer string, splits on double-newline (Pitfall 2).
 */
async function* parseSSEStream(
  response: Response
): AsyncGenerator<Record<string, unknown>> {
  if (!response.body) {
    throw new Error('Response body is null — streaming not supported in this environment');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE spec: events separated by double newlines
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? ""; // keep incomplete last chunk in buffer

    for (const event of events) {
      for (const line of event.split("\n")) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data) yield JSON.parse(data);
        }
      }
    }
  }
}

/**
 * Chat hook — state machine: idle → streaming → done/error → idle
 *
 * History management: client owns conversation history (backend is stateless).
 * Each submit call sends the full prior message history.
 * History items must have role "user" or "assistant" — never "system" (HTTP 422).
 */
export function useSSEChat(): UseSSEChatReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  /**
   * Shared fetch + SSE handler. Operates on the last message in state, which
   * must be an assistant placeholder inserted by the caller (submit or retry).
   */
  const runStream = useCallback(
    async (
      message: string,
      history: { role: string; content: string }[],
      onUnauthorized: () => void,
      sourceFilter?: string | null
    ): Promise<void> => {
      try {
        const response = await fetchWithAuth(
          "/api/chat",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              message,
              history,
              source_filter: sourceFilter ?? null,
            }),
          },
          onUnauthorized
        );

        if (!response.ok) {
          // Non-401 error (fetchWithAuth handles 401 with refresh retry)
          throw new Error(`HTTP ${response.status}`);
        }

        for await (const event of parseSSEStream(response)) {
          const ev = event as {
            type: string;
            content?: string;
            answer?: string;
            citations?: Citation[];
            message?: string; // error event field is "message" NOT "detail" — Pitfall 5
          };

          if (ev.type === "delta" && ev.content !== undefined) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = {
                ...last,
                content: last.content + ev.content,
              };
              return updated;
            });
          } else if (ev.type === "done") {
            const citations = ev.citations ?? [];
            const isNoMatch = citations.length === 0;
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                role: "assistant",
                content: ev.answer ?? "",
                citations,
                isNoMatch,
              };
              return updated;
            });
            setIsStreaming(false);
          } else if (ev.type === "error") {
            // Error event field is "message" NOT "detail" — Pitfall 5 in RESEARCH.md
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                role: "assistant",
                content:
                  "Something went wrong while generating the response. Please try again.",
                isError: true,
              };
              return updated;
            });
            setIsStreaming(false);
          }
        }
      } catch (_err) {
        // Network failure or fetchWithAuth threw (double 401 → onUnauthorized already called)
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant" && !last.content) {
            updated[updated.length - 1] = {
              role: "assistant",
              content:
                "Something went wrong while generating the response. Please try again.",
              isError: true,
            };
          }
          return updated;
        });
        setIsStreaming(false);
      }
    },
    []
  );

  const submit = useCallback(
    async (message: string, onUnauthorized: () => void, sourceFilter?: string | null): Promise<void> => {
      if (isStreaming) return; // prevent concurrent submits

      // Build history from current messages (exclude the user message we're about to add)
      // Only role "user" | "assistant" — never "system"
      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      // Add user message immediately
      const userMessage: Message = { role: "user", content: message };
      // Add placeholder assistant message for streaming
      const assistantPlaceholder: Message = {
        role: "assistant",
        content: "",
        citations: [],
      };

      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
      setIsStreaming(true);

      await runStream(message, history, onUnauthorized, sourceFilter);
    },
    [messages, isStreaming, runStream]
  );

  const retry = useCallback(
    async (onUnauthorized: () => void, sourceFilter?: string | null): Promise<void> => {
      if (isStreaming) return;

      const lastUserIdx = messages.map((m) => m.role).lastIndexOf("user");
      if (lastUserIdx === -1) return;
      const lastUserMessage = messages[lastUserIdx];

      // History = everything before the last user turn (no duplicate user message)
      const history = messages
        .slice(0, lastUserIdx)
        .map((m) => ({ role: m.role, content: m.content }));

      // Drop trailing assistant message(s), then add a fresh placeholder
      setMessages((prev) => {
        const trimmed = [...prev];
        while (trimmed.length > 0 && trimmed[trimmed.length - 1].role === "assistant") {
          trimmed.pop();
        }
        return [...trimmed, { role: "assistant", content: "", citations: [] } as Message];
      });
      setIsStreaming(true);

      await runStream(lastUserMessage.content, history, onUnauthorized, sourceFilter);
    },
    [messages, isStreaming, runStream]
  );

  return { messages, isStreaming, submit, retry };
}
