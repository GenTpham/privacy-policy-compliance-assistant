import { describe, test } from "vitest";

describe("useAuth (UI-06)", () => {
  test.skip("logout clears localStorage access_token and refresh_token", () => {
    // TODO: set both tokens in localStorage; call logout(); verify both removed
  });

  test.skip("logout calls POST /auth/logout with Bearer token", () => {
    // TODO: mock fetch; call logout(); verify fetch called with /auth/logout
  });

  test.skip("login stores access_token and refresh_token in localStorage", () => {
    // TODO: mock fetch returning tokens; call login(); verify localStorage set
  });
});
