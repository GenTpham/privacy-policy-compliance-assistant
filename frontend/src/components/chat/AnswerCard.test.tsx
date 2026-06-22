import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "@/components/layout/ThemeProvider";
import { AnswerCard } from "./AnswerCard";
import type { Citation } from "@/hooks/useSSEChat";

const citations: Citation[] = [
  { id: 1, qdrant_id: "a", title: "Google Privacy Policy", text: "Users can delete data.", score: 0.91 },
  { id: 2, qdrant_id: "b", title: "Meta Privacy Policy", text: "Meta retains data.", score: 0.74 },
];

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe("AnswerCard", () => {
  test("renders parsed answer with inline citation badges", () => {
    renderWithTheme(<AnswerCard content="Answer [1] and [2]." citations={citations} />);
    expect(screen.getByRole("button", { name: /citation 1/i })).toHaveTextContent("[1]");
    expect(screen.getByRole("button", { name: /citation 2/i })).toHaveTextContent("[2]");
  });

  test("opens evidence when citation badge is clicked", async () => {
    const openEvidence = vi.fn();
    renderWithTheme(
      <AnswerCard content="Answer [1]." citations={citations} onOpenEvidence={openEvidence} />
    );
    await userEvent.click(screen.getByRole("button", { name: /citation 1/i }));
    expect(openEvidence).toHaveBeenCalledWith(citations[0]);
  });

  test("renders sources section with cited sources", () => {
    renderWithTheme(<AnswerCard content="Answer [1]." citations={citations} />);
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("Google Privacy Policy")).toBeInTheDocument();
  });

  test("renders no-match message", () => {
    renderWithTheme(<AnswerCard content="No answer." citations={[]} isNoMatch />);
    expect(screen.getByText(/No matching policy sections found/i)).toBeInTheDocument();
  });

  test("renders error state with retry button", async () => {
    const retry = vi.fn();
    renderWithTheme(<AnswerCard content="" isError onRetry={retry} />);
    await userEvent.click(screen.getByRole("button", { name: /thử lại/i }));
    expect(retry).toHaveBeenCalled();
  });
});
