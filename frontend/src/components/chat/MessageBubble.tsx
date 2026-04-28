import { CitationCard } from "./CitationCard";
import { NoMatchMessage } from "./NoMatchMessage";
import { StreamingCursor } from "./StreamingCursor";
import type { Citation } from "@/hooks/useSSEChat";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
  isNoMatch?: boolean;
  isError?: boolean;
}

/**
 * User and assistant message bubbles.
 * Visual spec from UI-SPEC.md Message Bubbles section.
 * User:      right-aligned, bg-zinc-100, max-w-[70%]
 * Assistant: left-aligned, bg-white border border-zinc-200, max-w-[80%]
 * Citations fade in after done event (D-04): CSS fadeIn 200ms ease-out.
 */
export function MessageBubble({
  role,
  content,
  citations = [],
  isStreaming = false,
  isNoMatch = false,
}: MessageBubbleProps) {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-zinc-100 rounded-lg px-4 py-3 max-w-[70%] text-zinc-950 text-base leading-relaxed">
          {content}
        </div>
      </div>
    );
  }

  // Assistant bubble
  return (
    <div className="flex flex-col items-start gap-2 max-w-[80%]">
      {/* Message text — bg-white border border-zinc-200 per UI-SPEC */}
      <div className="bg-white border border-zinc-200 rounded-lg px-4 py-3 text-zinc-950 text-base leading-relaxed w-full">
        <span>{content}</span>
        {isStreaming && <StreamingCursor />}
      </div>

      {/* No-match state — replaces citation cards */}
      {isNoMatch && !isStreaming && <NoMatchMessage />}

      {/* Citation cards — fade in after done event (D-04), 200ms ease-out */}
      {!isNoMatch && !isStreaming && citations.length > 0 && (
        <div
          className="flex flex-col gap-2 w-full"
          style={{ animation: "fadeIn 200ms ease-out forwards" }}
        >
          {citations.map((citation) => (
            <CitationCard key={citation.id} citation={citation} />
          ))}
        </div>
      )}
    </div>
  );
}
