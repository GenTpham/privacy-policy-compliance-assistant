"""
backend/ingestion/chunker.py
Context-aware text splitting for privacy policy passages.
Tracks Markdown headers to inject breadcrumb context into each chunk.
Preserves list items as atomic units. Token budget: 350 (safe for Nemotron).
"""
import re
from dataclasses import dataclass

import tiktoken

MAX_TOKENS = 350       # reduced from 400 — safety buffer for Nemotron tokenizer mismatch
OVERLAP_TOKENS = 50    # ~14% overlap — preserves clause continuity at boundaries
SEPARATORS = ["\n\n", "\n", ". ", " "]  # priority order — paragraph → line → sentence → word

_enc = tiktoken.get_encoding("cl100k_base")

# ── Regex patterns ────────────────────────────────────────────────────────────
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_LIST_ITEM_RE = re.compile(
    r"^\s*(\d+\.|[a-z]\)|[a-z]\.|[(][a-z][)]|\*|-)\s", re.IGNORECASE
)


@dataclass
class Chunk:
    text: str
    title: str
    source_doc: str
    passage_id: str
    chunk_index: int
    token_count: int
    context_header: str = ""
    llm_context: str = ""

    @property
    def enriched_text(self) -> str:
        """Return text with context header and LLM context prepended (if present)."""
        parts: list[str] = []
        if self.context_header:
            parts.append(self.context_header)
        if self.llm_context:
            parts.append(self.llm_context)
        parts.append(self.text)
        return "\n\n".join(parts)


def _count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def _build_header_breadcrumb(header_stack: dict[int, str], title: str) -> str:
    """
    Build a breadcrumb string from the current header stack.
    Example: "[Source: Chính sách Zalo | Context: Điều 1 > Khoản 2]"
    """
    if not header_stack:
        return ""
    parts = [header_stack[level] for level in sorted(header_stack.keys())]
    context_path = " > ".join(parts)
    return f"[Source: {title} | Context: {context_path}]"


def _extract_headers(text: str) -> list[tuple[int, str, int]]:
    """
    Extract all markdown headers from text.
    Returns list of (level, header_text, char_position).
    """
    results = []
    for match in _HEADER_RE.finditer(text):
        level = len(match.group(1))  # number of '#' chars
        header_text = match.group(2).strip()
        results.append((level, header_text, match.start()))
    return results


def _is_list_item_start(text: str) -> bool:
    """Detect if text begins a numbered/lettered list item."""
    return bool(_LIST_ITEM_RE.match(text))


def _split_preserving_lists(text: str, separator: str) -> list[str]:
    """
    Split text by separator, but merge list items with their preceding
    content to avoid splitting mid-list.
    """
    if separator == " ":
        return text.split()

    raw_parts = text.split(separator)
    if len(raw_parts) <= 1:
        return [text]

    # Re-attach separator to end of each part except last
    parts = [p + separator for p in raw_parts[:-1]] + [raw_parts[-1]]

    # Merge consecutive list items into a single block
    merged: list[str] = []
    for part in parts:
        stripped = part.strip()
        if _is_list_item_start(stripped) and merged:
            # Append to previous block to keep list together
            merged[-1] += part
        else:
            merged.append(part)

    return merged


def _split_by_separator(text: str, separator: str) -> list[str]:
    """Split text by separator, keeping separators at end of left part."""
    if separator == " ":
        return text.split()
    parts = text.split(separator)
    return [p + separator for p in parts[:-1]] + [parts[-1]] if len(parts) > 1 else [text]


def chunk_passage(
    text: str,
    passage_id: str,
    title: str,
    source_doc: str,
) -> list[Chunk]:
    """
    Split a passage into chunks respecting token limits, semantic boundaries,
    and document structure (Markdown headers, lists).

    Each chunk gets a `context_header` breadcrumb derived from the nearest
    preceding Markdown headers, enabling standalone comprehension.
    """
    text = text.strip()
    if not text:
        return []

    # ── Phase 1: Extract header positions for breadcrumb tracking ─────────
    headers = _extract_headers(text)

    # ── Phase 2: Check token count ────────────────────────────────────────
    token_count = _count_tokens(text)

    # Fast path: passage fits in one chunk
    if token_count <= MAX_TOKENS:
        header_stack: dict[int, str] = {}
        for level, header_text, _ in headers:
            # Clear deeper levels when a higher-level header appears
            keys_to_remove = [k for k in header_stack if k >= level]
            for k in keys_to_remove:
                del header_stack[k]
            header_stack[level] = header_text

        breadcrumb = _build_header_breadcrumb(header_stack, title)
        return [
            Chunk(
                text=text,
                title=title,
                source_doc=source_doc,
                passage_id=passage_id,
                chunk_index=0,
                token_count=token_count,
                context_header=breadcrumb,
            )
        ]

    # ── Phase 3: Slow path — split long passages ──────────────────────────
    chunks: list[Chunk] = []
    chunk_index = 0
    remaining = text

    # Track the header context as we consume the text
    header_stack: dict[int, str] = {}
    header_idx = 0  # pointer into sorted headers list

    while remaining:
        split_done = False
        for sep in SEPARATORS:
            if sep not in remaining:
                continue

            parts = _split_preserving_lists(remaining, sep)
            current: list[str] = []
            current_tokens = 0

            for part in parts:
                # Update header stack for any headers in this part
                for h_level, h_text, h_pos in headers[header_idx:]:
                    if h_text in part:
                        keys_to_remove = [k for k in header_stack if k >= h_level]
                        for k in keys_to_remove:
                            del header_stack[k]
                        header_stack[h_level] = h_text
                        header_idx += 1
                    else:
                        break

                part_tokens = _count_tokens(part)
                if current_tokens + part_tokens <= MAX_TOKENS:
                    current.append(part)
                    current_tokens += part_tokens
                else:
                    if current:
                        chunk_text = "".join(current).strip()
                        if chunk_text:
                            breadcrumb = _build_header_breadcrumb(
                                header_stack, title
                            )
                            chunks.append(
                                Chunk(
                                    text=chunk_text,
                                    title=title,
                                    source_doc=source_doc,
                                    passage_id=passage_id,
                                    chunk_index=chunk_index,
                                    token_count=_count_tokens(chunk_text),
                                    context_header=breadcrumb,
                                )
                            )
                            chunk_index += 1

                            # Compute overlap
                            overlap_parts: list[str] = []
                            overlap_tok = 0
                            for prev_part in reversed(current):
                                pt = _count_tokens(prev_part)
                                if overlap_tok + pt <= OVERLAP_TOKENS:
                                    overlap_parts.insert(0, prev_part)
                                    overlap_tok += pt
                                else:
                                    break
                            current = overlap_parts + [part]
                            current_tokens = overlap_tok + part_tokens
                    else:
                        # Single part exceeds MAX_TOKENS — force it as a chunk
                        chunk_text = part.strip()
                        if chunk_text:
                            breadcrumb = _build_header_breadcrumb(
                                header_stack, title
                            )
                            chunks.append(
                                Chunk(
                                    text=chunk_text,
                                    title=title,
                                    source_doc=source_doc,
                                    passage_id=passage_id,
                                    chunk_index=chunk_index,
                                    token_count=_count_tokens(chunk_text),
                                    context_header=breadcrumb,
                                )
                            )
                            chunk_index += 1
                        current = []
                        current_tokens = 0

            # Flush remaining parts
            if current:
                chunk_text = "".join(current).strip()
                if chunk_text:
                    breadcrumb = _build_header_breadcrumb(header_stack, title)
                    chunks.append(
                        Chunk(
                            text=chunk_text,
                            title=title,
                            source_doc=source_doc,
                            passage_id=passage_id,
                            chunk_index=chunk_index,
                            token_count=_count_tokens(chunk_text),
                            context_header=breadcrumb,
                        )
                    )
                    chunk_index += 1
            remaining = ""
            split_done = True
            break

        if not split_done:
            chunk_text = remaining.strip()
            if chunk_text:
                breadcrumb = _build_header_breadcrumb(header_stack, title)
                chunks.append(
                    Chunk(
                        text=chunk_text,
                        title=title,
                        source_doc=source_doc,
                        passage_id=passage_id,
                        chunk_index=chunk_index,
                        token_count=_count_tokens(chunk_text),
                        context_header=breadcrumb,
                    )
                )
            remaining = ""

    return chunks if chunks else [
        Chunk(
            text=text,
            title=title,
            source_doc=source_doc,
            passage_id=passage_id,
            chunk_index=0,
            token_count=_count_tokens(text),
            context_header="",
        )
    ]
