import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NoMatchMessage } from "@/components/chat/NoMatchMessage";

describe("NoMatchMessage (UI-05)", () => {
  test("renders 'No matching policy found' heading", () => {
    render(<NoMatchMessage />);
    expect(screen.getByText("No matching policy found")).toBeInTheDocument();
  });

  test("renders body copy about rephrasing the question", () => {
    render(<NoMatchMessage />);
    expect(
      screen.getByText(/The query did not match any passages/)
    ).toBeInTheDocument();
    expect(screen.getByText(/Try rephrasing your question/)).toBeInTheDocument();
  });
});
