import { useState } from "react";
import { useTheme } from "@/lib/theme";
import { Badge } from "@/components/ui/Badge";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import { AUDIT_ENTRIES, type AuditEntry } from "@/lib/mockData";

export function AuditLogScreen() {
  const { t, accent } = useTheme();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<AuditEntry | null>(null);

  const filtered = AUDIT_ENTRIES.filter(
    (e) =>
      e.query.toLowerCase().includes(search.toLowerCase()) ||
      e.policies.some((p) => p.toLowerCase().includes(search.toLowerCase()))
  );

  const shortPolicy = (n: string) => n.replace(" Privacy Policy", "").replace(" Privacy Statement", "");

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header */}
        <div style={{ padding: "24px 28px 16px", borderBottom: `1px solid ${t.border}`, display: "flex", justifyContent: "space-between", alignItems: "center", background: t.surface }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: t.text, margin: 0 }}>Audit Log</h1>
            <p style={{ fontSize: 12, color: t.muted, margin: "3px 0 0" }}>{filtered.length} entries · sorted by most recent</p>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search queries…"
              style={{ padding: "7px 12px", fontSize: 12, border: `1px solid ${t.border}`, borderRadius: 6, outline: "none", width: 200, background: t.surface2, color: t.text }}
            />
            <button style={{ fontSize: 12, padding: "7px 14px", border: `1px solid ${t.border}`, borderRadius: 6, background: t.surface, color: t.text3, cursor: "pointer" }}>Export CSV</button>
          </div>
        </div>

        {/* Table */}
        <div style={{ flex: 1, overflowY: "auto", background: t.bg }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: t.surface2, borderBottom: `1px solid ${t.border}` }}>
                {["Timestamp", "Query", "Policy", "Chunks", "Confidence", "Status", "Feedback"].map((h) => (
                  <th key={h} style={{ padding: "10px 18px", textAlign: "left", fontSize: 11, fontWeight: 600, color: t.muted, letterSpacing: "0.04em", textTransform: "uppercase", whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((e, i) => (
                <tr
                  key={e.id}
                  onClick={() => setSelected(e)}
                  style={{
                    borderBottom: `1px solid ${t.border2}`,
                    cursor: "pointer",
                    background: selected?.id === e.id ? `${accent}11` : i % 2 === 0 ? t.surface : t.surface2,
                  }}
                >
                  <td style={{ padding: "11px 18px", fontSize: 11, color: t.muted, fontFamily: "monospace", whiteSpace: "nowrap" }}>{e.timestamp}</td>
                  <td style={{ padding: "11px 18px", fontSize: 13, color: t.text2, maxWidth: 300 }}>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.query}</div>
                    <div style={{ fontSize: 11, color: t.faint }}>{e.user}</div>
                  </td>
                  <td style={{ padding: "11px 18px", fontSize: 12, color: t.text3 }}>
                    {e.policies.map((p) => (
                      <div key={p} style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 160 }}>{shortPolicy(p)}</div>
                    ))}
                  </td>
                  <td style={{ padding: "11px 18px", fontSize: 13, color: t.text3, textAlign: "center" }}>{e.chunksRetrieved}</td>
                  <td style={{ padding: "11px 18px", minWidth: 120 }}><ConfidenceBar score={e.confidence} /></td>
                  <td style={{ padding: "11px 18px" }}><Badge status={e.status} /></td>
                  <td style={{ padding: "11px 18px" }}>
                    {e.feedback ? <Badge status={e.feedback} /> : <span style={{ fontSize: 11, color: t.faintest }}>—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail panel */}
      {selected && (
        <div style={{ width: 320, borderLeft: `1px solid ${t.border}`, background: t.surface, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "16px 20px", borderBottom: `1px solid ${t.border2}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>Query Detail</span>
            <button onClick={() => setSelected(null)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16, color: t.faint }}>✕</button>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
            <div style={{ fontSize: 11, color: t.faint, fontFamily: "monospace", marginBottom: 12 }}>{selected.timestamp}</div>
            <div style={{ fontSize: 13, color: t.text, fontWeight: 600, lineHeight: 1.5, marginBottom: 16, padding: "10px 12px", background: t.surface2, borderRadius: 6, borderLeft: `3px solid ${accent}` }}>
              {selected.query}
            </div>
            {[
              { label: "User",              val: selected.user },
              { label: "Chunks Retrieved",  val: String(selected.chunksRetrieved) },
              { label: "Status",            val: <Badge status={selected.status} /> },
              { label: "User Feedback",     val: selected.feedback ? <Badge status={selected.feedback} /> : "None" },
            ].map((r) => (
              <div key={r.label} style={{ display: "flex", justifyContent: "space-between", padding: "9px 0", borderBottom: `1px solid ${t.border2}`, alignItems: "center" }}>
                <span style={{ fontSize: 12, color: t.muted }}>{r.label}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: t.text2 }}>{r.val}</span>
              </div>
            ))}
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: t.muted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>Policies Accessed</div>
              {selected.policies.map((p) => (
                <div key={p} style={{ fontSize: 12, color: accent, padding: "6px 10px", background: `${accent}18`, borderRadius: 4, marginBottom: 4 }}>{p}</div>
              ))}
            </div>
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: t.muted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>Confidence Score</div>
              <ConfidenceBar score={selected.confidence} />
            </div>
            <button style={{ marginTop: 20, width: "100%", padding: 9, background: "transparent", color: t.text3, border: `1px solid ${t.border}`, borderRadius: 6, fontSize: 12, cursor: "pointer" }}>
              Download Evidence Bundle
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
