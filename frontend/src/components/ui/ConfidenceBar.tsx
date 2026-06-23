export function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const colorClass = score >= 0.8 ? "bg-emerald-500" : score >= 0.5 ? "bg-amber-500" : "bg-red-500";
  const textClass = score >= 0.8 ? "text-emerald-600 dark:text-emerald-500" : score >= 0.5 ? "text-amber-600 dark:text-amber-500" : "text-red-600 dark:text-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 bg-border rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-[11px] font-semibold min-w-[28px] ${textClass}`}>{pct}%</span>
    </div>
  );
}
