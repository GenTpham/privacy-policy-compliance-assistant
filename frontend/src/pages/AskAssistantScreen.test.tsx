import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "@/components/layout/ThemeProvider";
import { AskAssistantScreen } from "./AskAssistantScreen";
import type { UseSSEChatReturn, Citation, Message } from "@/hooks/useSSEChat";

vi.mock("@/lib/api", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ sources: ["Google Privacy Policy"] }),
  }),
}));

function makeChat(messages: Message[] = [], isStreaming = false): UseSSEChatReturn {
  return {
    messages,
    isStreaming,
    submit: vi.fn(),
    retry: vi.fn(),
  };
}

const citation: Citation = {
  id: 1,
  qdrant_id: "a",
  title: "Google Privacy Policy",
  text: "Users can delete data.",
  score: 0.91,
};

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe("AskAssistantScreen", () => {
  test("renders AnswerCard for completed assistant message", async () => {
    const chat = makeChat([
      { role: "user", content: "Hello" },
      { role: "assistant", content: "Answer [1].", citations: [citation] },
    ]);
    renderWithTheme(<AskAssistantScreen chat={chat} forceLogout={vi.fn()} />);
    expect(await screen.findByRole("button", { name: /citation 1/i })).toBeInTheDocument();
  });

  test("opens Evidence panel when citation badge is clicked", async () => {
    const chat = makeChat([
      { role: "user", content: "Hello" },
      { role: "assistant", content: "Answer [1].", citations: [citation] },
    ]);
    renderWithTheme(<AskAssistantScreen chat={chat} forceLogout={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /citation 1/i }));
    expect(screen.getByText(/Evidence/i)).toBeInTheDocument();
  });

  test("calls retry on error answer", async () => {
    const chat = makeChat([
      { role: "user", content: "Hello" },
      { role: "assistant", content: "", isError: true },
    ]);
    renderWithTheme(<AskAssistantScreen chat={chat} forceLogout={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /thử lại/i }));
    expect(chat.retry).toHaveBeenCalled();
  });
});
