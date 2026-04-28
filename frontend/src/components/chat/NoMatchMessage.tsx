import { AlertCircle } from "lucide-react";

/**
 * Rendered when done event returns citations: [] (no chunks passed threshold).
 * Copy from UI-SPEC.md Copywriting Contract and No Matching Policy Found section.
 */
export function NoMatchMessage() {
  return (
    <div
      className="flex items-start gap-3 bg-white border border-zinc-200 rounded-lg px-4 py-3 max-w-[80%]"
      role="status"
      aria-live="polite"
    >
      {/* AlertCircle in text-amber-500 per UI-SPEC */}
      <AlertCircle
        className="h-5 w-5 text-amber-500 shrink-0 mt-0.5"
        aria-hidden="true"
      />
      <div>
        <p className="font-medium text-zinc-950">No matching policy found</p>
        <p className="text-sm text-zinc-600 mt-1">
          The query did not match any passages in the indexed policy corpus. Try
          rephrasing your question or using different terms.
        </p>
      </div>
    </div>
  );
}
