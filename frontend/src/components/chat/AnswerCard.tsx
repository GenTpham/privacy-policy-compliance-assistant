import { parseCitations } from "@/lib/parseCitations";
import { InlineCitationBadge } from "./InlineCitationBadge";
import { CitationCard } from "./CitationCard";
import type { Citation } from "@/hooks/useSSEChat";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, AlignLeft, Globe } from "lucide-react";

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
      <div className="w-full">
        <p className="m-0 mb-3 text-red-500">
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

  // Import lucide icons at the top of this chunk for the layout
  // (We'll assume they are imported, wait I should use a replace block for imports too)

  return (
    <div className="w-full flex flex-col gap-8">
      {citedSources.length > 0 && !isNoMatch && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 bg-surface border border-border rounded-md flex items-center justify-center shadow-sm">
              <Link className="w-4 h-4 text-text-3" />
            </div>
            <h2 className="text-[16px] font-bold text-text-1 m-0">Sources</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {citedSources.slice(0, 3).map((c) => (
              <div key={c.id} onClick={() => onOpenEvidence?.(c)} className="cursor-pointer flex flex-col justify-center p-3 bg-surface-2 border border-border rounded-xl hover:bg-border transition-colors">
                <div className="text-[13px] font-semibold text-text-1 line-clamp-1 mb-1.5">
                  {c.doc_id.replace(".txt", "")}
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-5 h-5 bg-surface rounded-full flex items-center justify-center shadow-sm">
                    <Globe className="w-3 h-3 text-text-3" />
                  </div>
                  <span className="text-[11px] font-medium text-text-2 truncate">{c.doc_id}</span>
                </div>
              </div>
            ))}
            {citedSources.length > 3 && (
              <div className="flex flex-col justify-center p-3 bg-surface-2 border border-border rounded-xl cursor-pointer hover:bg-border transition-colors">
                <div className="text-[13px] font-semibold text-text-1 line-clamp-1 mb-1.5">
                  View {citedSources.length - 3} more sources
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-5 h-5 bg-surface rounded-full flex items-center justify-center shadow-sm">
                    <Globe className="w-3 h-3 text-text-3" />
                  </div>
                  <span className="text-[11px] font-medium text-text-2 truncate">View All Sources</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <div>
        <div className="flex items-center gap-2 mb-4">
          <div className="w-7 h-7 bg-surface border border-border rounded-md flex items-center justify-center shadow-sm">
            <AlignLeft className="w-4 h-4 text-text-3" />
          </div>
          <h2 className="text-[16px] font-bold text-text-1 m-0">Answer</h2>
        </div>
        <div className="markdown-body text-[15px] leading-[1.8] text-text-2">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => <p className="m-0 mb-4">{children}</p>,
              ul: ({ children }) => <ul className="m-0 mb-4 pl-5 list-disc">{children}</ul>,
              ol: ({ children }) => <ol className="m-0 mb-4 pl-5 list-decimal">{children}</ol>,
              li: ({ children }) => <li className="my-1.5">{children}</li>,
              h1: ({ children }) => <h1 className="text-xl font-bold text-text-1 mt-6 mb-3">{children}</h1>,
              h2: ({ children }) => <h2 className="text-lg font-bold text-text-1 mt-5 mb-2">{children}</h2>,
              h3: ({ children }) => <h3 className="text-base font-bold text-text-1 mt-4 mb-2">{children}</h3>,
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
                return <a href={href} className="text-accent font-semibold hover:underline">{children}</a>;
              },
            }}
          >
            {processedContent || ""}
          </ReactMarkdown>
        </div>
        {isNoMatch && (
          <div className="text-[13px] text-muted italic mt-2">
            No matching policy sections found for this query.
          </div>
        )}
      </div>
    </div>
  );
}
