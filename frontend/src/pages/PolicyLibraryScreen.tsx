import { useState } from "react";
import { useTheme } from "@/lib/theme";
import { Badge } from "@/components/ui/Badge";
import { POLICIES, POLICY_SECTIONS } from "@/lib/mockData";
import type { Policy } from "@/lib/mockData";

export function PolicyLibraryScreen({ onAsk }: { onAsk?: (policyName: string) => void }) {
  const { t, accent } = useTheme();
  const [selected, setSelected] = useState<Policy | null>(null);
  const [search, setSearch] = useState("");

  const filtered = POLICIES.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.vendor.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      {/* Table area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header */}
        <div style={{ padding: "24px 28px 16px", borderBottom: `1px solid ${t.border}`, display: "flex", justifyContent: "space-between", alignItems: "center", background: t.surface }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: t.text, margin: 0 }}>Policy Library</h1>
            <p style={{ fontSize: 12, color: t.muted, margin: "3px 0 0" }}>
              {POLICIES.length} documents · {POLICIES.filter((p) => p.status === "indexed").length} indexed
            </p>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search policies…"
              style={{ padding: "7px 12px", fontSize: 12, border: `1px solid ${t.border}`, borderRadius: 6, outline: "none", width: 220, background: t.surface2, color: t.text }}
            />
            <button style={{ background: accent, color: "#fff", border: "none", borderRadius: 6, padding: "8px 16px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
              + Add Policy
            </button>
          </div>
        </div>

        {/* Table */}
        <div style={{ flex: 1, overflowY: "auto", background: t.bg }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: t.surface2, borderBottom: `1px solid ${t.border}` }}>
                {["Policy Name", "Vendor", "Effective Date", "Chunks", "Status", "Tags"].map((h) => (
                  <th key={h} style={{ padding: "10px 20px", textAlign: "left", fontSize: 11, fontWeight: 600, color: t.muted, letterSpacing: "0.04em", textTransform: "uppercase", whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((p, i) => (
                <tr
                  key={p.id}
                  onClick={() => setSelected(p)}
                  style={{
                    borderBottom: `1px solid ${t.border2}`,
                    cursor: "pointer",
                    background: selected?.id === p.id ? `${accent}11` : i % 2 === 0 ? t.surface : t.surface2,
                  }}
                >
                  <td style={{ padding: "12px 20px" }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: t.text }}>{p.name}</div>
                    <div style={{ fontSize: 11, color: t.faint }}>{p.version}</div>
                  </td>
                  <td style={{ padding: "12px 20px", fontSize: 13, color: t.text3 }}>{p.vendor}</td>
                  <td style={{ padding: "12px 20px", fontSize: 12, color: t.muted, fontFamily: "monospace" }}>{p.effectiveDate}</td>
                  <td style={{ padding: "12px 20px", fontSize: 13, color: t.text3, fontWeight: 500 }}>{p.chunks.toLocaleString()}</td>
                  <td style={{ padding: "12px 20px" }}><Badge status={p.status} /></td>
                  <td style={{ padding: "12px 20px" }}>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {p.tags.slice(0, 2).map((tg) => (
                        <span key={tg} style={{ fontSize: 10, padding: "2px 6px", background: `${accent}22`, color: accent, borderRadius: 3, fontWeight: 500 }}>{tg}</span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail drawer */}
      {selected && (
        <div style={{ width: 340, borderLeft: `1px solid ${t.border}`, background: t.surface, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "16px 20px", borderBottom: `1px solid ${t.border2}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>Policy Details</span>
            <button onClick={() => setSelected(null)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16, color: t.faint }}>✕</button>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: t.text, margin: "0 0 4px" }}>{selected.name}</h2>
            <p style={{ fontSize: 12, color: t.muted, margin: "0 0 20px" }}>{selected.vendor}</p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
              {[
                { label: "Version",  val: selected.version },
                { label: "Effective", val: selected.effectiveDate },
                { label: "Chunks",   val: String(selected.chunks) },
                { label: "Status",   val: <Badge status={selected.status} /> },
              ].map((r) => (
                <div key={r.label} style={{ background: t.surface2, borderRadius: 6, padding: "10px 12px" }}>
                  <div style={{ fontSize: 10, color: t.faint, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>{r.label}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: t.text2 }}>{r.val}</div>
                </div>
              ))}
            </div>
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: t.muted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>Topics / Tags</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {selected.tags.map((tg) => (
                  <span key={tg} style={{ fontSize: 11, padding: "4px 10px", background: `${accent}22`, color: accent, borderRadius: 4, fontWeight: 500 }}>{tg}</span>
                ))}
              </div>
            </div>
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: t.muted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>Section Tree</div>
              {POLICY_SECTIONS.map((s, i) => (
                <div key={i} style={{ fontSize: 12, color: t.text3, padding: "6px 10px", borderLeft: `2px solid ${t.border}`, marginBottom: 3, cursor: "pointer" }}>{s}</div>
              ))}
            </div>
            <button
              onClick={() => onAsk?.(selected.name)}
              style={{ width: "100%", padding: 10, background: accent, color: "#fff", border: "none", borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: "pointer", marginBottom: 8 }}
            >
              Ask questions about this policy
            </button>
            <button style={{ width: "100%", padding: 10, background: "transparent", color: t.text3, border: `1px solid ${t.border}`, borderRadius: 6, fontSize: 13, cursor: "pointer" }}>
              Re-index document
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
