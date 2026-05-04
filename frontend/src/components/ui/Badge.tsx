import { useTheme } from "@/lib/theme";

type BadgeStatus = "indexed" | "processing" | "failed" | "answered" | "insufficient" | "helpful" | "not-helpful";

const STATUS_MAP: Record<BadgeStatus, { bg: string; color: string; dbg: string; dc: string; label: string }> = {
  indexed:       { bg: "#D1FAE5", color: "#065F46", dbg: "#064E3B", dc: "#6EE7B7", label: "Indexed" },
  processing:    { bg: "#FEF3C7", color: "#92400E", dbg: "#451A03", dc: "#FCD34D", label: "Processing" },
  failed:        { bg: "#FEE2E2", color: "#991B1B", dbg: "#450A0A", dc: "#FCA5A5", label: "Failed" },
  answered:      { bg: "#D1FAE5", color: "#065F46", dbg: "#064E3B", dc: "#6EE7B7", label: "Answered" },
  insufficient:  { bg: "#FEE2E2", color: "#991B1B", dbg: "#450A0A", dc: "#FCA5A5", label: "Insufficient" },
  helpful:       { bg: "#DBEAFE", color: "#1E40AF", dbg: "#1E3A8A", dc: "#93C5FD", label: "Helpful" },
  "not-helpful": { bg: "#FEE2E2", color: "#991B1B", dbg: "#450A0A", dc: "#FCA5A5", label: "Not Helpful" },
};

export function Badge({ status }: { status: string }) {
  const { isDark } = useTheme();
  const s = STATUS_MAP[status as BadgeStatus] ?? { bg: "#F3F4F6", color: "#374151", dbg: "#1F2937", dc: "#9CA3AF", label: status };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center",
      padding: "2px 8px", borderRadius: 4,
      fontSize: 11, fontWeight: 600, letterSpacing: "0.03em",
      background: isDark ? s.dbg : s.bg,
      color: isDark ? s.dc : s.color,
    }}>
      {s.label}
    </span>
  );
}
