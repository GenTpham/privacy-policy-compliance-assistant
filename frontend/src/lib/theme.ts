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
      bg:            "#0E1825",
      surface:       "#152033",
      surface2:      "#1C2A40",
      border:        "#2A3F5C",
      border2:       "#1F3049",
      text:          "#FFFFFF",
      text2:         "#E8F2FF",
      text3:         "#CBDCEB",
      muted:         "#8FA8C4",
      faint:         "#5C7A9B",
      faintest:      "#2A3F5C",
      userBubble:    "#1E4A7A",
      userBubbleText:"#F5EFE6",
      isDark: true,
    };
  }
  return {
    bg:            "#6D94C5",
    surface:       "#CBDCEB",
    surface2:      "#B8CDE0",
    border:        "#E8DFCA",
    border2:       "#F5EFE6",
    text:          "#0E1825",
    text2:         "#1C3050",
    text3:         "#2E4E78",
    muted:         "#4A6A90",
    faint:         "#7A9FCA",
    faintest:      "#A8C4E0",
    userBubble:    "#1C3050",
    userBubbleText:"#F5EFE6",
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
