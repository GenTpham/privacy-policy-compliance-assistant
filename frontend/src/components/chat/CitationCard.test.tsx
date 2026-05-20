import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CitationCard } from "@/components/chat/CitationCard";
import type { Citation } from "@/hooks/useSSEChat";

const mockCitation: Citation = {
  id: 1,
  qdrant_id: "abc-123",
  title: "Google Privacy Policy",
  text: "Users may request deletion of their personal data by contacting our support team through the privacy settings page.",
  score: 0.42,
};

const shortCitation: Citation = {
  id: 2,
  qdrant_id: "def-456",
  title: "Short Doc",
  text: "Short text",
  score: 0.37,
};

describe("CitationCard (UI-04, CITE-04)", () => {
  test("renders document title in collapsed state", () => {
    render(<CitationCard citation={mockCitation} />);
    expect(screen.getByText("Google Privacy Policy")).toBeInTheDocument();
  });

  test("truncates preview text to 50 chars with ellipsis", () => {
    render(<CitationCard citation={mockCitation} />);
    const expectedPreview = mockCitation.text.slice(0, 50) + "…";
    expect(screen.getByText(expectedPreview)).toBeInTheDocument();
  });

  test("does not show full text in collapsed state", () => {
    render(<CitationCard citation={mockCitation} />);
    // Full text is longer than 50 chars — should not be visible collapsed
    expect(screen.queryByText(mockCitation.text)).not.toBeInTheDocument();
  });

  test("shows full text after clicking to expand", async () => {
    render(<CitationCard citation={mockCitation} />);
    const trigger = screen.getByRole("button", { name: /expand citation/i });
    await userEvent.click(trigger);
    expect(screen.getByText(mockCitation.text)).toBeInTheDocument();
  });

  test("does not truncate short text", () => {
    render(<CitationCard citation={shortCitation} />);
    expect(screen.getByText("Short text")).toBeInTheDocument();
  });
});
