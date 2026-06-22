import type { Citation } from "@/hooks/useSSEChat";

export interface CitationSegment {
  type: "text" | "citation";
  content?: string;
  citationId?: number;
}

export interface ParsedCitations {
  segments: CitationSegment[];
  citedSources: Citation[];
}

/**
 * Parse an assistant answer string into renderable segments, replacing `[N]`
 * references with citation markers. Invalid IDs (no matching citation) are
 * left as literal text. Returns the deduplicated list of cited sources in
 * first-occurrence order.
 */
export function parseCitations(answer: string, citations: Citation[]): ParsedCitations {
  const segments: CitationSegment[] = [];
  const citedSourceIds = new Set<number>();
  const regex = /\[(\d+)\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(answer)) !== null) {
    const id = parseInt(match[1], 10);
    const citation = citations.find((c) => c.id === id);
    if (!citation) continue;

    if (match.index > lastIndex) {
      segments.push({ type: "text", content: answer.slice(lastIndex, match.index) });
    }
    segments.push({ type: "citation", citationId: id });
    citedSourceIds.add(id);
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < answer.length) {
    segments.push({ type: "text", content: answer.slice(lastIndex) });
  }

  const citedSources = Array.from(citedSourceIds)
    .map((id) => citations.find((c) => c.id === id))
    .filter((c): c is Citation => c !== undefined);

  return { segments, citedSources };
}
