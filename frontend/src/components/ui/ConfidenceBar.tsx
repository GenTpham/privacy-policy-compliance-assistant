import { useTheme } from "@/lib/theme";

export function ConfidenceBar({ score }: { score: number }) {
  const { t } = useTheme();
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? "#22C55E" : score >= 0.5 ? "#F59E0B" : "#EF4444";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 4, background: t.border, borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: 11, color, fontWeight: 600, minWidth: 28 }}>{pct}%</span>
    </div>
  );
}
