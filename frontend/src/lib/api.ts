const BASE_URL = import.meta.env.VITE_API_URL ?? "";
import { tokens } from "./tokens";

// Module-level flag prevents concurrent refresh storms (D-10).
// If a 401 arrives while a refresh is already in-flight, call onUnauthorized
// immediately rather than queuing another refresh.
let isRefreshing = false;

/**
 * Authenticated fetch wrapper.
 * On 401: attempts one silent token refresh (D-09), then retries.
 * On double 401: calls onUnauthorized (clears tokens + redirects to /login per D-10).
 *
 * IMPORTANT: Do NOT use this function for /auth/* endpoints — they do not require
 * an access token and calling it on /auth/refresh would create an infinite loop.
 */
export async function fetchWithAuth(
  url: string,
  options: RequestInit,
  onUnauthorized: () => void
): Promise<Response> {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${tokens.getAccess()}`,
    },
  });

  if (response.status !== 401) return response;

  if (isRefreshing) {
    onUnauthorized();
    throw new Error("Already refreshing — force logout");
  }

  isRefreshing = true;
  try {
    const refreshToken = tokens.getRefresh();
    if (!refreshToken) {
      onUnauthorized();
      throw new Error("No refresh token stored — force logout");
    }
    const refreshResp = await fetch("/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!refreshResp.ok) {
      onUnauthorized();
      throw new Error("Refresh failed — force logout");
    }
    const { access_token } = await refreshResp.json();
    tokens.setAccess(access_token);
  } finally {
    isRefreshing = false;
  }

  // Retry original request once with new access token
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${tokens.getAccess()}`,
    },
  });
}

/** Plain auth endpoint wrappers — do NOT go through fetchWithAuth */

export async function apiLogin(
  username: string,
  password: string
): Promise<Response> {
  return fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

export async function apiRefresh(refreshToken: string): Promise<Response> {
  return fetch("/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function apiLogout(accessToken: string): Promise<Response> {
  // Send bearer header but do NOT use fetchWithAuth — logout must never trigger
  // a refresh attempt (fire-and-forget per D-11, CONTEXT.md).
  return fetch("/auth/logout", {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}
