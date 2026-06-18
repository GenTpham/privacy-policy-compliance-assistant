import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "@/components/layout/ThemeProvider";
import { MessageBubble } from "./MessageBubble";
import type { Citation } from "@/hooks/useSSEChat";

const citations: Citation[] = [
  { id: 1, qdrant_id: "a", title: "Google Privacy Policy", text: "Users can delete data.", score: 0.91 },
];

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe("MessageBubble", () => {
  test("renders user message as bubble", () => {
    renderWithTheme(<MessageBubble role="user" content="Hello" />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  test("renders AnswerCard for completed assistant message", () => {
    renderWithTheme(
      <MessageBubble role="assistant" content="Answer [1]." citations={citations} />
    );
    expect(screen.getByRole("button", { name: /citation 1/i })).toBeInTheDocument();
  });

  test("renders plain text while streaming", () => {
    renderWithTheme(<MessageBubble role="assistant" content="Still typing" isStreaming />);
    expect(screen.getByText("Still typing")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /citation/i })).not.toBeInTheDocument();
  });

  test("passes onOpenEvidence to AnswerCard", async () => {
    const openEvidence = vi.fn();
    renderWithTheme(
      <MessageBubble
        role="assistant"
        content="Answer [1]."
        citations={citations}
        onOpenEvidence={openEvidence}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /citation 1/i }));
    expect(openEvidence).toHaveBeenCalledWith(citations[0]);
  });
});
