import { LoginForm } from "@/components/auth/LoginForm";
import { useTheme } from "@/lib/theme";

export function LoginPage() {
  const { t, accent } = useTheme();
  return (
    <div style={{ minHeight: "100vh", background: t.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: "0 16px" }}>
      <div style={{ width: "100%", maxWidth: 400, background: t.surface, border: `1px solid ${t.border}`, borderRadius: 10, padding: 32 }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 28 }}>
          <div style={{ width: 32, height: 32, background: accent, borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 1L2 4v4c0 3.3 2.4 6.4 6 7 3.6-.6 6-3.7 6-7V4L8 1z" fill="rgba(255,255,255,0.9)"/>
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: t.text, lineHeight: 1.2 }}>PrivacyAI</div>
            <div style={{ fontSize: 11, color: t.muted }}>Compliance Assistant</div>
          </div>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
