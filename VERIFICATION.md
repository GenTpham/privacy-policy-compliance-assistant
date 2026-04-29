# Phase 6 End-to-End Verification Checklist

**Purpose:** Manual browser verification that the full Docker Compose stack works end-to-end.
Run this checklist after `docker compose up --build` or `make smoke-test`.

---

## Prerequisites

- [ ] `.env` file is populated with `OPENROUTER_API_KEY`, `JWT_SECRET_KEY`, and other required secrets
- [ ] `docker compose up --build` has completed (all services show as healthy in `docker compose ps`)
- [ ] No prior browser tabs have stale auth tokens (open a fresh private/incognito window)

---

## Step 1: Confirm All Services Are Healthy

Run:
```bash
docker compose ps
```

Expected output: all three services (`qdrant`, `backend`, `frontend`) show status `running (healthy)`.

- [ ] qdrant: running (healthy)
- [ ] backend: running (healthy)
- [ ] frontend: running (healthy)

---

## Step 2: Open the App

Open a browser and navigate to: **http://localhost**

Expected: The login page is displayed. The chat interface is NOT visible without logging in.

- [ ] Login page is displayed at http://localhost
- [ ] Navigating to http://localhost/chat redirects to the login page (ProtectedRoute working)

---

## Step 3: Login

Enter credentials for the seeded test user (from `.env` or seed script).

- [ ] Login form accepts username and password
- [ ] Clicking "Login" with correct credentials redirects to the chat interface
- [ ] Clicking "Login" with wrong credentials shows an error message (not a blank screen)

---

## Step 4: Policy Question — Streamed Answer with Citations

Type a policy question in Vietnamese or English, e.g.:

> chính sách nào áp dụng cho lưu trữ dữ liệu khách hàng

Submit the question.

- [ ] Response tokens appear progressively (character-by-character streaming — NOT all at once after a delay)
- [ ] The completed answer contains at least one citation card below the message
- [ ] Each citation card shows the source document title and a verbatim excerpt
- [ ] The answer does NOT contain fabricated document names

---

## Step 5: Conflict Query — Verdict Classification

In the same session, send a conflict query using the Phase 5 trigger keyword:

> mâu thuẫn về chính sách lưu trữ dữ liệu

- [ ] The response uses the conflict-detection format (Verdict: CONTRADICTORY / CONSISTENT / ONE-SILENT)
- [ ] The response cites passages from at least two different source documents
- [ ] Each cited passage includes a document title and chunk ID
- [ ] The previous chat context (Step 4 question) is still visible above this response

---

## Step 6: No-Match Message

Send a question that is entirely unrelated to privacy policies, e.g.:

> What is the recipe for chocolate cake?

- [ ] The response shows a "No matching policy found" message (or equivalent)
- [ ] The LLM does NOT hallucinate a policy answer

---

## Step 7: Logout

Click the logout button (top-right of chat interface).

- [ ] The browser returns to the login page
- [ ] Running `curl -H "Authorization: Bearer <old_token>" http://localhost/api/chat` returns HTTP 401
- [ ] Refreshing http://localhost shows the login page (tokens are cleared)

---

## Step 8: Restart Persistence

Stop and restart the stack:

```bash
docker compose down
docker compose up -d
```

Wait for healthy, then log in again and send a policy question.

- [ ] Previously indexed passages are still queryable (data persisted in qdrant_storage volume)
- [ ] No re-ingestion step was required

---

## Checklist Complete

All items checked = Phase 6 verification PASSED.

If any item fails, note the failing step and open a bug. Do not mark Phase 6 complete until all items pass.
