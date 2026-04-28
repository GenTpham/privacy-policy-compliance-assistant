import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Mock hooks to prevent actual API calls
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    logout: vi.fn(),
    forceLogout: vi.fn(),
  }),
}));

vi.mock("@/hooks/useSSEChat", () => ({
  useSSEChat: () => ({
    messages: [],
    isStreaming: false,
    submit: vi.fn(),
  }),
}));

describe("ChatPage (UI-02)", () => {
  beforeEach(() => {
    localStorage.setItem("access_token", "test-token");
  });

  test("renders message list and chat input", async () => {
    const { ChatPage } = await import("@/pages/ChatPage");
    render(
      <MemoryRouter>
        <ChatPage />
      </MemoryRouter>
    );
    // Input row present
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    // Send button present
    expect(
      screen.getByRole("button", { name: /send message/i })
    ).toBeInTheDocument();
  });

  test("renders empty state heading when messages is empty", async () => {
    const { ChatPage } = await import("@/pages/ChatPage");
    render(
      <MemoryRouter>
        <ChatPage />
      </MemoryRouter>
    );
    expect(screen.getByText("Ask a policy question")).toBeInTheDocument();
  });
});
