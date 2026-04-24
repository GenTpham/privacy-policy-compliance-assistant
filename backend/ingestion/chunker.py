"""
backend/ingestion/chunker.py
Text splitting for privacy policy passages.
Splits passages exceeding MAX_TOKENS into semantically coherent chunks.
Most dataset passages fit within MAX_TOKENS and are returned as a single chunk.
"""
import re
from dataclasses import dataclass

import tiktoken

MAX_TOKENS = 400      # target chunk size (AI-SPEC §4 Context Window Strategy)
OVERLAP_TOKENS = 50   # ~12.5% overlap — preserves clause continuity at boundaries
SEPARATORS = ["\n\n", "\n", ". ", " "]  # priority order — paragraph → sentence → word

_enc = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    text: str
    title: str
    source_doc: str
    passage_id: str
    chunk_index: int
    token_count: int


def _count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def _split_by_separator(text: str, separator: str) -> list[str]:
    """Split text by separator, keeping separators at end of left part (preserve structure)."""
    if separator == " ":
        return text.split()
    parts = text.split(separator)
    # Re-attach the separator to the end of each part except the last
    return [p + separator for p in parts[:-1]] + [parts[-1]] if len(parts) > 1 else [text]


def _is_list_item_start(text: str) -> bool:
    """
    Detect if text begins a numbered/lettered list item.
    Atomic unit rule: list items must not be split from their context.
    """
    return bool(re.match(r"^\s*(\d+\.|[a-z]\)|[a-z]\.|[(][a-z][)]|\*|\-)\s", text, re.IGNORECASE))


def chunk_passage(
    text: str,
    passage_id: str,
    title: str,
    source_doc: str,
) -> list[Chunk]:
    """
    Split a passage into chunks respecting token limits and semantic boundaries.
    If the passage fits within MAX_TOKENS, returns a single chunk (most dataset records).
    """
    token_count = _count_tokens(text)

    # Fast path: passage fits in one chunk — most dataset records take this path
    if token_count <= MAX_TOKENS:
        return [
            Chunk(
                text=text.strip(),
                title=title,
                source_doc=source_doc,
                passage_id=passage_id,
                chunk_index=0,
                token_count=token_count,
            )
        ]

    # Slow path: split long passages using separator hierarchy
    chunks: list[Chunk] = []
    chunk_index = 0
    remaining = text.strip()

    while remaining:
        # Try each separator in priority order to find a split point within MAX_TOKENS
        split_done = False
        for sep in SEPARATORS:
            if sep not in remaining:
                continue
            parts = _split_by_separator(remaining, sep)
            current: list[str] = []
            current_tokens = 0

            for part in parts:
                part_tokens = _count_tokens(part)
                if current_tokens + part_tokens <= MAX_TOKENS:
                    current.append(part)
                    current_tokens += part_tokens
                else:
                    if current:
                        chunk_text = "".join(current).strip()
                        if chunk_text:
                            chunks.append(
                                Chunk(
                                    text=chunk_text,
                                    title=title,
                                    source_doc=source_doc,
                                    passage_id=passage_id,
                                    chunk_index=chunk_index,
                                    token_count=_count_tokens(chunk_text),
                                )
                            )
                            chunk_index += 1

                            # Compute overlap: take last OVERLAP_TOKENS of current chunk
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
                            chunks.append(
                                Chunk(
                                    text=chunk_text,
                                    title=title,
                                    source_doc=source_doc,
                                    passage_id=passage_id,
                                    chunk_index=chunk_index,
                                    token_count=_count_tokens(chunk_text),
                                )
                            )
                            chunk_index += 1
                        current = []
                        current_tokens = 0

            # Flush remaining
            if current:
                chunk_text = "".join(current).strip()
                if chunk_text:
                    chunks.append(
                        Chunk(
                            text=chunk_text,
                            title=title,
                            source_doc=source_doc,
                            passage_id=passage_id,
                            chunk_index=chunk_index,
                            token_count=_count_tokens(chunk_text),
                        )
                    )
                    chunk_index += 1
            remaining = ""
            split_done = True
            break

        if not split_done:
            # No separators found — treat entire remaining as one chunk
            chunk_text = remaining.strip()
            if chunk_text:
                chunks.append(
                    Chunk(
                        text=chunk_text,
                        title=title,
                        source_doc=source_doc,
                        passage_id=passage_id,
                        chunk_index=chunk_index,
                        token_count=_count_tokens(chunk_text),
                    )
                )
            remaining = ""

    return chunks if chunks else [
        Chunk(
            text=text.strip(),
            title=title,
            source_doc=source_doc,
            passage_id=passage_id,
            chunk_index=0,
            token_count=_count_tokens(text),
        )
    ]
