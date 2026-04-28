import { describe, test } from "vitest";

describe("useSSEChat (UI-03)", () => {
  test.skip("isStreaming is true during delta events, false after done event", () => {
    // TODO: mock fetch with SSE stream; verify isStreaming state transitions
  });

  test.skip("tokens are appended to message content on delta events", () => {
    // TODO: mock fetch yielding delta events; verify content accumulates
  });

  test.skip("citations are set on done event", () => {
    // TODO: mock fetch with done event containing citations array
  });
});
