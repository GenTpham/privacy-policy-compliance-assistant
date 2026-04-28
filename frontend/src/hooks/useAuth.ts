import { useNavigate } from "react-router-dom";
import { tokens } from "../lib/tokens";
import { apiLogin, apiLogout } from "../lib/api";

/**
 * Auth hook. Provides login, logout, and forceLogout operations.
 *
 * - login: calls /auth/login, stores tokens, navigates to /
 * - logout: calls /auth/logout (D-11 — fire and forget), clears tokens, navigates to /login
 * - forceLogout: called by fetchWithAuth on double 401 (D-10) — clears tokens, navigates to /login
 *   without calling the API (the token is already dead)
 */
export function useAuth() {
  const navigate = useNavigate();

  const login = async (username: string, password: string): Promise<void> => {
    const resp = await apiLogin(username, password);
    if (!resp.ok) {
      throw new Error("Invalid credentials");
    }
    const { access_token, refresh_token } = await resp.json();
    tokens.setBoth(access_token, refresh_token);
    navigate("/");
  };

  const logout = async (): Promise<void> => {
    const accessToken = tokens.getAccess();
    if (accessToken) {
      // Fire-and-forget per D-11: don't await, don't throw on failure
      apiLogout(accessToken).catch(() => {});
    }
    tokens.clearAll();
    navigate("/login");
  };

  /**
   * Called by fetchWithAuth when refresh token is expired/invalid (D-10).
   * Does not call the API — token is dead.
   */
  const forceLogout = (): void => {
    tokens.clearAll();
    navigate("/login");
  };

  return { login, logout, forceLogout };
}
