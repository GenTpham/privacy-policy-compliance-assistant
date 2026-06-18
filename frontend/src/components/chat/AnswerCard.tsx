import { useTheme } from "@/lib/theme";
import { parseCitations } from "@/lib/parseCitations";
import { InlineCitationBadge } from "./InlineCitationBadge";
import { CitationCard } from "./CitationCard";
import type { Citation } from "@/hooks/useSSEChat";

export interface AnswerCardProps {
  content: string;
  citations?: Citation[];
  isNoMatch?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  onOpenEvidence?: (citation: Citation) => void;
  activeFilter?: string;
}

/**
 * Assistant answer rendered as a single card: concise answer text with inline
 * `[N]` citation badges, an optional active-filter label, a friendly no-match
 * message, and a collapsible source list reusing CitationCard. Error state
 * shows a retry button.
 */
export function AnswerCard({
  content,
  citations = [],
  isNoMatch,
  isError,
  onRetry,
  onOpenEvidence,
  activeFilter,
}: AnswerCardProps) {
  const { t, accent } = useTheme();
  const { segments, citedSources } = parseCitations(content, citations);

  const shortName = (name: string) =>
    name.replace(" Privacy Policy", "").replace(" Privacy Statement", "");

  if (isError) {
    return (
      <div
        style={{
          background: t.surface,
          border: `1px solid ${t.border}`,
          borderRadius: 8,
          padding: "14px 16px",
          fontSize: 13,
          lineHeight: 1.6,
          color: t.text2,
        }}
      >
        <p style={{ margin: "0 0 12px" }}>
          Something went wrong while generating the response. Please try again.
        </p>
        <button
          type="button"
          onClick={onRetry}
          style={{
            background: accent,
            color: "#fff",
            border: "none",
            borderRadius: 6,
            padding: "6px 14px",
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Thử lại
        </button>
      </div>
    );
  }

  return (
    <div
      style={{
        background: t.surface,
        border: `1px solid ${t.border}`,
        borderRadius: "2px 8px 8px 8px",
        padding: "14px 16px",
        fontSize: 13,
        lineHeight: 1.6,
        color: t.text2,
      }}
    >
      {activeFilter && activeFilter !== "All Sources" && (
        <div style={{ fontSize: 12, color: accent, fontWeight: 600, marginBottom: 8 }}>
          Trả lời cho: {shortName(activeFilter)}
        </div>
      )}
      <p style={{ margin: "0 0 12px" }}>
        {segments.map((seg, idx) =>
          seg.type === "text" ? (
            <span key={idx}>{seg.content}</span>
          ) : (
            <InlineCitationBadge
              key={idx}
              id={seg.citationId!}
              onClick={(id) => {
                const c = citations.find((x) => x.id === id);
                if (c) onOpenEvidence?.(c);
              }}
            />
          )
        )}
      </p>
      {isNoMatch && (
        <div style={{ fontSize: 12, color: t.muted, fontStyle: "italic", marginTop: 8 }}>
          No matching policy sections found for this query.
        </div>
      )}
      {citedSources.length > 0 && !isNoMatch && (
        <div style={{ borderTop: `1px solid ${t.border2}`, paddingTop: 10 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: t.text, marginBottom: 8 }}>
            Sources
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {citedSources.map((c) => (
              <CitationCard key={c.id} citation={c} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
