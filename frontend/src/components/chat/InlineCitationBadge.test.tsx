import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InlineCitationBadge } from "./InlineCitationBadge";

describe("InlineCitationBadge", () => {
  test("renders citation id", () => {
    render(<InlineCitationBadge id={3} />);
    expect(screen.getByRole("button", { name: /citation 3/i })).toHaveTextContent("[3]");
  });

  test("calls onClick with id when clicked", async () => {
    const handleClick = vi.fn();
    render(<InlineCitationBadge id={3} onClick={handleClick} />);
    await userEvent.click(screen.getByRole("button", { name: /citation 3/i }));
    expect(handleClick).toHaveBeenCalledWith(3);
  });
});
