import { describe, test } from "vitest";

describe("ProtectedRoute (UI-01)", () => {
  test.skip("unauthenticated visit to / renders Navigate to /login", () => {
    // TODO: render ProtectedRoute without access_token in localStorage
    // expect Navigate to /login to be rendered
  });

  test.skip("authenticated visit to / renders children", () => {
    // TODO: set localStorage.access_token, render ProtectedRoute with children
    // expect children to be rendered
  });
});
