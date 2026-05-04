import { useState, useEffect, type ReactNode } from "react";
import { ThemeContext, makeTokens } from "@/lib/theme";

const STORAGE_KEY = "ppca_tweaks";
const PREFS_VERSION = "v3"; // bump when changing DEFAULTS to force reset

interface Prefs { dark: boolean; accentColor: string; version: string; }
const DEFAULTS: Prefs = { dark: false, accentColor: "#6D94C5", version: PREFS_VERSION };

function load(): Prefs {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}") as Partial<Prefs>;
    // If version mismatch, discard stale prefs and use DEFAULTS
    if (saved.version !== PREFS_VERSION) return DEFAULTS;
    return { ...DEFAULTS, ...saved };
  } catch {
    return DEFAULTS;
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(load);

  const isDark = prefs.dark;
  const accent = prefs.accentColor;
  const t = makeTokens(isDark);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    document.body.classList.toggle("dark", isDark);
    document.body.style.background = t.bg;
    document.body.style.color = t.text;
  }, [prefs, isDark, t.bg, t.text]);

  const setDark = (v: boolean) => setPrefs((p) => ({ ...p, dark: v }));
  const setAccent = (v: string) => setPrefs((p) => ({ ...p, accentColor: v }));

  return (
    <ThemeContext.Provider value={{ t, accent, isDark, setDark, setAccent }}>
      {children}
    </ThemeContext.Provider>
  );
}
