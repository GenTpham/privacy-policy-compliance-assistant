import { useState, useEffect, type ReactNode } from "react";
import { ThemeContext, makeTokens } from "@/lib/theme";

const STORAGE_KEY = "ppca_tweaks";
const PREFS_VERSION = "v4"; // bumped to v4 to force flush of old prefs
interface Prefs { dark: boolean; accentColor: string; version: string; }
const DEFAULTS: Prefs = { dark: false, accentColor: "#2563EB", version: PREFS_VERSION };

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
    document.documentElement.classList.toggle("dark", isDark);
    document.documentElement.style.background = t.bg;
    document.documentElement.style.color = t.text;
  }, [prefs, isDark, t.bg, t.text]);

  const setDark = (v: boolean) => setPrefs((p) => ({ ...p, dark: v }));
  const setAccent = (v: string) => setPrefs((p) => ({ ...p, accentColor: v }));

  return (
    <ThemeContext.Provider value={{ t, accent, isDark, setDark, setAccent }}>
      {children}
    </ThemeContext.Provider>
  );
}
