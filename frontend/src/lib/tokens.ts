// Centralized localStorage token I/O.
// Key names "access_token" and "refresh_token" are fixed by D-08 and must be
// consistent across this file, useAuth.ts, and api.ts.
export const tokens = {
  getAccess: (): string | null => localStorage.getItem("access_token"),
  getRefresh: (): string | null => localStorage.getItem("refresh_token"),
  setAccess: (t: string): void => {
    localStorage.setItem("access_token", t);
  },
  setBoth: (access: string, refresh: string): void => {
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
  },
  clearAll: (): void => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  },
};
