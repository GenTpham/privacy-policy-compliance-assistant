import { Badge } from "@/components/ui/Badge";
import { fetchWithAuth } from "@/lib/api";
import { useEffect, useState } from "react";

interface Stats {
  total_queries: number;
  total_documents: number;
  active_users: number;
  success_rate: number;
}

export function DashboardScreen({ forceLogout }: { forceLogout: () => void }) {
  const [stats, setStats] = useState<Stats>({ total_queries: 0, total_documents: 0, active_users: 0, success_rate: 0 });
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
  }, [forceLogout]);

  const kpis = [
    { label: "Total Policies",    value: String(stats.total_documents),          sub: "Indexed documents" },
    { label: "Queries Processed", value: String(stats.total_queries),            sub: `${stats.active_users} active users` },
    { label: "Success Rate",      value: `${stats.success_rate}%`,               sub: "Successful queries" },
    { label: "System Status",     value: stats.success_rate > 90 ? "Healthy" : "Degraded", sub: "Based on success rate" },
  ];

  return (
    <div className="py-10 px-8 max-w-[1100px] mx-auto overflow-y-auto h-full">
      {/* Header */}
      <header className="mb-12 animate-stagger" style={{ "--idx": 0 } as React.CSSProperties}>
        <h1 className="text-4xl font-bold text-text-1 tracking-tighter mb-2">Dashboard</h1>
        <p className="text-[15px] text-muted font-medium">System overview</p>
      </header>

      {/* KPI Cards */}
      <dl className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10" aria-label="Key Performance Indicators">
        {kpis.map((k, i) => (
          <div key={i} className="bg-surface border border-border rounded-[2rem] p-8 shadow-[var(--shadow-diffusion)] animate-stagger flex flex-col justify-center" style={{ "--idx": i + 1 } as React.CSSProperties}>
            <dt className="text-[12px] font-semibold text-faint tracking-widest uppercase mb-4">{k.label}</dt>
            <dd className="text-4xl font-mono font-bold text-text-1 mb-2 tracking-tighter m-0">{k.value}</dd>
            <dd className="text-[13px] text-muted font-medium m-0">{k.sub}</dd>
          </div>
        ))}
      </dl>

      {/* Recent Queries + Top Topics */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-8 mb-8">
        {/* Recent Queries */}
        <section className="bg-surface border border-border rounded-[2rem] overflow-hidden shadow-[var(--shadow-diffusion)] flex flex-col animate-stagger" style={{ "--idx": 5 } as React.CSSProperties}>
          <header className="px-6 py-5 border-b border-border-2 flex justify-between items-center bg-surface-2/30">
            <h2 className="text-[14px] font-semibold text-text-1 m-0">Recent Queries</h2>
          </header>
          <ul className="flex-1 overflow-y-auto list-none m-0 p-0">
            {recentQueries.map((a, i) => (
              <li key={i} className={`px-6 py-4 flex items-center gap-4 transition-colors hover:bg-surface-2/50 ${i < recentQueries.length - 1 ? "border-b border-border-2/50" : ""}`}>
                <time className="text-[11px] text-faint font-mono font-medium min-w-[44px]" dateTime={a.timestamp}>
                  {a.timestamp ? new Date(a.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                </time>
                <span className="text-[13px] text-text-2 flex-1 font-medium">{a.query}</span>
                <Badge status={a.status === "success" ? "Answered" : a.status === "error" ? "Insufficient" : "Processing"} />
              </li>
            ))}
            {recentQueries.length === 0 && <li className="px-6 py-8 text-[13px] text-muted text-center">No queries yet</li>}
          </ul>
        </section>

        {/* Top Topics */}
        <section className="bg-surface border border-border rounded-[2rem] overflow-hidden shadow-[var(--shadow-diffusion)] flex flex-col animate-stagger" style={{ "--idx": 6 } as React.CSSProperties}>
          <header className="px-6 py-5 border-b border-border-2 bg-surface-2/30">
            <h2 className="text-[14px] font-semibold text-text-1 m-0">Top Queried Topics</h2>
          </header>
          <ul className="flex-1 overflow-y-auto list-none m-0 p-0">
            {topics.map((tp, i) => {
              const percentage = (tp.value / (topics[0]?.value || 1)) * 100;
              return (
                <li key={i} className={`px-6 py-4 transition-colors hover:bg-surface-2/50 ${i < topics.length - 1 ? "border-b border-border-2/50" : ""}`}>
                  <div className="flex justify-between mb-2">
                    <span className="text-[13px] text-text-2 font-medium">{tp.name}</span>
                    <span className="text-[12px] font-semibold text-muted" aria-hidden="true">{tp.value}</span>
                  </div>
                  <div 
                    className="h-1.5 bg-border rounded-full overflow-hidden" 
                    role="progressbar" 
                    aria-label={`${tp.name} queries`} 
                    aria-valuenow={tp.value} 
                    aria-valuemin={0} 
                    aria-valuemax={topics[0]?.value || 100}
                  >
                    <div className="h-full bg-accent rounded-full" style={{ width: `${percentage}%` }} />
                  </div>
                </li>
              );
            })}
            {topics.length === 0 && <li className="px-6 py-8 text-[13px] text-muted text-center">No topic data</li>}
          </ul>
        </section>
      </div>

      {/* Ingestion Status */}
      <section className="bg-surface border border-border rounded-[2rem] overflow-hidden shadow-[var(--shadow-diffusion)] animate-stagger" style={{ "--idx": 7 } as React.CSSProperties}>
        <header className="px-6 py-5 border-b border-border-2 flex justify-between items-center bg-surface-2/30">
          <h2 className="text-[14px] font-semibold text-text-1 m-0">Policy Ingestion Status</h2>
        </header>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4">
          {documents.slice(0, 4).map((p, i) => (
            <article key={p.id} className={`p-5 hover:bg-surface-2/50 transition-colors ${i < Math.min(3, documents.length - 1) ? "md:border-r border-border-2/50" : ""} ${i > 0 ? "border-t md:border-t-0 border-border-2/50" : ""}`}>
              <h3 className="text-[13px] font-semibold text-text-1 mb-1 whitespace-nowrap overflow-hidden text-ellipsis m-0">
                {p.title.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
              </h3>
              <div className="text-[11px] text-faint mb-3 font-medium">{p.chunk_count || 0} chunks</div>
              <Badge status={p.status} />
            </article>
          ))}
          {documents.length === 0 && <div className="p-6 text-[13px] text-muted col-span-full text-center">No documents indexed</div>}
        </div>
      </section>
    </div>
  );
}
