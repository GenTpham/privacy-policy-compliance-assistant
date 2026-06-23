import { createContext, useContext } from "react";

export interface ThemeTokens {
  bg: string;
  surface: string;
  surface2: string;
  border: string;
  border2: string;
  text: string;
  text2: string;
  text3: string;
  muted: string;
  faint: string;
  faintest: string;
  userBubble: string;
  userBubbleText: string;
  isDark: boolean;
}

export function makeTokens(isDark: boolean): ThemeTokens {
  if (isDark) {
    return {
      bg:            "#030712",
      surface:       "#111827",
      surface2:      "#1F2937",
      border:        "#374151",
      border2:       "#4B5563",
      text:          "#F9FAFB",
      text2:         "#D1D5DB",
      text3:         "#9CA3AF",
      muted:         "#6B7280",
      faint:         "#4B5563",
      faintest:      "#374151",
      userBubble:    "#1F2937",
      userBubbleText:"#F9FAFB",
      isDark: true,
    };
  }
  return {
    bg:            "#F9FAFB",
    surface:       "#FFFFFF",
    surface2:      "#F3F4F6",
    border:        "#E5E7EB",
    border2:       "#D1D5DB",
    text:          "#030712",
    text2:         "#374151",
    text3:         "#6B7280",
    muted:         "#9CA3AF",
    faint:         "#D1D5DB",
    faintest:      "#E5E7EB",
    userBubble:    "#030712",
    userBubbleText:"#F9FAFB",
    isDark: false,
  };
}

export interface ThemeContextValue {
  t: ThemeTokens;
  accent: string;
  isDark: boolean;
  setDark: (v: boolean) => void;
  setAccent: (v: string) => void;
}

export const ThemeContext = createContext<ThemeContextValue>({
  t: makeTokens(false),
  accent: "#6D94C5",
  isDark: false,
  setDark: () => {},
  setAccent: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}
