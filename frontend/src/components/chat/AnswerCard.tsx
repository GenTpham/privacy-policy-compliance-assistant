import { parseCitations } from "@/lib/parseCitations";
import { InlineCitationBadge } from "./InlineCitationBadge";
import { CitationCard } from "./CitationCard";
import type { Citation } from "@/hooks/useSSEChat";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
  const { citedSources } = parseCitations(content, citations);

  const processedContent = content.replace(/\[(\d+)\]/g, (match, idStr) => {
    const id = parseInt(idStr, 10);
    if (citations.some((c) => c.id === id)) {
      return `[CITATION:${id}](#cite)`;
    }
    return match;
  });

  const shortName = (name: string) =>
    name.replace(" Privacy Policy", "").replace(" Privacy Statement", "");

  if (isError) {
    return (
      <div className="bg-surface border border-border rounded-[2rem] rounded-tl-sm px-6 py-5 text-[14px] leading-relaxed text-text-2 shadow-[var(--shadow-diffusion)]">
        <p className="m-0 mb-3">
          Something went wrong while generating the response. Please try again.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="bg-accent text-white border-none rounded-lg px-4 py-1.5 text-[13px] font-semibold cursor-pointer transition-all hover:bg-accent/90 active:scale-95 shadow-sm"
        >
          Thử lại
        </button>
      </div>
    );
  }

  return (
    <div className="bg-surface border border-border rounded-[2rem] rounded-tl-sm px-6 py-5 text-[14px] leading-relaxed text-text-2 shadow-[var(--shadow-diffusion)] w-full">
      {activeFilter && activeFilter !== "All Sources" && (
        <div className="text-[12px] text-accent font-semibold mb-2">
          Trả lời cho: {shortName(activeFilter)}
        </div>
      )}
      <div className="markdown-body mb-3">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            p: ({ children }) => <p className="m-0 mb-2">{children}</p>,
            ul: ({ children }) => <ul className="m-0 mb-2 pl-5 list-disc">{children}</ul>,
            ol: ({ children }) => <ol className="m-0 mb-2 pl-5 list-decimal">{children}</ol>,
            li: ({ children }) => <li className="my-1">{children}</li>,
            a: ({ href, children }) => {
              if (href === "#cite") {
                const text = children?.toString() || "";
                const match = text.match(/CITATION:(\d+)/);
                if (match) {
                  const id = parseInt(match[1], 10);
                  return (
                    <InlineCitationBadge
                      id={id}
                      onClick={() => {
                        const c = citations.find((x) => x.id === id);
                        if (c) onOpenEvidence?.(c);
                      }}
                    />
                  );
                }
              }
              return <a href={href} className="text-accent underline decoration-accent/30 underline-offset-2 hover:decoration-accent transition-colors">{children}</a>;
            },
          }}
        >
          {processedContent || ""}
        </ReactMarkdown>
      </div>
      {isNoMatch && (
        <div className="text-[12px] text-muted italic mt-2">
          No matching policy sections found for this query.
        </div>
      )}
      {citedSources.length > 0 && !isNoMatch && (
        <div className="border-t border-border-2 pt-3 mt-1">
          <div className="text-[12px] font-semibold text-text-1 mb-2">
            Sources
          </div>
          <div className="flex flex-col gap-2">
            {citedSources.map((c) => (
              <CitationCard key={c.id} citation={c} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
