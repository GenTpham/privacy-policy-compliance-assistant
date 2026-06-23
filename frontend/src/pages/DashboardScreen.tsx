import { Badge } from "@/components/ui/Badge";


import { fetchWithAuth } from "@/lib/api";
import { useEffect, useState } from "react";

export function DashboardScreen({ forceLogout }: { forceLogout: () => void }) {

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
    <div className="py-10 px-8 max-w-[1100px] mx-auto overflow-y-auto h-full">
      {/* Header */}
      <div className="mb-12 animate-stagger" style={{ "--idx": 0 } as React.CSSProperties}>
        <h1 className="text-4xl font-bold text-text-1 tracking-tighter mb-2">Dashboard</h1>
        <p className="text-[15px] text-muted font-medium">System overview</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-6 mb-10">
        {kpis.map((k, i) => (
          <div key={i} className="bg-surface border border-border rounded-[2rem] p-8 shadow-[var(--shadow-diffusion)] animate-stagger flex flex-col justify-center" style={{ "--idx": i + 1 } as React.CSSProperties}>
            <div className="text-[12px] font-semibold text-faint tracking-widest uppercase mb-4">{k.label}</div>
            <div className="text-4xl font-mono font-bold text-text-1 mb-2 tracking-tighter">{k.value}</div>
            <div className="text-[13px] text-muted font-medium">{k.sub}</div>
          </div>
        ))}
      </div>

      {/* Recent Queries + Top Topics */}
      <div className="grid grid-cols-[1fr_360px] gap-8 mb-8">
        {/* Recent Queries */}
        <div className="bg-surface border border-border rounded-[2rem] overflow-hidden shadow-[var(--shadow-diffusion)] flex flex-col animate-stagger" style={{ "--idx": 5 } as React.CSSProperties}>
          <div className="px-6 py-5 border-b border-border-2 flex justify-between items-center bg-surface-2/30">
            <span className="text-[14px] font-semibold text-text-1">Recent Queries</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {recentQueries.map((a, i) => (
              <div key={i} className={`px-6 py-4 flex items-center gap-4 transition-colors hover:bg-surface-2/50 ${i < recentQueries.length - 1 ? "border-b border-border-2/50" : ""}`}>
                <span className="text-[11px] text-faint font-mono font-medium min-w-[44px]">
                  {a.timestamp ? new Date(a.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                </span>
                <span className="text-[13px] text-text-2 flex-1 font-medium">{a.query}</span>
                <Badge status={a.status === "success" ? "Answered" : a.status === "error" ? "Insufficient" : "Processing"} />
              </div>
            ))}
            {recentQueries.length === 0 && <div className="px-6 py-8 text-[13px] text-muted text-center">No queries yet</div>}
          </div>
        </div>

        {/* Top Topics */}
        <div className="bg-surface border border-border rounded-[2rem] overflow-hidden shadow-[var(--shadow-diffusion)] flex flex-col animate-stagger" style={{ "--idx": 6 } as React.CSSProperties}>
          <div className="px-6 py-5 border-b border-border-2 bg-surface-2/30">
            <span className="text-[14px] font-semibold text-text-1">Top Queried Topics</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {topics.map((tp, i) => (
              <div key={i} className={`px-6 py-4 transition-colors hover:bg-surface-2/50 ${i < topics.length - 1 ? "border-b border-border-2/50" : ""}`}>
                <div className="flex justify-between mb-2">
                  <span className="text-[13px] text-text-2 font-medium">{tp.name}</span>
                  <span className="text-[12px] font-semibold text-muted">{tp.value}</span>
                </div>
                <div className="h-1.5 bg-border rounded-full overflow-hidden">
                  <div className="h-full bg-accent rounded-full" style={{ width: `${(tp.value / (topics[0]?.value || 1)) * 100}%` }} />
                </div>
              </div>
            ))}
            {topics.length === 0 && <div className="px-6 py-8 text-[13px] text-muted text-center">No topic data</div>}
          </div>
        </div>
      </div>

      {/* Ingestion Status */}
      <div className="bg-surface border border-border rounded-[2rem] overflow-hidden shadow-[var(--shadow-diffusion)] animate-stagger" style={{ "--idx": 7 } as React.CSSProperties}>
        <div className="px-6 py-5 border-b border-border-2 flex justify-between items-center bg-surface-2/30">
          <span className="text-[14px] font-semibold text-text-1">Policy Ingestion Status</span>
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))]">
          {documents.slice(0, 4).map((p, i) => (
            <div key={p.id} className={`p-5 hover:bg-surface-2/50 transition-colors ${i < Math.min(3, documents.length - 1) ? "border-r border-border-2/50" : ""}`}>
              <div className="text-[13px] font-semibold text-text-1 mb-1 whitespace-nowrap overflow-hidden text-ellipsis">
                {p.title.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
              </div>
              <div className="text-[11px] text-faint mb-3 font-medium">{p.chunk_count || 0} chunks</div>
              <Badge status={p.status} />
            </div>
          ))}
          {documents.length === 0 && <div className="p-6 text-[13px] text-muted col-span-full text-center">No documents indexed</div>}
        </div>
      </div>
    </div>
  );
}
