import { StreamingCursor } from "./StreamingCursor";
import { AnswerCard } from "./AnswerCard";
import type { Citation } from "@/hooks/useSSEChat";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
  isNoMatch?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  onOpenEvidence?: (citation: Citation) => void;
  activeFilter?: string;
}

/**
 * User and assistant message bubbles.
 * User: right-aligned bubble.
 * Assistant (streaming): plain text with a streaming cursor.
 * Assistant (done): AnswerCard with inline citations and source list.
 */
export function MessageBubble({
  role,
  content,
  citations = [],
  isStreaming = false,
  isNoMatch = false,
  isError = false,
  onRetry,
  onOpenEvidence,
  activeFilter,
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
      {isStreaming ? (
        <div className="bg-white border border-zinc-200 rounded-lg px-4 py-3 text-zinc-950 text-base leading-relaxed w-full">
          <span>{content}</span>
          <StreamingCursor />
        </div>
      ) : (
        <AnswerCard
          content={content}
          citations={citations}
          isNoMatch={isNoMatch}
          isError={isError}
          onRetry={onRetry}
          onOpenEvidence={onOpenEvidence}
          activeFilter={activeFilter}
        />
      )}
    </div>
  );
}
