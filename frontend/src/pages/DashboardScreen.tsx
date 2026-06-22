import { useTheme } from "@/lib/theme";
import { Badge } from "@/components/ui/Badge";


import { fetchWithAuth } from "@/lib/api";
import { useEffect, useState } from "react";

export function DashboardScreen({ forceLogout }: { forceLogout: () => void }) {
  const { t, accent } = useTheme();

  const [stats, setStats] = useState({ total_queries: 0, total_documents: 0, active_users: 0, success_rate: 0 });
  const [topics, setTopics] = useState<any[]>([]);
  const [recentQueries, setRecentQueries] = useState<any[]>([]);
  const [documents, setDocuments] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      fetchWithAuth("/api/dashboard/stats", { method: "GET" }, forceLogout).then(res => res.json()),
      fetchWithAuth("/api/dashboard/topics", { method: "GET" }, forceLogout).then(res => res.json()),
      fetchWithAuth("/api/dashboard/recent-queries", { method: "GET" }, forceLogout).then(res => res.json()),
      fetchWithAuth("/api/dashboard/documents", { method: "GET" }, forceLogout).then(res => res.json())
    ]).then(([statsData, topicsData, queriesData, docsData]) => {
      setStats(statsData || { total_queries: 0, total_documents: 0, active_users: 0, success_rate: 0 });
      setTopics(topicsData || []);
      setRecentQueries(queriesData || []);
      setDocuments(docsData || []);
    }).catch(console.error);
  }, []);

  const kpis = [
    { label: "Total Policies",    value: String(stats.total_documents),          sub: "Indexed documents" },
    { label: "Queries Processed", value: String(stats.total_queries),            sub: `${stats.active_users} active users` },
    { label: "Success Rate",      value: `${stats.success_rate}%`,               sub: "Successful queries" },
    { label: "System Status",     value: stats.success_rate > 90 ? "Healthy" : "Degraded", sub: "Based on success rate" },
  ];

  return (
    <div style={{ padding: "32px 36px", maxWidth: 1100, margin: "0 auto", overflowY: "auto", height: "100%" }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: t.text, margin: 0 }}>Dashboard</h1>
        <p style={{ fontSize: 13, color: t.muted, marginTop: 4 }}>System overview</p>
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
          </div>
          {recentQueries.map((a, i) => (
            <div key={i} style={{ padding: "12px 20px", borderBottom: i < recentQueries.length - 1 ? `1px solid ${t.border2}` : "none", display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ fontSize: 11, color: t.faint, fontFamily: "monospace", minWidth: 40 }}>
                {a.timestamp ? new Date(a.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
              </span>
              <span style={{ fontSize: 13, color: t.text2, flex: 1 }}>{a.query}</span>
              <Badge status={a.status === "success" ? "Answered" : a.status === "error" ? "Insufficient" : "Processing"} />
            </div>
          ))}
          {recentQueries.length === 0 && <div style={{ padding: "16px 20px", fontSize: 13, color: t.muted }}>No queries yet</div>}
        </div>

        {/* Top Topics */}
        <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, overflow: "hidden" }}>
          <div style={{ padding: "16px 20px", borderBottom: `1px solid ${t.border2}` }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>Top Queried Topics</span>
          </div>
          {topics.map((tp, i) => (
            <div key={i} style={{ padding: "12px 20px", borderBottom: i < topics.length - 1 ? `1px solid ${t.border2}` : "none" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 13, color: t.text2 }}>{tp.name}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: t.muted }}>{tp.value}</span>
              </div>
              <div style={{ height: 4, background: t.border, borderRadius: 2, overflow: "hidden" }}>
                <div style={{ width: `${(tp.value / (topics[0]?.value || 1)) * 100}%`, height: "100%", background: accent, borderRadius: 2 }} />
              </div>
            </div>
          ))}
          {topics.length === 0 && <div style={{ padding: "16px 20px", fontSize: 13, color: t.muted }}>No topic data</div>}
        </div>
      </div>

      {/* Ingestion Status */}
      <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, overflow: "hidden" }}>
        <div style={{ padding: "16px 20px", borderBottom: `1px solid ${t.border2}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>Policy Ingestion Status</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}>
          {documents.slice(0, 4).map((p, i) => (
            <div key={p.id} style={{ padding: "14px 20px", borderRight: i < Math.min(3, documents.length - 1) ? `1px solid ${t.border2}` : "none" }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: t.text, marginBottom: 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {p.title.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
              </div>
              <div style={{ fontSize: 11, color: t.faint, marginBottom: 8 }}>{p.chunks} chunks</div>
              <Badge status={p.status === "completed" ? "Up to date" : p.status === "processing" ? "Indexing" : "Error"} />
            </div>
          ))}
          {documents.length === 0 && <div style={{ padding: "16px 20px", fontSize: 13, color: t.muted, gridColumn: "1 / -1" }}>No documents indexed</div>}
        </div>
      </div>
    </div>
  );
}
