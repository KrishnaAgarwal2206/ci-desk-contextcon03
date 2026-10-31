# SOURCE DECISIONS

## Sources inspected (31 Oct 2026)
| Source | Location | Used for |
|---|---|---|
| PM Verdict (authoritative) | `PM_Verdict_ContextCon03_v2.docx` | All product decisions |
| Problem statement | `ContextCon PS - CrustData.pdf` (5 pp.) | Original rules, API list, criteria |
| Event deck | `ContextCon 03_ IIT Bombay · Event Deck (1).pptx (1).pdf` | Rules, schedule, rubric, README/Loom guidance, MCP |
| Themes deck | `ContextCon 03- IIT Bombay · The Themes.pptx` | Research & Markets, Investing |
| Legacy CI docs | `Competitive-Intelligence-Docs/` (already extracted; no ZIP present in the project dir) — 50 HTML pages | Blueprint only; **no application source code** |
| Crustdata docs | `https://docs.crustdata.com/llms.txt` + Watcher, pricing, credits, permissions, rate-limits, best-practices pages | Verified API facts |
| Photo | `WhatsApp Image 2026-10-31 at 10.12.53 AM.jpeg` | Not required for decisions |
| Event page | https://events.ycombinator.com/lczadh0gm | Not fetched (time-box); deck is the more detailed source |

## Discrepancies and resolutions
1. **Crustdata mandatory vs optional.** PS PDF rule 3: "Every participating team must utilize Crustdata's API keys and identity graph." Event deck "Rules" slide (labelled 33): "Using Crustdata is optional"; FAQ slide (43): "Every project is judged on the same five criteria, with or without it." **Resolution:** the later event deck governs the rules. We use Crustdata deeply anyway as a **product strategy choice** — it is the strongest identity/data substrate and Watcher is the recommended ingestion layer.
2. **Judging criteria.** PS lists four criteria without weights; deck slide 38 lists five weighted criteria (25/20/20/20/15). **Resolution:** the deck rubric is definitive.
3. **Credits.** User reports ~US$4,500 of credits; deck says 15,000 credits per builder; PS says $1,500 per team. **Resolution:** never convert or assume; `GET /account/credits` is the only source of truth.
4. **Page count.** Audit prompt mentions 98 legacy HTML pages; the archive contains 50 `.html` files. Immaterial — no legacy pages are edited.
5. **ZIP.** `Competitive-Intelligence-Docs.zip` is not in the project directory; the extracted folder is. Originals left untouched; copy at `docs/competitive-intelligence-v2/`.

## Verified Crustdata facts (vs assumptions)
See `CRUSTDATA_INTEGRATION.md` and `WATCHER_INGESTION.md`. Items there marked **[VERIFY-LIVE]** must be confirmed against a real response during preflight before code depends on them.

## Legacy-doc facts relied on [LEGACY]
- Stack direction: Python/FastAPI, SQLite, SQLAlchemy.
- `POST /admin/feedback/nl-command` executes mutations immediately; `proposals_created` always empty (`reference/api/feedback-governance.html`).
- `approve_proposal` activates regardless of `risk_level`.
- Single active `ScoringWeightProfile`; impact prompt hardcoded to Godrej/FMCG.
- Two non-unified suppression systems; missed/false-negative feedback has no proposal builder.
- Release notes: server only enqueues jobs; no worker consumes them in server mode.
