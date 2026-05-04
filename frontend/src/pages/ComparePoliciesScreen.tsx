import { useState } from "react";
import { useTheme } from "@/lib/theme";
import { POLICIES, COMPARE_TOPICS, COMPARE_RESULTS } from "@/lib/mockData";

export function ComparePoliciesScreen() {
  const { t, accent } = useTheme();
  const [policyA, setPolicyA] = useState("Google Privacy Policy");
  const [policyB, setPolicyB] = useState("OpenAI Privacy Policy");
  const [topic, setTopic] = useState("Data Retention");
  const [compared, setCompared] = useState(true);
  const [loading, setLoading] = useState(false);

  const indexedPolicies = POLICIES.filter((p) => p.status === "indexed").map((p) => p.name);
  const result = COMPARE_RESULTS[topic] ?? COMPARE_RESULTS["Data Retention"];

  const runCompare = () => {
    setLoading(true);
    setCompared(false);
    setTimeout(() => { setCompared(true); setLoading(false); }, 900);
  };

  const selStyle: React.CSSProperties = {
    padding: "8px 12px", border: `1px solid ${t.border}`, borderRadius: 6,
    fontSize: 13, color: t.text, background: t.surface2, outline: "none",
    minWidth: 220, fontFamily: "inherit",
  };

  const shortName = (n: string) => n.replace(" Privacy Policy", "").replace(" Privacy Statement", "");

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Controls */}
      <div style={{ padding: "20px 28px", borderBottom: `1px solid ${t.border}`, background: t.surface, flexShrink: 0 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: t.text, margin: "0 0 16px" }}>Compare Policies</h1>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: t.muted, textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>Policy A</label>
            <select value={policyA} onChange={(e) => setPolicyA(e.target.value)} style={selStyle}>
              {indexedPolicies.map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div style={{ fontSize: 18, color: t.faint, paddingBottom: 8 }}>⇔</div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: t.muted, textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>Policy B</label>
            <select value={policyB} onChange={(e) => setPolicyB(e.target.value)} style={selStyle}>
              {indexedPolicies.map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: t.muted, textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>Topic</label>
            <select value={topic} onChange={(e) => setTopic(e.target.value)} style={{ ...selStyle, minWidth: 180 }}>
              {COMPARE_TOPICS.map((tp) => <option key={tp}>{tp}</option>)}
            </select>
          </div>
          <button
            onClick={runCompare}
            style={{ padding: "9px 24px", background: accent, color: "#fff", border: "none", borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: "pointer" }}
          >
            Compare
          </button>
        </div>
      </div>

      {/* Results */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px", background: t.bg }}>
        {loading && (
          <div style={{ textAlign: "center", padding: 60, color: t.faint, fontSize: 13 }}>Comparing policies…</div>
        )}
        {compared && !loading && (
          <>
            {/* Side-by-side summaries */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
              {[
                { label: shortName(policyA), data: result.policyA, isA: true },
                { label: shortName(policyB), data: result.policyB, isA: false },
              ].map((col, i) => (
                <div key={i} style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, overflow: "hidden" }}>
                  <div style={{ padding: "12px 18px", background: i === 0 ? t.userBubble : accent, color: i === 0 ? t.userBubbleText : "#fff" }}>
                    <span style={{ fontSize: 13, fontWeight: 700 }}>{col.label}</span>
                    <span style={{ fontSize: 11, opacity: 0.7, marginLeft: 8 }}>· {topic}</span>
                  </div>
                  <div style={{ padding: "16px 18px" }}>
                    <p style={{ fontSize: 13, color: t.text2, lineHeight: 1.65, margin: "0 0 14px" }}>{col.data.summary}</p>
                    <div style={{ fontSize: 11, fontWeight: 600, color: t.faint, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>Sources</div>
                    {col.data.citations.map((c, j) => (
                      <div key={j} style={{ fontSize: 11, color: accent, padding: "4px 8px", background: `${accent}18`, borderRadius: 4, marginBottom: 4 }}>↗ {c}</div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Key Differences */}
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, overflow: "hidden" }}>
              <div style={{ padding: "12px 18px", borderBottom: `1px solid ${t.border2}`, display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>Key Differences</span>
                <span style={{ fontSize: 11, padding: "2px 8px", background: "#FEF9C3", color: "#92400E", borderRadius: 4, fontWeight: 600 }}>{result.differences.length} identified</span>
              </div>
              {result.differences.map((d, i) => (
                <div key={i} style={{ padding: "12px 18px", borderBottom: i < result.differences.length - 1 ? `1px solid ${t.border2}` : "none", display: "flex", gap: 12 }}>
                  <span style={{ fontSize: 12, color: "#F59E0B", fontWeight: 700, marginTop: 1, flexShrink: 0 }}>△</span>
                  <p style={{ fontSize: 13, color: t.text3, lineHeight: 1.6, margin: 0 }}>{d}</p>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
