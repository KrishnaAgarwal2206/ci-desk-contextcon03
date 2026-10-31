# DEMO PLAN — Persona-aware Competitive Intelligence Desk

Repo + Loom due **15:30 IST**. **HARD LIMIT: the video is 2:00. The script ends at 1:55.**
Every value below was read from the running app (`/requests/5`, `/requests/4`, `/`) at about 15:00 IST.

---

## 1. THE 2-MINUTE LOOM SCRIPT (main deliverable)

Pace is about 2.5 words per second, and every line fits its slot. **Nothing waits for a live run.** You submit the brief live, then cut straight to request #5, which ran earlier today, and you say that out loud.

| Time | Len | Screen / tab | Action | Voiceover (say exactly) | Words | Rubric |
|---|---|---|---|---|---|---|
| 0:00–0:06 | 6 s | Landing `/` | — | "Companies pay analysts to watch competitors and brief each stakeholder. This desk does that job." | 14 | Customer value (20) |
| 0:06–0:14 | 8 s | Landing | Paste the brief (section 2), click **Run research** | "A brief it has never seen: three vector-database companies, five stakeholders. A run takes about eighty seconds." | 17 | End-to-end (25) |
| 0:14–0:20 | 6 s | Switch to the `/requests/5` tab | — | "So here's the same pipeline's run from earlier today: Cursor, Cognition, Replit." | 13 | Demo honesty (15) |
| 0:20–0:30 | 10 s | **Overview**, KPI strip | Point along the strip | "Three of three resolved, nine developments, seventy-four cited evidence records, 14.85 Crustdata credits, five cents of LLM." | 17 | End-to-end (25) |
| 0:30–0:42 | 12 s | Overview, *Canonical companies* | Hover ID `820671` | "Identify returns canonical IDs. Ambiguous names aren't guessed. Earlier, 'Sierra' had twelve candidates, and a reviewer picked sierra.ai." | 19 | Facts (20), Robustness (20) |
| 0:42–0:48 | 6 s | Overview, *Notes, failures & unknowns* | Point at "Cursor: 25 enrich news items dropped" | "Off-entity news is dropped and counted, never hidden." | 8 | Robustness (20) |
| 0:48–0:58 | 10 s | Overview, **stakeholder matrix** | Hover the top row (Cognition funding) | "One shared event, Cognition weighing a seventy-to-eighty-billion round, scores 0.47 for VC and 0.14 for Talent." | 17 | Customer value (20) |
| 0:58–1:12 | 14 s | **Stakeholder briefs**, VC tab | Show the card "Cognition mega-round in view", click **E353** | "Each stakeholder gets insight cards: implication, action, confidence. Citations are validated. E353 opens the source with its retrieval time. Facts are cited; interpretation is labelled." | 25 | Facts (20) |
| 1:12–1:30 | 18 s | **Governance** | Type a reviewer name, click **Create proposal** (the VC text is pre-filled) | "Plain-English feedback becomes a typed proposal, pending review. Nothing changes yet. Here's the diff, and a replay on stored events." | 21 | Customer value (20), Robustness (20) |
| 1:30–1:40 | 10 s | Governance | Click **Approve → new vc_partner version** | "A named reviewer approves. That creates a new immutable VC policy version. The other four personas don't change." | 17 | Customer value (20) |
| 1:40–1:48 | 8 s | **Monitoring** | Point at "Crustdata watch ID 56281" | "One shared Crustdata Watcher. It runs weekly with a thirty-day SLA. Scheduled, not real time." | 14 | End-to-end (25) |
| 1:48–1:55 | 7 s | **Execution trace** | Scroll the Crustdata calls | "Every call is logged with its credits. When an LLM call failed, it fell back to labelled templates instead of breaking." | 14 | Robustness (20), Demo (15) |
| 1:55 | — | — | **Stop recording** | — | — | 5 s buffer |

**Editing rules:**
- The proposal and approve clicks each take about 5 s and 1 s. If the proposal is slow, pause the Loom and resume.
- Do one dry run with a stopwatch. If you're over 1:55, drop the 0:42 Notes line first, then trim the 0:30 Sierra sentence.
- If your live run happens to finish before 0:14, you can show its KPI strip instead. Read its numbers and don't use #5's.

---

## 2. Pre-recording checklist (do it before recording)

**Brief to paste (in your clipboard):**
> Track the vector database market: pinecone.io, weaviate.io and qdrant.tech. Hiring, leadership, funding, launches and partnerships for Strategy, VC, R&D, Sales and Recruiting.

It uses domains so the companies resolve. The run takes about 70–90 s and costs about 15 credits, $0.05 and one new Watcher. Let it finish off camera. It shows up in the "Recent research" list on `/`.

**State reset. VC is at policy v2 right now** (approved by "Demo Reviewer", rule `suppress junior_hiring`):
- **(A) Recommended:** on `/requests/5#stakeholders`, open the VC tab and click **"Roll back to v1 (creates new version)"**. That makes v3. Your live approval will then make v4, so say "new version", not "v2".
- **(B)** Delete `contextcon03.db` and restart. **This also deletes fallback #5 and #4**, so don't do it.
- **(C)** No reset. At 1:12, approve the pending **Talent Proposal #2** instead (`leadership_change 0.8 → 1.0`, `+ suppress news_mention`) and say "Talent" instead of "VC".

**Tabs (one window):** `/` with an empty textarea, `/requests/5` on Overview, and `/requests/4` as an optional backup for Sierra.
**Zoom** 110–125 %. **Hide** the terminal, editor, `.env`, bookmarks bar and notifications.
**Check** `curl http://127.0.0.1:8000/health` returns `crustdata: live`, `llm: llm:claude-sonnet-5-5`, `webhook: pull-only`.

---

## 3. "Do not say"

| Don't say | Say instead |
|---|---|
| LLM judge / "AI verifies facts" | "Citations are validated against stored evidence." |
| "Alerts the VC on Slack/email" | "Above-threshold events are flagged in the app." |
| "Real-time monitoring" | "Scheduled weekly, 30-day SLA, pull reconciliation." |
| "The Watcher detected a change" | "No change event has arrived yet; the baseline is a snapshot, not an event." |
| Supply-chain persona, auth/RBAC, backtesting, forecasting | "Five personas; a named reviewer; replay on stored events." |
| Person Enrich / Web Fetch | "Person Search and Web Search." |
| "Cursor was bought by SpaceX" as fact | "Public sources report…" |
| Calling #5 "the run I just started" | "The same pipeline's run from earlier today." |

---

## 4. Risk / backup

| Failure | Backup |
|---|---|
| Live run slow or erroring | The script already cuts to #5. Just continue. |
| Proposal creation slow or invalid | Pause the Loom, or approve the pending Talent Proposal #2 instead. |
| Brief shows a template, not `llm:` | "The LLM was unavailable, so this is the labelled fallback; ranking is unchanged." |
| Server down | Restart `uvicorn app.main:app --reload`. Don't delete the DB. |
| A key appears on screen | Re-record. |

---

## 5. Five-minute finals (short)

1. **(0:00–0:30) Who pays:** enterprise CI and strategy teams, consultancies, and VC funds paying associates and data subscriptions for competitor and portfolio tracking.
2. **(0:30–1:00) Live brief:** submit it. While it runs, show the hardest case, `/requests/4`. "Sierra" had 12 candidates (sierra.ai 1128961, sierra.com 1161138, sierratextiles.com 3713584), and a reviewer picked one.
3. **(1:00–2:00) Results:** KPI strip → IDs → matrix → VC card → E353 → Evidence row E307 (Cognition `series_e`, $2.0B, 2026-09-08, from Enrich).
4. **(2:00–2:30) Score breakdown:** `0.55 × 0.6 × 0.85 = 0.281`, threshold 0.3. Ranking is deterministic; the LLM only phrases.
5. **(2:30–3:30) Governance:** proposal → clamp warnings → diff → replay (Proposal #1: 75 events, alerts 34 → 33, Clay GTM rank 16 → 8) → approve → rollback.
6. **(3:30–4:15) Watcher 56281:** `every_hours 168`, `refresh_frequency_days 30`, ≤25 results. Baseline runs `run_488288` and `run_488411` were stored as baseline samples, not as events.
7. **(4:15–5:00) Trace and tests:** 18 Crustdata calls, all 200/201, 14.85 credits. One synthesis `http_400` was recovered. `pytest -q` gives 19 passing tests, with 402/403/429/malformed/webhook cases mocked.

### Judge Q&A (crisp)
1. **Why Watcher?** One shared watch over all the competitors. It's free until something changes (5 credits per changed company per run), versus re-polling Enrich at about 2 credits per company every time.
2. **How are facts verified?** Each record stores its URL or Crustdata endpoint + ID + field, the source date and the retrieval time. Citations are validated and uncited insights dropped. News below 0.93 match confidence is dropped. There is no LLM judge.
3. **Ambiguous names?** They stay `ambiguous`, the candidates are shown, and a reviewer clicks "use this" (#4).
4. **402 / 429 / failure?** 429 and 5xx are retried with backoff. 402 and 403 stop and get recorded. There's a 150-credit run cap. LLM failures fall back to labelled templates. All of this is pytest-covered.
5. **Why governance?** One persona's feedback must never silently change another's ranking. Changes are validated, diffed, replayed, approved by name, versioned and reversible.
6. **Cost per run?** About 15 credits (#5: Enrich 6.0, Person 4.95, Web 3.0, Jobs 0.9, Identify 0) plus about $0.05 of LLM.
7. **What failed?** LLM `max_tokens` and "grammar too large" errors (fixed with an array schema plus a fallback). The Watcher test returns 400 for pull watches (that button is now hidden). Off-entity news like "Umecrine Cognition" (fixed with the 0.93 filter; some noise remains and is visible).
8. **Real-time? Alerts?** No. It's a weekly schedule, and alerts are in-app threshold flags only.
9. **Testing?** 19 mocked pytest tests and five live end-to-end runs today.
10. **What's next, and why not now?** A public HTTPS webhook (the receiver is built), Slack/email routing, auth/RBAC, Person Enrich and Web Fetch, and watch PATCH. Time-boxed: we prioritized provenance and governance.
