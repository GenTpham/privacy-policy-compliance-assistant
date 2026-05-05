# Phase 8: Corpus Expansion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 08-corpus-expansion
**Areas discussed:** PDF extraction library, Document chunking strategy, CLI design, Validation scope

---

## PDF Extraction Library

### Library choice

| Option | Description | Selected |
|--------|-------------|----------|
| pypdf (Recommended) | Pure Python, no C dependencies, easy Docker build. PdfReader API. | ✓ |
| pdfplumber | Better for multi-column/table-heavy PDFs. Heavier dependency tree. | |
| pdfminer.six | Low-level, most control. Verbose API. | |

**User's choice:** pypdf
**Notes:** Policy documents have standard text layout — pypdf is sufficient.

### Multi-page handling

| Option | Description | Selected |
|--------|-------------|----------|
| Concatenate all pages (Recommended) | Join pages with `\n\n`, pass whole-doc text to `chunk_passage()`. | ✓ |
| Page-by-page | Each page text → its own `chunk_passage()` call. | |

**User's choice:** Concatenate all pages

### Empty text handling

| Option | Description | Selected |
|--------|-------------|----------|
| Hard fail with clear error (Recommended) | Raise error if zero text extracted (scanned/encrypted PDF). | ✓ |
| Warn and skip empty pages | Log warning per empty page, continue with rest. | |
| Hard fail only if zero total text | Allow empty pages, fail only if entire doc has no text. | |

**User's choice:** Hard fail with clear error

---

## Document Chunking Strategy

### passage_id assignment

| Option | Description | Selected |
|--------|-------------|----------|
| Filename stem (Recommended) | passage_id = filename without extension. Readable, stable. | ✓ |
| UUID generated at ingest time | Random UUID4 per run. Harder to trace to source. | |
| Filename + page range | More precise but adds complexity. | |

**User's choice:** Filename stem

### file_type payload field

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, add file_type (Recommended) | Payload gets `file_type='pdf'` or `'txt'`. Supports future filtering. | ✓ |
| No, keep payload unchanged | Simpler, no schema change. | |

**User's choice:** Yes, add file_type

### TXT file handling

| Option | Description | Selected |
|--------|-------------|----------|
| Same pipeline as PDF (Recommended) | Read entire TXT, pass to `chunk_passage()`. Consistent. | ✓ |
| TXT = one passage per paragraph | Split on double newlines. Assumes pre-formatted TXT. | |

**User's choice:** Same pipeline as PDF

---

## CLI Design

### Title/source_doc assignment

| Option | Description | Selected |
|--------|-------------|----------|
| --title required arg (Recommended) | Admin names the source explicitly. Prevents filename-derived names. | ✓ |
| Infer from filename | Simpler but admin must name files carefully. | |
| --title optional, filename as fallback | Flexible but risks inconsistent naming. | |

**User's choice:** --title required arg

### Script structure

| Option | Description | Selected |
|--------|-------------|----------|
| Separate module: ingest_doc.py (Recommended) | Clean separation. Existing ingest.py untouched. | ✓ |
| Extend existing ingest.py | Single entry point but shared file complicates both paths. | |

**User's choice:** Separate module: ingest_doc.py

### Dry-run flag

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, add --dry-run (Recommended) | Shows chunk count and dedup hits without writing to Qdrant. | ✓ |
| No, skip dry-run | Dedup is idempotent anyway. | |

**User's choice:** Yes, add --dry-run

---

## Validation Scope

### Script placement

| Option | Description | Selected |
|--------|-------------|----------|
| Separate script: validate_corpus.py (Recommended) | Validates entire collection. Admin can run anytime. | ✓ |
| --validate flag on ingest_doc.py | Convenient but collection-wide validation coupled to file-specific script. | |

**User's choice:** Separate script: validate_corpus.py

### Report sections

| Option | Description | Selected |
|--------|-------------|----------|
| Total passage count | Overall Qdrant point count. | ✓ |
| Per-source breakdown | Count by source_doc, sorted descending. | ✓ |
| Sample metadata rows | 5 random payload rows. | ✓ |
| Anomaly flags | Zero-length text, missing fields, token_count=0 or >500. | ✓ |

**User's choice:** All four sections

---

## Claude's Discretion

- Exact argparse error messages and help strings
- Whether to use `qdrant.scroll()` or `qdrant.count()` for dry-run dedup check
- Output formatting (plain text with `[section]` headers — match existing ingest.py style)
- validate_corpus.py sampling approach (scroll with limit=5 vs first 5)

## Deferred Ideas

- OCR support for scanned PDFs — would require tesseract; not needed for v2.0
- End-user PDF upload via chat UI — explicitly out of scope (v3.0, CORP-03/04)
- Per-document ingestion history log — useful but not required by CORP-01/02
- validate_corpus.py --source filter flag — full-collection validation sufficient for v2.0
