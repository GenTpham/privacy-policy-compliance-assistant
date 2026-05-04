import { useTheme } from "@/lib/theme";
import { Badge } from "@/components/ui/Badge";
import { KPI, RECENT_ACTIVITY, TOP_TOPICS, POLICIES } from "@/lib/mockData";
import type { Screen } from "@/components/layout/AppShell";

export function DashboardScreen({ onNavigate }: { onNavigate: (s: Screen) => void }) {
  const { t, accent } = useTheme();

  const kpis = [
    { label: "Total Policies",    value: String(KPI.totalPolicies),             sub: "5 vendors" },
    { label: "Indexed Chunks",    value: KPI.indexedChunks.toLocaleString(),     sub: "across all docs" },
    { label: "Queries Today",     value: String(KPI.queriesToday),               sub: "+12% vs yesterday" },
    { label: "Citation Coverage", value: KPI.citationCoverage,                   sub: `${KPI.insufficientRate} insufficient` },
  ];

  return (
    <div style={{ padding: "32px 36px", maxWidth: 1100, margin: "0 auto", overflowY: "auto", height: "100%" }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: 0 }}>Dashboard</h1>
        <p style={{ fontSize: 13, color: t.muted, marginTop: 4 }}>System overview — April 22, 2026</p>
      </div>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 28 }}>
        {kpis.map((k, i) => (
          <div key={i} style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, padding: "20px 22px" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: t.faint, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 10 }}>{k.label}</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: t.text, marginBottom: 4 }}>{k.value}</div>
            <div style={{ fontSize: 12, color: t.muted }}>{k.sub}</div>
          </div>
        ))}
      </div>

      {/* Recent Queries + Top Topics */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 20, marginBottom: 20 }}>
        {/* Recent Queries */}
        <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, overflow: "hidden" }}>
          <div style={{ padding: "16px 20px", borderBottom: `1px solid ${t.border2}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>Recent Queries</span>
            <button onClick={() => onNavigate("audit")} style={{ fontSize: 12, color: accent, background: "none", border: "none", cursor: "pointer", fontWeight: 500 }}>View all →</button>
          </div>
          {RECENT_ACTIVITY.map((a, i) => (
            <div key={i} style={{ padding: "12px 20px", borderBottom: i < RECENT_ACTIVITY.length - 1 ? `1px solid ${t.border2}` : "none", display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ fontSize: 11, color: t.faint, fontFamily: "monospace", minWidth: 40 }}>{a.time}</span>
              <span style={{ fontSize: 13, color: t.text2, flex: 1 }}>{a.query}</span>
              <Badge status={a.status} />
            </div>
          ))}
        </div>

        {/* Top Topics */}
        <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, overflow: "hidden" }}>
          <div style={{ padding: "16px 20px", borderBottom: `1px solid ${t.border2}` }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>Top Queried Topics</span>
          </div>
          {TOP_TOPICS.map((tp, i) => (
            <div key={i} style={{ padding: "12px 20px", borderBottom: i < TOP_TOPICS.length - 1 ? `1px solid ${t.border2}` : "none" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 13, color: t.text2 }}>{tp.topic}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: t.muted }}>{tp.count}</span>
              </div>
              <div style={{ height: 4, background: t.border, borderRadius: 2, overflow: "hidden" }}>
                <div style={{ width: `${(tp.count / 38) * 100}%`, height: "100%", background: accent, borderRadius: 2 }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Ingestion Status */}
      <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, overflow: "hidden" }}>
        <div style={{ padding: "16px 20px", borderBottom: `1px solid ${t.border2}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>Policy Ingestion Status</span>
          <button onClick={() => onNavigate("library")} style={{ fontSize: 12, color: accent, background: "none", border: "none", cursor: "pointer", fontWeight: 500 }}>Manage library →</button>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)" }}>
          {POLICIES.slice(0, 4).map((p, i) => (
            <div key={p.id} style={{ padding: "14px 20px", borderRight: i < 3 ? `1px solid ${t.border2}` : "none" }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: t.text, marginBottom: 4 }}>
                {p.name.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
              </div>
              <div style={{ fontSize: 11, color: t.faint, marginBottom: 8 }}>{p.chunks} chunks</div>
              <Badge status={p.status} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
