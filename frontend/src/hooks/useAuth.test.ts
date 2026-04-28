import { describe, test, expect, vi, beforeEach } from "vitest";
import React from "react";
import { renderHook, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

// .ts file — no JSX allowed; use React.createElement for wrapper
const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(MemoryRouter, null, children);

describe("useAuth (UI-06)", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  test("login stores access_token and refresh_token in localStorage", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "acc-token",
          refresh_token: "ref-token",
          token_type: "bearer",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", mockFetch);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.login("user", "pass");
    });

    expect(localStorage.getItem("access_token")).toBe("acc-token");
    expect(localStorage.getItem("refresh_token")).toBe("ref-token");
  });

  test("logout clears localStorage access_token and refresh_token", async () => {
    localStorage.setItem("access_token", "acc");
    localStorage.setItem("refresh_token", "ref");

    const mockFetch = vi.fn().mockResolvedValue(
      new Response("{}", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", mockFetch);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.logout();
    });

    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  test("logout calls POST /auth/logout with Bearer token", async () => {
    localStorage.setItem("access_token", "my-token");

    const mockFetch = vi.fn().mockResolvedValue(
      new Response("{}", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", mockFetch);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.logout();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/auth/logout",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer my-token",
        }),
      })
    );
  });

  test("forceLogout clears tokens without calling API", () => {
    localStorage.setItem("access_token", "acc");
    localStorage.setItem("refresh_token", "ref");

    const mockFetch = vi.fn();
    vi.stubGlobal("fetch", mockFetch);

    const { result } = renderHook(() => useAuth(), { wrapper });

    act(() => {
      result.current.forceLogout();
    });

    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  test("login throws on 401 response", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Invalid credentials" }),
        { status: 401, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", mockFetch);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await expect(
      act(async () => {
        await result.current.login("user", "wrong");
      })
    ).rejects.toThrow();
  });
});
