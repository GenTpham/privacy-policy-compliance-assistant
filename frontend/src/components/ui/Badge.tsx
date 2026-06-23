type BadgeStatus = "indexed" | "success" | "processing" | "extracting_text" | "chunking_text" | "embedding_and_saving" | "failed" | "answered" | "insufficient" | "helpful" | "not-helpful";

const STATUS_MAP: Record<BadgeStatus, { className: string; label: string }> = {
  indexed:       { className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400", label: "Indexed" },
  success:       { className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400", label: "Indexed" },
  processing:    { className: "bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-400", label: "Processing" },
  extracting_text: { className: "bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-400", label: "Extracting" },
  chunking_text: { className: "bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-400", label: "Chunking" },
  embedding_and_saving: { className: "bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-400", label: "Embedding" },
  failed:        { className: "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-400", label: "Failed" },
  answered:      { className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400", label: "Answered" },
  insufficient:  { className: "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-400", label: "Insufficient" },
  helpful:       { className: "bg-blue-100 text-blue-800 dark:bg-blue-950/50 dark:text-blue-400", label: "Helpful" },
  "not-helpful": { className: "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-400", label: "Not Helpful" },
};

export function Badge({ status }: { status: string }) {
  const s = STATUS_MAP[status as BadgeStatus] ?? { className: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300", label: status };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold tracking-wide ${s.className}`}>
      {s.label}
    </span>
  );
}
