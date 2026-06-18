import { describe, test, expect } from "vitest";
import { parseCitations } from "./parseCitations";
import type { Citation } from "@/hooks/useSSEChat";

const citations: Citation[] = [
  { id: 1, qdrant_id: "a", title: "T1", text: "Text one", score: 0.9 },
  { id: 2, qdrant_id: "b", title: "T2", text: "Text two", score: 0.8 },
];

describe("parseCitations", () => {
  test("splits answer into text and citation segments", () => {
    const result = parseCitations("Hello [1] world [2] end.", citations);
    expect(result.segments).toEqual([
      { type: "text", content: "Hello " },
      { type: "citation", citationId: 1 },
      { type: "text", content: " world " },
      { type: "citation", citationId: 2 },
      { type: "text", content: " end." },
    ]);
  });

  test("returns deduplicated cited sources in first-occurrence order", () => {
    const result = parseCitations("[2] then [1] then [2] again.", citations);
    expect(result.citedSources.map((c) => c.id)).toEqual([2, 1]);
  });

  test("drops invalid citation ids", () => {
    const result = parseCitations("Valid [1] invalid [99] end.", citations);
    expect(result.segments).toEqual([
      { type: "text", content: "Valid " },
      { type: "citation", citationId: 1 },
      { type: "text", content: " invalid [99] end." },
    ]);
    expect(result.citedSources.map((c) => c.id)).toEqual([1]);
  });

  test("handles answer with no citations", () => {
    const result = parseCitations("Just text.", citations);
    expect(result.segments).toEqual([{ type: "text", content: "Just text." }]);
    expect(result.citedSources).toEqual([]);
  });
});
