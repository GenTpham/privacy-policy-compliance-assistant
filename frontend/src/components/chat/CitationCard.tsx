import { useState } from "react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Citation } from "@/hooks/useSSEChat";

interface CitationCardProps {
  citation: Citation;
}

/**
 * Expandable citation card.
 * Collapsed state (default, D-05): title + 50-char excerpt preview (D-06).
 * Expanded state: full verbatim text in font-mono (D-07).
 * Fade-in applied at container level in MessageBubble (D-04).
 * Keyboard accessible via Radix Collapsible (shadcn/ui).
 */
export function CitationCard({ citation }: CitationCardProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Truncate preview to ~50 chars with ellipsis (D-06)
  const preview =
    citation.text.length > 50
      ? citation.text.slice(0, 50) + "…"
      : citation.text;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger
        className={cn(
          "w-full flex items-start justify-between gap-2 p-3 rounded-md text-left",
          "bg-zinc-50 border border-zinc-200",
          "hover:bg-zinc-100 transition-colors",
          isOpen && "bg-white border-zinc-300 rounded-b-none"
        )}
        aria-label={isOpen ? "Collapse citation" : "Expand citation"}
      >
        <div className="flex items-start gap-2 min-w-0">
          {/* FileText icon in accent color (UI-SPEC Color section) */}
          <FileText
            className="h-4 w-4 text-zinc-950 shrink-0 mt-0.5"
            aria-hidden="true"
          />
          <div className="min-w-0">
            {/* Document title — 14px/600 per UI-SPEC Typography label */}
            <p className="text-sm font-semibold text-zinc-950 truncate">
              {citation.title}
            </p>
            {/* 50-char preview — 12px/400 per UI-SPEC Typography caption */}
            <p className="text-xs text-zinc-500 truncate">{preview}</p>
          </div>
        </div>
        {/* ChevronDown rotates 180deg on open — 150ms ease-in-out per UI-SPEC Animation Contract */}
        <ChevronDown
          className={cn(
            "h-4 w-4 text-zinc-950 shrink-0 mt-0.5 transition-transform duration-150 ease-in-out",
            isOpen && "rotate-180"
          )}
          aria-hidden="true"
        />
      </CollapsibleTrigger>
      <CollapsibleContent>
        {/* Full verbatim excerpt — font-mono text-sm per UI-SPEC Citation Cards expanded state */}
        <div className="bg-white border border-zinc-300 border-t-0 rounded-b-md p-3">
          <p className="font-mono text-sm text-zinc-800 whitespace-pre-wrap">
            {citation.text}
          </p>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
