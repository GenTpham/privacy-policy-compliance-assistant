# Chat UX Answer Card + Inline Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the assistant answer in the chat UI so general users can quickly scan a concise answer, click inline `[N]` badges to verify sources, and expand the source list only when needed.

**Architecture:** The backend SSE stream is unchanged. The frontend adds a small parser (`parseCitations`) and a reusable `AnswerCard` component. `AskAssistantScreen` manages a collapsible Evidence panel and passes `onOpenEvidence` into each answer card. `useSSEChat` gains a lightweight `retry` helper so the error state can resubmit the last user message.

**Tech Stack:** React 18, TypeScript, Vite, Vitest, React Testing Library, Tailwind CSS (for `MessageBubble`/`CitationCard`), inline theme tokens (for `AskAssistantScreen`/`AnswerCard`).

## Global Constraints

- Python 3.11 only — explicit runtime requirement (no backend changes in this plan).
- Models: OpenRouter exclusively (`google/gemma-4-26b-a4b` + `nvidia/llama-nemotron-embed-vl-1b-v2:free`) — no substitutions.
- Vector Store: Qdrant — no changes.
- Deployment: Docker Compose — frontend build must still pass `npm run build` and `npm test`.
- Auth: JWT-gated UI — no auth changes.
- Frontend framework: React + Vite + Tailwind; reuse existing components and theme tokens where possible.
- Testing: TDD-style, one failing test per new behavior, then implementation, then commit.

---

## File Structure

- **Create:** `frontend/src/lib/parseCitations.ts` — pure helper that splits an answer string into text segments and `[N]` citation references, returning a deduplicated ordered list of cited sources.
- **Create:** `frontend/src/lib/parseCitations.test.ts` — unit tests for the parser.
- **Create:** `frontend/src/components/chat/InlineCitationBadge.tsx` — small clickable `[N]` badge.
- **Create:** `frontend/src/components/chat/InlineCitationBadge.test.tsx` — unit tests for the badge.
- **Create:** `frontend/src/components/chat/AnswerCard.tsx` — card combining parsed answer, inline badges, and a collapsible source list.
- **Create:** `frontend/src/components/chat/AnswerCard.test.tsx` — unit tests for the card.
- **Create:** `frontend/src/components/chat/MessageBubble.test.tsx` — unit tests for the updated bubble.
- **Modify:** `frontend/src/components/chat/MessageBubble.tsx` — render `AnswerCard` for completed assistant messages; keep plain text during streaming.
- **Modify:** `frontend/src/hooks/useSSEChat.ts` — add `retry` function that resubmits the last user message after stripping the failed assistant placeholder.
- **Modify:** `frontend/src/pages/AskAssistantScreen.tsx` — manage Evidence panel open/closed state, pass `onOpenEvidence` and `onRetry` into the answer card, display active filter label.
- **Modify:** `frontend/src/lib/mockData.ts` — rephrase suggested prompts for general users.
- **Modify:** `frontend/src/components/chat/ChatPage.test.tsx` — update existing tests if mock data changes break assertions.

---

### Task 1: Create `parseCitations` helper

**Files:**
- Create: `frontend/src/lib/parseCitations.ts`
- Create: `frontend/src/lib/parseCitations.test.ts`

**Interfaces:**
- Consumes: `Citation` type from `frontend/src/hooks/useSSEChat.ts` (`{ id: number; qdrant_id: string; title: string; text: string; score: number }`).
- Produces: `ParsedCitations` with `segments: CitationSegment[]` and `citedSources: Citation[]`. Later tasks import `parseCitations` and `ParsedCitations` from this file.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/lib/parseCitations.test.ts
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/parseCitations.test.ts`

Expected: FAIL with `Error: Cannot find module './parseCitations'` or similar.

- [ ] **Step 3: Write minimal implementation**

```typescript
// frontend/src/lib/parseCitations.ts
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/parseCitations.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/parseCitations.ts frontend/src/lib/parseCitations.test.ts
git commit -m "feat: add parseCitations helper for inline citation badges

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Create `InlineCitationBadge` component

**Files:**
- Create: `frontend/src/components/chat/InlineCitationBadge.tsx`
- Create: `frontend/src/components/chat/InlineCitationBadge.test.tsx`

**Interfaces:**
- Consumes: nothing from other tasks (pure presentational).
- Produces: `InlineCitationBadgeProps { id: number; onClick?: (id: number) => void }`. `AnswerCard` (Task 3) imports this component and provides `onClick`.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/components/chat/InlineCitationBadge.test.tsx
import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InlineCitationBadge } from "./InlineCitationBadge";

describe("InlineCitationBadge", () => {
  test("renders citation id", () => {
    render(<InlineCitationBadge id={3} />);
    expect(screen.getByRole("button", { name: /citation 3/i })).toHaveTextContent("[3]");
  });

  test("calls onClick with id when clicked", async () => {
    const handleClick = vi.fn();
    render(<InlineCitationBadge id={3} onClick={handleClick} />);
    await userEvent.click(screen.getByRole("button", { name: /citation 3/i }));
    expect(handleClick).toHaveBeenCalledWith(3);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/InlineCitationBadge.test.tsx`

Expected: FAIL with module not found.

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/components/chat/InlineCitationBadge.tsx
export interface InlineCitationBadgeProps {
  id: number;
  onClick?: (id: number) => void;
}

export function InlineCitationBadge({ id, onClick }: InlineCitationBadgeProps) {
  return (
    <button
      type="button"
      onClick={() => onClick?.(id)}
      className="inline-flex items-center justify-center px-1.5 py-0.5 mx-0.5 text-xs font-semibold rounded bg-blue-100 text-blue-700 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300"
      aria-label={`Citation ${id}`}
    >
      [{id}]
    </button>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/chat/InlineCitationBadge.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/InlineCitationBadge.tsx frontend/src/components/chat/InlineCitationBadge.test.tsx
git commit -m "feat: add inline citation badge component

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Create `AnswerCard` component

**Files:**
- Create: `frontend/src/components/chat/AnswerCard.tsx`
- Create: `frontend/src/components/chat/AnswerCard.test.tsx`
- Modify: `frontend/src/components/chat/CitationCard.tsx` (only if visual spacing inside AnswerCard needs adjustment; otherwise skip)

**Interfaces:**
- Consumes: `parseCitations` from Task 1, `InlineCitationBadge` from Task 2, `CitationCard` from existing code, `Citation` from `useSSEChat.ts`, `useTheme` from `frontend/src/lib/theme.ts`.
- Produces: `AnswerCardProps { content: string; citations?: Citation[]; isNoMatch?: boolean; isError?: boolean; onRetry?: () => void; onOpenEvidence?: (citation: Citation) => void; activeFilter?: string }`. `MessageBubble` (Task 4) and `AskAssistantScreen` (Task 5) import and use `AnswerCard`.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/components/chat/AnswerCard.test.tsx
import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AnswerCard } from "./AnswerCard";
import type { Citation } from "@/hooks/useSSEChat";

const citations: Citation[] = [
  { id: 1, qdrant_id: "a", title: "Google Privacy Policy", text: "Users can delete data.", score: 0.91 },
  { id: 2, qdrant_id: "b", title: "Meta Privacy Policy", text: "Meta retains data.", score: 0.74 },
];

describe("AnswerCard", () => {
  test("renders parsed answer with inline citation badges", () => {
    render(<AnswerCard content="Answer [1] and [2]." citations={citations} />);
    expect(screen.getByText("Answer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /citation 1/i })).toHaveTextContent("[1]");
    expect(screen.getByRole("button", { name: /citation 2/i })).toHaveTextContent("[2]");
  });

  test("opens evidence when citation badge is clicked", async () => {
    const openEvidence = vi.fn();
    render(<AnswerCard content="Answer [1]." citations={citations} onOpenEvidence={openEvidence} />);
    await userEvent.click(screen.getByRole("button", { name: /citation 1/i }));
    expect(openEvidence).toHaveBeenCalledWith(citations[0]);
  });

  test("renders sources section with cited sources", () => {
    render(<AnswerCard content="Answer [1]." citations={citations} />);
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("Google Privacy Policy")).toBeInTheDocument();
  });

  test("renders no-match message", () => {
    render(<AnswerCard content="No answer." citations={[]} isNoMatch />);
    expect(screen.getByText(/No matching policy sections found/i)).toBeInTheDocument();
  });

  test("renders error state with retry button", async () => {
    const retry = vi.fn();
    render(<AnswerCard content="" isError onRetry={retry} />);
    await userEvent.click(screen.getByRole("button", { name: /thử lại/i }));
    expect(retry).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/AnswerCard.test.tsx`

Expected: FAIL with module not found.

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/components/chat/AnswerCard.tsx
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

  const shortName = (name: string) => name.replace(" Privacy Policy", "").replace(" Privacy Statement", "");

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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/chat/AnswerCard.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/AnswerCard.tsx frontend/src/components/chat/AnswerCard.test.tsx
# If CitationCard.tsx was modified, add it too.
git commit -m "feat: add AnswerCard with inline citations and source list

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Update `MessageBubble` to render `AnswerCard`

**Files:**
- Modify: `frontend/src/components/chat/MessageBubble.tsx`
- Create: `frontend/src/components/chat/MessageBubble.test.tsx`

**Interfaces:**
- Consumes: `AnswerCard` from Task 3, `Citation` from `useSSEChat.ts`.
- Produces: `MessageBubbleProps` gains optional `onOpenEvidence` and `onRetry`. `ChatPage` (existing) and `MessageList` (existing) consume `MessageBubble`.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/components/chat/MessageBubble.test.tsx
import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MessageBubble } from "./MessageBubble";
import type { Citation } from "@/hooks/useSSEChat";

const citations: Citation[] = [
  { id: 1, qdrant_id: "a", title: "Google Privacy Policy", text: "Users can delete data.", score: 0.91 },
];

describe("MessageBubble", () => {
  test("renders user message as bubble", () => {
    render(<MessageBubble role="user" content="Hello" />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  test("renders AnswerCard for completed assistant message", () => {
    render(<MessageBubble role="assistant" content="Answer [1]." citations={citations} />);
    expect(screen.getByRole("button", { name: /citation 1/i })).toBeInTheDocument();
  });

  test("renders plain text while streaming", () => {
    render(<MessageBubble role="assistant" content="Still typing" isStreaming />);
    expect(screen.getByText("Still typing")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /citation/i })).not.toBeInTheDocument();
  });

  test("passes onOpenEvidence to AnswerCard", async () => {
    const openEvidence = vi.fn();
    render(
      <MessageBubble
        role="assistant"
        content="Answer [1]."
        citations={citations}
        onOpenEvidence={openEvidence}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /citation 1/i }));
    expect(openEvidence).toHaveBeenCalledWith(citations[0]);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/MessageBubble.test.tsx`

Expected: FAIL because `MessageBubble` does not yet export `onOpenEvidence`/`onRetry` or render `AnswerCard`.

- [ ] **Step 3: Write minimal implementation**

Update `frontend/src/components/chat/MessageBubble.tsx`:

```tsx
import { CitationCard } from "./CitationCard";
import { NoMatchMessage } from "./NoMatchMessage";
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
}

export function MessageBubble({
  role,
  content,
  citations = [],
  isStreaming = false,
  isNoMatch = false,
  isError = false,
  onRetry,
  onOpenEvidence,
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

  return (
    <div className="flex flex-col items-start gap-2 max-w-[80%]">
      {isStreaming ? (
        <div className="bg-white border border-zinc-200 rounded-lg px-4 py-3 text-zinc-950 text-base leading-relaxed w-full">
          <span>{content}</span>
          {isStreaming && <StreamingCursor />}
        </div>
      ) : (
        <AnswerCard
          content={content}
          citations={citations}
          isNoMatch={isNoMatch}
          isError={isError}
          onRetry={onRetry}
          onOpenEvidence={onOpenEvidence}
        />
      )}
    </div>
  );
}
```

Note: Remove the old `NoMatchMessage` and `CitationCard` imports if no longer used. If `CitationCard` is still used elsewhere in the file, keep it. After the change above, `NoMatchMessage`, `CitationCard`, and the old inline rendering are no longer needed inside `MessageBubble`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/chat/MessageBubble.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/MessageBubble.tsx frontend/src/components/chat/MessageBubble.test.tsx
git commit -m "feat: render AnswerCard inside MessageBubble for completed assistant messages

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Add `retry` to `useSSEChat`

**Files:**
- Modify: `frontend/src/hooks/useSSEChat.ts`
- Modify: `frontend/src/hooks/useSSEChat.test.ts` (if it exists; otherwise create it)

**Interfaces:**
- Consumes: existing `fetchWithAuth`, `parseSSEStream`, `tokens` refresh flow inside `fetchWithAuth`.
- Produces: `UseSSEChatReturn` gains `retry: (onUnauthorized: () => void, sourceFilter?: string | null) => Promise<void>`. `AskAssistantScreen` (Task 6) and `ChatPage` (existing) consume `retry`.

- [ ] **Step 1: Write the failing test**

First check if `frontend/src/hooks/useSSEChat.test.ts` exists. If not, create it.

```typescript
// frontend/src/hooks/useSSEChat.test.ts
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useSSEChat } from "./useSSEChat";

const mockReader = {
  read: vi.fn(),
  releaseLock: vi.fn(),
};

global.fetch = vi.fn();

function createStream(chunks: string[]) {
  let i = 0;
  return {
    getReader: () => ({
      read: async () => {
        if (i >= chunks.length) return { done: true, value: undefined };
        const value = new TextEncoder().encode(chunks[i++]);
        return { done: false, value };
      },
      releaseLock: vi.fn(),
    }),
  };
}

describe("useSSEChat retry", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("retry resubmits the last user message after an error", async () => {
    const { result } = renderHook(() => useSSEChat());

    // First submit fails
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    await act(async () => {
      await result.current.submit("What data does Google collect?", vi.fn());
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1].isError).toBe(true);

    // Retry succeeds
    const successResponse = {
      ok: true,
      body: createStream([
        `data: {"type":"delta","content":"Answer"}\n\n`,
        `data: {"type":"done","answer":"Answer.","citations":[]}\n\n`,
      ]),
    };
    (global.fetch as any).mockResolvedValueOnce(successResponse);

    await act(async () => {
      await result.current.retry(vi.fn());
    });

    await waitFor(() => expect(result.current.messages.some((m) => m.content === "Answer.")).toBe(true));
    expect(result.current.isStreaming).toBe(false);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/useSSEChat.test.ts`

Expected: FAIL because `retry` is not exported from `useSSEChat`.

- [ ] **Step 3: Write minimal implementation**

Refactor `frontend/src/hooks/useSSEChat.ts` to extract a shared streaming core (`runStream`) so `submit` and `retry` share the fetch + SSE handling without duplicating the user message.

First update the exported return type:

```typescript
export interface UseSSEChatReturn {
  messages: Message[];
  isStreaming: boolean;
  submit: (message: string, onUnauthorized: () => void, sourceFilter?: string | null) => Promise<void>;
  retry: (onUnauthorized: () => void, sourceFilter?: string | null) => Promise<void>;
}
```

Then add a `runStream` helper inside `useSSEChat` that owns the fetch + SSE loop and updates the **last** assistant message in state. Move the existing fetch/SSE/catch body out of `submit` into `runStream`:

```typescript
const runStream = useCallback(
  async (
    message: string,
    history: { role: string; content: string }[],
    onUnauthorized: () => void,
    sourceFilter?: string | null
  ): Promise<void> => {
    try {
      const response = await fetchWithAuth(
        "/api/chat",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            history,
            source_filter: sourceFilter ?? null,
          }),
        },
        onUnauthorized
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      for await (const event of parseSSEStream(response)) {
        const ev = event as {
          type: string;
          content?: string;
          answer?: string;
          citations?: Citation[];
          message?: string;
        };

        if (ev.type === "delta" && ev.content !== undefined) {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            updated[updated.length - 1] = { ...last, content: last.content + ev.content };
            return updated;
          });
        } else if (ev.type === "done") {
          const citations = ev.citations ?? [];
          const isNoMatch = citations.length === 0;
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = { role: "assistant", content: ev.answer ?? "", citations, isNoMatch };
            return updated;
          });
          setIsStreaming(false);
        } else if (ev.type === "error") {
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              role: "assistant",
              content: "Something went wrong while generating the response. Please try again.",
              isError: true,
            };
            return updated;
          });
          setIsStreaming(false);
        }
      }
    } catch (_err) {
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === "assistant" && !last.content) {
          updated[updated.length - 1] = {
            role: "assistant",
            content: "Something went wrong while generating the response. Please try again.",
            isError: true,
          };
        }
        return updated;
      });
      setIsStreaming(false);
    }
  },
  []
);
```

Rewrite `submit` to add the user message + placeholder, then delegate to `runStream`:

```typescript
const submit = useCallback(
  async (message: string, onUnauthorized: () => void, sourceFilter?: string | null): Promise<void> => {
    if (isStreaming) return;

    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    const userMessage: Message = { role: "user", content: message };
    const assistantPlaceholder: Message = { role: "assistant", content: "", citations: [] };

    setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
    setIsStreaming(true);

    await runStream(message, history, onUnauthorized, sourceFilter);
  },
  [messages, isStreaming, runStream]
);
```

Add `retry`. It does NOT call `submit` (which would add a duplicate user message). Instead it rebuilds history from everything **before** the last user message, strips trailing assistant messages, adds one fresh placeholder, and streams again:

```typescript
const retry = useCallback(
  async (onUnauthorized: () => void, sourceFilter?: string | null): Promise<void> => {
    if (isStreaming) return;

    const lastUserIdx = messages.map((m) => m.role).lastIndexOf("user");
    if (lastUserIdx === -1) return;
    const lastUserMessage = messages[lastUserIdx];

    // History = everything before the last user turn (no duplicate user message)
    const history = messages
      .slice(0, lastUserIdx)
      .map((m) => ({ role: m.role, content: m.content }));

    // Drop trailing assistant message(s), then add a fresh placeholder
    setMessages((prev) => {
      const trimmed = [...prev];
      while (trimmed.length > 0 && trimmed[trimmed.length - 1].role === "assistant") {
        trimmed.pop();
      }
      return [...trimmed, { role: "assistant", content: "", citations: [] } as Message];
    });
    setIsStreaming(true);

    await runStream(lastUserMessage.content, history, onUnauthorized, sourceFilter);
  },
  [messages, isStreaming, runStream]
);
```

Update the return statement:

```typescript
return { messages, isStreaming, submit, retry };
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/hooks/useSSEChat.test.ts`

Expected: PASS. If the mock stream setup is tricky, adjust the mock to match the `parseSSEStream` implementation.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useSSEChat.ts frontend/src/hooks/useSSEChat.test.ts
git commit -m "feat: add retry helper to useSSEChat for failed assistant responses

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Update `AskAssistantScreen` for collapsible Evidence panel

**Files:**
- Modify: `frontend/src/pages/AskAssistantScreen.tsx`

**Interfaces:**
- Consumes: `AnswerCard` from Task 3, `retry` from Task 5, `useTheme` from `frontend/src/lib/theme.ts`, `fetchWithAuth` from `frontend/src/lib/api.ts`.
- Produces: `AskAssistantScreen` renders the new answer card layout and manages `isEvidenceOpen` / `activeEvidence` state.

- [ ] **Step 1: Write the failing test**

Create or update a test for `AskAssistantScreen`. If the file does not exist, create `frontend/src/pages/AskAssistantScreen.test.tsx`.

```typescript
// frontend/src/pages/AskAssistantScreen.test.tsx
import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AskAssistantScreen } from "./AskAssistantScreen";
import type { UseSSEChatReturn, Citation, Message } from "@/hooks/useSSEChat";

vi.mock("@/lib/api", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({ ok: true, json: async () => ({ sources: ["Google Privacy Policy"] }) }),
}));

function makeChat(messages: Message[] = [], isStreaming = false): UseSSEChatReturn {
  return {
    messages,
    isStreaming,
    submit: vi.fn(),
    retry: vi.fn(),
  };
}

const citation: Citation = { id: 1, qdrant_id: "a", title: "Google Privacy Policy", text: "Users can delete data.", score: 0.91 };

describe("AskAssistantScreen", () => {
  test("renders AnswerCard for completed assistant message", () => {
    const chat = makeChat([
      { role: "user", content: "Hello" },
      { role: "assistant", content: "Answer [1].", citations: [citation] },
    ]);
    render(<AskAssistantScreen chat={chat} forceLogout={vi.fn()} />);
    expect(screen.getByRole("button", { name: /citation 1/i })).toBeInTheDocument();
  });

  test("opens Evidence panel when citation badge is clicked", async () => {
    const chat = makeChat([
      { role: "user", content: "Hello" },
      { role: "assistant", content: "Answer [1].", citations: [citation] },
    ]);
    render(<AskAssistantScreen chat={chat} forceLogout={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /citation 1/i }));
    expect(screen.getByText(/Evidence/i)).toBeInTheDocument();
  });

  test("calls retry on error answer", async () => {
    const chat = makeChat([
      { role: "user", content: "Hello" },
      { role: "assistant", content: "", isError: true },
    ]);
    render(<AskAssistantScreen chat={chat} forceLogout={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /thử lại/i }));
    expect(chat.retry).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/AskAssistantScreen.test.tsx`

Expected: FAIL because the screen does not yet use `AnswerCard` or manage the panel state.

- [ ] **Step 3: Write minimal implementation**

Modify `frontend/src/pages/AskAssistantScreen.tsx`:

1. Add imports:

```tsx
import { AnswerCard } from "@/components/chat/AnswerCard";
```

2. Add state for the Evidence panel:

```tsx
const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);
```

3. Add a handler to open evidence:

```tsx
const handleOpenEvidence = (c: Citation) => {
  setActiveEvidence([c]);
  setIsEvidenceOpen(true);
};
```

4. In the assistant message rendering, replace the current inline answer block with `AnswerCard`. Locate the existing assistant rendering inside the `messages.map` block and replace the assistant branch (the `else` branch starting at line ~186) with:

```tsx
} else {
  return (
    <div
      key={idx}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        maxWidth: "85%",
        alignSelf: "flex-start",
      }}
    >
      <AnswerCard
        content={msg.content}
        citations={msg.citations}
        isNoMatch={msg.isNoMatch}
        isError={msg.isError}
        onRetry={() => chat.retry(forceLogout, activeFilter === "All Sources" ? null : activeFilter)}
        onOpenEvidence={handleOpenEvidence}
        activeFilter={activeFilter}
      />
      <span style={{ fontSize: 10, color: t.faintest, marginTop: 4 }}>
        {new Date().toTimeString().slice(0, 5)}
      </span>
    </div>
  );
}
```

5. Make the Evidence panel conditionally visible. Wrap the right-side Evidence panel `div` with a conditional. The existing right panel starts around line 264. Replace the static width with a conditional width and add a close button:

```tsx
{isEvidenceOpen && (
  <div style={{ width: 300, borderLeft: `1px solid ${t.border}`, background: t.surface2, display: "flex", flexDirection: "column", flexShrink: 0 }}>
    <div style={{ padding: "14px 16px", borderBottom: `1px solid ${t.border2}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{ fontSize: 12, fontWeight: 700, color: t.text, letterSpacing: "0.04em", textTransform: "uppercase" }}>Evidence</span>
      <button type="button" onClick={() => setIsEvidenceOpen(false)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16, color: t.faint }}>✕</button>
    </div>
    <div style={{ flex: 1, overflowY: "auto", padding: 12 }}>
      {/* existing activeEvidence rendering */}
    </div>
  </div>
)}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/AskAssistantScreen.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/AskAssistantScreen.tsx frontend/src/pages/AskAssistantScreen.test.tsx
git commit -m "feat: use AnswerCard and collapsible Evidence panel in AskAssistantScreen

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Update suggested prompts for general users

**Files:**
- Modify: `frontend/src/lib/mockData.ts`
- Modify: `frontend/src/components/chat/ChatPage.test.tsx` (if any test asserts the old prompt text)

**Interfaces:**
- Consumes: none.
- Produces: `SUGGESTED_PROMPTS` array with new Vietnamese/English prompts tailored to general users.

- [ ] **Step 1: Update the prompts**

Replace `SUGGESTED_PROMPTS` in `frontend/src/lib/mockData.ts`:

```typescript
export const SUGGESTED_PROMPTS = [
  "Google thu thập dữ liệu gì từ tôi?",
  "TikTok có chia sẻ dữ liệu không?",
  "Tôi có quyền gì với dữ liệu của mình trên Facebook?",
  "Dữ liệu của tôi được lưu giữ bao lâu trên OpenAI?",
  "Shopify dùng cookie gì để theo dõi?",
];
```

- [ ] **Step 2: Run tests to verify no regression**

Run: `cd frontend && npx vitest run`

Expected: PASS. If any existing test asserts the old prompt text, update that test.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/mockData.ts
# Add any test file updates if needed
git commit -m "feat: rephrase suggested prompts for general users

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Integration verification and final QA

**Files:**
- All frontend files changed above.
- No new files.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: passing test suite and successful build.

- [ ] **Step 1: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`

Expected: PASS.

- [ ] **Step 2: Run the frontend build**

Run: `cd frontend && npm run build`

Expected: PASS with no TypeScript or build errors.

- [ ] **Step 3: Run backend regression tests**

Run: `python -m pytest backend/app/tests`

Expected: PASS (no backend changes, but verify nothing is broken).

- [ ] **Step 4: Manual smoke test in browser**

1. Start the stack: `docker compose up --build` (or `make up` if Makefile is configured).
2. Log in and navigate to Ask Assistant.
3. Ask: “Google thu thập dữ liệu gì từ tôi?”
4. Verify:
   - Answer appears as a card.
   - Inline `[N]` badges are clickable.
   - Clicking a badge opens the Evidence panel on the right.
   - The Sources section is visible below the answer.
   - Suggested prompts are rephrased.
5. Ask an unanswerable question and verify the no-match message.
6. Simulate an error (e.g., temporarily disable OpenRouter key) and verify the retry button.

- [ ] **Step 5: Final commit (if any fixes were needed)**

```bash
git commit -m "fix: final QA adjustments for chat UX answer card

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Plan Self-Review

### 1. Spec coverage

| Spec requirement | Task that implements it |
|---|---|
| Answer card layout with inline badges and Sources section | Task 3 (AnswerCard) |
| Inline badges open Evidence panel | Task 3 + Task 6 |
| Evidence panel collapsed by default | Task 6 |
| Preserve SSE streaming | Task 3 (AnswerCard only renders after `done`; streaming remains plain text) + Task 4 |
| Retry on error | Task 5 + Task 3 error state |
| No-match friendly message | Task 3 |
| Suggested prompts for general users | Task 7 |
| Reuse existing CitationCard | Task 3 |

### 2. Placeholder scan

- No TBD/TODO markers in the plan.
- Every step includes concrete code, commands, and expected outputs.
- Test code is provided for every new behavior.

### 3. Type consistency

- `Citation` type is imported from `frontend/src/hooks/useSSEChat.ts` in all tasks.
- `AnswerCardProps` uses `citations?: Citation[]` consistently.
- `InlineCitationBadge` uses `onClick?: (id: number) => void` consistently.
- `useSSEChat` return type is updated to include `retry` in Task 5; consumers in Task 6 use `chat.retry`.

### 4. Known gaps / notes

- `MessageBubble` is updated for `ChatPage`, but the primary user-facing chat is `AskAssistantScreen`. Both are covered.
- `CitationCard` may need minor spacing tweaks when nested inside `AnswerCard`; if so, fix in Task 3 and add a quick test.
- `retry` shares a `runStream` core with `submit` so it does not create a duplicate user message — history is rebuilt from everything before the last user turn.
