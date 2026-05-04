import { type ReactNode } from "react";
import { useTheme } from "@/lib/theme";
import { useAuth } from "@/hooks/useAuth";

type Screen = "dashboard" | "ask" | "library" | "compare" | "audit" | "settings";

const NAV_ITEMS: { id: Screen; label: string; icon: string }[] = [
  { id: "dashboard", label: "Dashboard",        icon: "▦"  },
  { id: "ask",       label: "Ask Assistant",    icon: "💬" },
  { id: "library",   label: "Policy Library",   icon: "📁" },
  { id: "compare",   label: "Compare Policies", icon: "⇔"  },
  { id: "audit",     label: "Audit Log",        icon: "📋" },
  { id: "settings",  label: "Settings",         icon: "⚙"  },
];

interface AppShellProps {
  screen: Screen;
  onNavigate: (s: Screen) => void;
  children: ReactNode;
  indexedCount?: number;
  totalChunks?: number;
}

function MoonIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
    </svg>
  );
}

function SunIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5"/>
      <line x1="12" y1="1" x2="12" y2="3"/>
      <line x1="12" y1="21" x2="12" y2="23"/>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
      <line x1="1" y1="12" x2="3" y2="12"/>
      <line x1="21" y1="12" x2="23" y2="12"/>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
    </svg>
  );
}

export function AppShell({ screen, onNavigate, children, indexedCount = 8, totalChunks = 2083 }: AppShellProps) {
  const { t, accent, isDark, setDark } = useTheme();
  const { logout } = useAuth();

  const sidebarBg = "#1E293B";
  const sidebarText = "#94A3B8";

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", fontSize: 14, background: t.bg, color: t.text }}>

      {/* Sidebar */}
      <aside style={{ width: 220, background: sidebarBg, display: "flex", flexDirection: "column", flexShrink: 0 }}>
        {/* Logo */}
        <div style={{ padding: "20px 18px 16px", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 30, height: 30, background: accent, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 1L2 4v4c0 3.3 2.4 6.4 6 7 3.6-.6 6-3.7 6-7V4L8 1z" fill="rgba(255,255,255,0.9)"/>
              </svg>
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#F8FAFC", lineHeight: 1.2 }}>PrivacyAI</div>
              <div style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", letterSpacing: "0.03em" }}>Compliance Assistant</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: "12px 10px", overflowY: "auto" }}>
          {NAV_ITEMS.map((item) => {
            const active = screen === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                style={{
                  display: "flex", alignItems: "center", gap: 10, width: "100%",
                  padding: "8px 10px", borderRadius: 6, border: "none", cursor: "pointer",
                  marginBottom: 2,
                  background: active ? "rgba(255,255,255,0.1)" : "transparent",
                  color: active ? "#fff" : sidebarText,
                  fontWeight: active ? 600 : 400, fontSize: 13, textAlign: "left",
                  transition: "background 0.1s",
                }}
              >
                <span style={{ fontSize: 14, opacity: active ? 1 : 0.6 }}>{item.icon}</span>
                {item.label}
                {active && <div style={{ marginLeft: "auto", width: 4, height: 4, borderRadius: "50%", background: accent }} />}
              </button>
            );
          })}
        </nav>

        {/* Bottom */}
        <div style={{ padding: "12px 14px", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#22C55E", flexShrink: 0 }} />
            <span style={{ fontSize: 11, color: "rgba(255,255,255,0.5)" }}>Index: Live</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 26, height: 26, borderRadius: "50%", background: accent, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "#fff" }}>A</div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#F8FAFC" }}>analyst</div>
              <div style={{ fontSize: 10, color: "rgba(255,255,255,0.4)" }}>firm.io</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>

        {/* Top bar */}
        <header style={{ height: 52, background: t.surface, borderBottom: `1px solid ${t.border}`, display: "flex", alignItems: "center", padding: "0 24px", gap: 14, flexShrink: 0 }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, background: t.surface2, border: `1px solid ${t.border}`, borderRadius: 6, padding: "6px 12px", width: 280 }}>
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <circle cx="5.5" cy="5.5" r="4" stroke={t.faint} strokeWidth="1.4"/>
                <path d="M9 9l2.5 2.5" stroke={t.faint} strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              <span style={{ fontSize: 12, color: t.faint }}>Search policies, queries…</span>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 4, background: `${accent}18`, border: `1px solid ${accent}30`, borderRadius: 5, padding: "4px 10px" }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#22C55E" }} />
            <span style={{ fontSize: 11, color: accent, fontWeight: 600 }}>{indexedCount} policies · {totalChunks.toLocaleString()} chunks</span>
          </div>

          <button
            onClick={() => setDark(!isDark)}
            title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", borderRadius: 6, border: `1px solid ${t.border}`, background: t.surface2, color: t.text3, cursor: "pointer", fontSize: 12 }}
          >
            {isDark ? <SunIcon /> : <MoonIcon />}
            <span>{isDark ? "Light" : "Dark"}</span>
          </button>

          <button
            onClick={() => logout()}
            style={{ background: "none", border: `1px solid ${t.border}`, borderRadius: 6, padding: "6px 12px", fontSize: 12, color: t.text3, cursor: "pointer" }}
          >
            Sign out
          </button>

          <div style={{ width: 30, height: 30, borderRadius: "50%", background: accent, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, color: "#fff", cursor: "pointer" }}>A</div>
        </header>

        {/* Screen content */}
        <main style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column", background: t.bg }}>
          {children}
        </main>
      </div>
    </div>
  );
}

export type { Screen };
