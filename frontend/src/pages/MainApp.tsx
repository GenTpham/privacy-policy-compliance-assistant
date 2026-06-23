import { useState } from "react";
import { AppShell, type Screen } from "@/components/layout/AppShell";
import { useTheme } from "@/lib/theme";
import { useSSEChat } from "@/hooks/useSSEChat";
import { useAuth } from "@/hooks/useAuth";
import { DashboardScreen } from "./DashboardScreen";
import { AskAssistantScreen } from "./AskAssistantScreen";
import { PolicyLibraryScreen } from "./PolicyLibraryScreen";
import { ComparePoliciesScreen } from "./ComparePoliciesScreen";
import { AuditLogScreen } from "./AuditLogScreen";

export function MainApp() {
  const { t } = useTheme();
  const { forceLogout } = useAuth();

  // Lifted here so chat history survives screen switches
  const chat = useSSEChat();

  const [screen, setScreen] = useState<Screen>(() => {
    const saved = localStorage.getItem("ppca_screen");
    return (saved as Screen) ?? "dashboard";
  });

  const handleNavigate = (s: Screen) => {
    setScreen(s);
    localStorage.setItem("ppca_screen", s);
  };

    const renderScreen = () => {
    switch (screen) {
      case "dashboard": return <DashboardScreen forceLogout={forceLogout} />;
      case "ask":       return <AskAssistantScreen chat={chat} forceLogout={forceLogout} />;
      case "library":   return <PolicyLibraryScreen onAsk={() => handleNavigate("ask")} forceLogout={forceLogout} />;
      case "compare":   return <ComparePoliciesScreen />;
      case "audit":     return <AuditLogScreen />;
      case "settings":  return (
        <div style={{ padding: "40px 36px", background: t.bg, height: "100%", color: t.muted, fontSize: 13 }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: t.text, marginBottom: 8 }}>Settings</h1>
          <p>Configure index settings, API keys, user roles, and data sources here.</p>
        </div>
      );
    }
  };

  return (
    <AppShell screen={screen} onNavigate={handleNavigate}>
      {renderScreen()}
    </AppShell>
  );
}
