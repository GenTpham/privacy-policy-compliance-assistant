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
  const { isDark, setDark } = useTheme();
  const { logout } = useAuth();

  return (
    <div className="flex h-screen overflow-hidden text-sm bg-background text-text-1">

      {/* Sidebar */}
      <aside className="w-[240px] bg-[#161b22] dark:bg-[#0d1117] flex flex-col shrink-0 border-r border-border">
        {/* Logo */}
        <div className="px-5 py-6 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0 text-white shadow-md">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 1L2 4v4c0 3.3 2.4 6.4 6 7 3.6-.6 6-3.7 6-7V4L8 1z" fill="currentColor"/>
              </svg>
            </div>
            <div>
              <div className="text-[15px] font-bold text-slate-50 tracking-tight leading-tight">PrivacyAI</div>
              <div className="text-[11px] text-slate-400 font-medium">Compliance Assistant</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-4 py-6 overflow-y-auto space-y-1.5">
          {NAV_ITEMS.map((item) => {
            const active = screen === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-lg border-none cursor-pointer transition-all duration-200 ${
                  active 
                    ? "bg-accent/15 text-accent font-semibold shadow-sm" 
                    : "bg-transparent text-slate-400 font-medium hover:bg-white/5 hover:text-slate-200"
                } text-sm text-left`}
              >
                <span className={`text-[15px] ${active ? "opacity-100" : "opacity-60"}`}>{item.icon}</span>
                {item.label}
                {active && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-accent shadow-[0_0_8px_rgba(var(--color-accent),0.8)]" />}
              </button>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="px-5 py-5 border-t border-white/5 bg-black/10">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Index: Live</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-accent flex items-center justify-center text-sm font-bold text-white shadow-md">A</div>
            <div>
              <div className="text-sm font-semibold text-slate-50">analyst</div>
              <div className="text-[11px] text-slate-400">firm.io</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        
        {/* Top bar */}
        <header className="h-16 bg-surface border-b border-border flex items-center px-8 gap-5 shrink-0 shadow-sm z-10">
          <div className="flex-1">
            <div className="flex items-center gap-2.5 bg-surface-2 border border-border rounded-lg px-3.5 py-2.5 w-80 transition-all focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20 focus-within:bg-background">
              <svg width="14" height="14" viewBox="0 0 13 13" fill="none" className="text-faint">
                <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" strokeWidth="1.4"/>
                <path d="M9 9l2.5 2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              <input 
                type="text" 
                placeholder="Search policies, queries…" 
                className="bg-transparent border-none outline-none text-[13px] text-text-1 w-full placeholder:text-faint"
              />
            </div>
          </div>

          <div className="flex items-center gap-2.5 bg-accent/10 border border-accent/20 rounded-full px-4 py-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]" />
            <span className="text-[11px] text-accent font-semibold tracking-wide">{indexedCount} policies · {totalChunks.toLocaleString()} chunks</span>
          </div>

          <button
            onClick={() => setDark(!isDark)}
            title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg border border-border bg-surface-2 text-text-2 font-medium cursor-pointer text-[13px] hover:bg-border transition-colors hover:text-text-1 hover:shadow-sm active:scale-95"
          >
            {isDark ? <SunIcon /> : <MoonIcon />}
            <span>{isDark ? "Light" : "Dark"}</span>
          </button>

          <button
            onClick={() => logout()}
            className="bg-transparent border border-border rounded-lg px-4 py-2 text-[13px] font-medium text-text-2 cursor-pointer hover:bg-border transition-colors hover:text-text-1 active:scale-95"
          >
            Sign out
          </button>

          <div className="w-9 h-9 rounded-full bg-accent flex items-center justify-center text-sm font-bold text-white shadow-md cursor-pointer hover:opacity-90 transition-opacity ring-2 ring-transparent hover:ring-accent/30">A</div>
        </header>

        {/* Screen content */}
        <main className="flex-1 overflow-hidden flex flex-col bg-background relative">
          {children}
        </main>
      </div>
    </div>
  );
}

export type { Screen };
