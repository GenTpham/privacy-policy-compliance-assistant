---
phase: 4
slug: web-frontend
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-27
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | vitest 4.1.5 + happy-dom |
| **Config file** | `frontend/vite.config.ts` (test block) — Wave 0 installs |
| **Quick run command** | `cd frontend && npx vitest run --reporter=verbose` |
| **Full suite command** | `cd frontend && npx vitest run --reporter=verbose --coverage` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx vitest run --reporter=verbose`
- **After every plan wave:** Run `cd frontend && npx vitest run --reporter=verbose --coverage`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 0 | UI-01 | — | N/A | scaffold | `cd frontend && npm run build` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 1 | UI-02 | T-4-01 | JWT stored in memory (not localStorage) | unit | `cd frontend && npx vitest run src/__tests__/auth.test.tsx` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 1 | UI-03 | T-4-02 | Unauthenticated routes redirect to /login | unit | `cd frontend && npx vitest run src/__tests__/routing.test.tsx` | ❌ W0 | ⬜ pending |
| 4-03-01 | 03 | 2 | UI-04 | — | N/A | unit | `cd frontend && npx vitest run src/__tests__/chat.test.tsx` | ❌ W0 | ⬜ pending |
| 4-03-02 | 03 | 2 | UI-05 | — | SSE stream parsed correctly; no auth header leakage | unit | `cd frontend && npx vitest run src/__tests__/streaming.test.tsx` | ❌ W0 | ⬜ pending |
| 4-04-01 | 04 | 2 | CITE-04 | — | N/A | unit | `cd frontend && npx vitest run src/__tests__/citations.test.tsx` | ❌ W0 | ⬜ pending |
| 4-04-02 | 04 | 2 | UI-06 | — | N/A | unit | `cd frontend && npx vitest run src/__tests__/no-match.test.tsx` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/src/__tests__/auth.test.tsx` — stubs for UI-02 (login flow, JWT handling)
- [ ] `frontend/src/__tests__/routing.test.tsx` — stubs for UI-03 (protected route redirect)
- [ ] `frontend/src/__tests__/chat.test.tsx` — stubs for UI-04 (chat interface render)
- [ ] `frontend/src/__tests__/streaming.test.tsx` — stubs for UI-05 (SSE stream parsing)
- [ ] `frontend/src/__tests__/citations.test.tsx` — stubs for CITE-04 (citation card render/expand)
- [ ] `frontend/src/__tests__/no-match.test.tsx` — stubs for UI-06 (no-match message display)
- [ ] `frontend/vite.config.ts` — vitest config block with happy-dom environment
- [ ] `npx shadcn@latest init` — Wave 0 blocker; components.json does not exist

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Streaming tokens appear progressively in browser | UI-05 | SSE visual rendering requires a live browser | `docker compose up`, submit a question, verify tokens appear character-by-character |
| Login page redirect for unauthenticated visit | UI-02 | Requires a running backend returning 401 | Open app without token, verify redirect to /login |
| Logout clears session; next chat request returns 401 | UI-03 | Requires backend + token invalidation in full stack | Log in, log out, open DevTools Network tab, re-submit a question, verify HTTP 401 |
| Citation card expand/collapse interaction | CITE-04 | Visual click-through interaction | Click a citation card, verify it expands to show full excerpt |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
