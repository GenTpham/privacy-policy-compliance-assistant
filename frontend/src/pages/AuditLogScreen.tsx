import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import { AUDIT_ENTRIES, type AuditEntry } from "@/lib/mockData";

export function AuditLogScreen() {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<AuditEntry | null>(null);

  const filtered = AUDIT_ENTRIES.filter(
    (e) =>
      e.query.toLowerCase().includes(search.toLowerCase()) ||
      e.policies.some((p) => p.toLowerCase().includes(search.toLowerCase()))
  );

  const shortPolicy = (n: string) => n.replace(" Privacy Policy", "").replace(" Privacy Statement", "");

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden bg-background">
        {/* Header */}
        <div className="px-8 py-6 border-b border-border bg-surface flex justify-between items-center z-10 shadow-sm">
          <div>
            <h1 className="text-2xl font-bold text-text-1 tracking-tight m-0">Audit Log</h1>
            <p className="text-xs text-muted font-medium mt-1">{filtered.length} entries · sorted by most recent</p>
          </div>
          <div className="flex gap-3">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search queries…"
              className="px-3.5 py-2 text-[13px] border border-border rounded-lg outline-none w-[240px] bg-surface-2 text-text-1 focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all placeholder:text-faint shadow-sm"
            />
            <button className="px-4 py-2 text-[13px] border border-border rounded-lg bg-surface text-text-2 font-semibold hover:bg-surface-2 hover:text-text-1 transition-colors shadow-sm cursor-pointer active:scale-95">
              Export CSV
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-y-auto">
          <table className="w-full border-collapse">
            <thead className="sticky top-0 z-10">
              <tr className="bg-surface-2/80 backdrop-blur-sm border-b border-border">
                {["Timestamp", "Query", "Policy", "Chunks", "Confidence", "Status", "Feedback"].map((h) => (
                  <th key={h} className="px-5 py-3.5 text-left text-[11px] font-semibold text-faint tracking-wider uppercase whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => {
                const isSelected = selected?.id === e.id;
                return (
                  <tr
                    key={e.id}
                    onClick={() => setSelected(e)}
                    className={`border-b border-border-2 cursor-pointer transition-colors ${
                      isSelected 
                        ? "bg-accent/10 hover:bg-accent/15" 
                        : "hover:bg-surface-2/50 bg-background"
                    }`}
                  >
                    <td className="px-5 py-3.5 text-[11px] text-muted font-mono whitespace-nowrap">{e.timestamp}</td>
                    <td className="px-5 py-3.5 text-[13px] text-text-2 max-w-[300px]">
                      <div className="truncate font-medium">{e.query}</div>
                      <div className="text-[11px] text-faint mt-0.5">{e.user}</div>
                    </td>
                    <td className="px-5 py-3.5 text-[12px] text-text-3">
                      <div className="flex flex-col gap-1">
                        {e.policies.map((p) => (
                          <div key={p} className="truncate max-w-[160px]">{shortPolicy(p)}</div>
                        ))}
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-[13px] text-text-3 text-center font-medium">{e.chunksRetrieved}</td>
                    <td className="px-5 py-3.5 min-w-[120px]"><div className="w-24"><ConfidenceBar score={e.confidence} /></div></td>
                    <td className="px-5 py-3.5"><Badge status={e.status} /></td>
                    <td className="px-5 py-3.5">
                      {e.feedback ? <Badge status={e.feedback} /> : <span className="text-[11px] text-faint">—</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div className="text-center py-16 text-[14px] text-muted font-medium">
              No audit logs found matching your search.
            </div>
          )}
        </div>
      </div>

      {/* Detail panel */}
      {selected && (
        <div className="w-[360px] border-l border-border bg-surface flex flex-col overflow-hidden shrink-0 shadow-[-8px_0_24px_-8px_rgba(0,0,0,0.1)] z-20">
          <div className="px-6 py-5 border-b border-border-2 flex justify-between items-center bg-surface-2/30">
            <span className="text-[14px] font-bold text-text-1 tracking-wide">Query Detail</span>
            <button 
              onClick={() => setSelected(null)} 
              className="bg-transparent border-none cursor-pointer text-lg text-faint hover:text-text-1 transition-colors w-7 h-7 flex items-center justify-center rounded-md hover:bg-border"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-6">
            <div className="text-[11px] text-faint font-mono mb-3">{selected.timestamp}</div>
            <div className="text-[13.5px] text-text-1 font-semibold leading-relaxed mb-6 px-4 py-3 bg-surface-2 rounded-xl border-l-4 border-accent shadow-sm">
              {selected.query}
            </div>
            
            <div className="space-y-0.5 mb-6">
              {[
                { label: "User",              val: selected.user },
                { label: "Chunks Retrieved",  val: String(selected.chunksRetrieved) },
                { label: "Status",            val: <Badge status={selected.status} /> },
                { label: "User Feedback",     val: selected.feedback ? <Badge status={selected.feedback} /> : "None" },
              ].map((r) => (
                <div key={r.label} className="flex justify-between items-center py-2.5 border-b border-border-2 last:border-0">
                  <span className="text-[12px] text-muted">{r.label}</span>
                  <span className="text-[12px] font-bold text-text-2">{r.val}</span>
                </div>
              ))}
            </div>
            
            <div className="mb-6">
              <div className="text-[11px] font-bold text-muted uppercase tracking-wider mb-3">Policies Accessed</div>
              <div className="flex flex-col gap-1.5">
                {selected.policies.map((p) => (
                  <div key={p} className="text-[12px] text-accent font-medium px-3 py-2 bg-accent/10 rounded-md border border-accent/10">
                    {p}
                  </div>
                ))}
              </div>
            </div>
            
            <div className="mb-6">
              <div className="text-[11px] font-bold text-muted uppercase tracking-wider mb-3">Confidence Score</div>
              <div className="bg-surface-2 rounded-lg p-3">
                <ConfidenceBar score={selected.confidence} />
              </div>
            </div>
            
            <button className="w-full mt-2 py-2.5 bg-transparent text-text-3 border border-border rounded-lg text-[13px] font-medium cursor-pointer hover:bg-surface-2 hover:text-text-2 active:scale-95 transition-all shadow-sm">
              Download Evidence Bundle
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
