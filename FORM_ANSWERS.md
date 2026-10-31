# Hackathon form answers (copy-paste ready)

## Team name
<TEAM NAME>

## One line
Turns a plain-English competitor brief into cited, stakeholder-specific intelligence briefs from live Crustdata, and learns from feedback only through reviewed, versioned policy changes.

## Theme
Research and Markets (secondary: Investing)

## GitHub repo
https://github.com/KrishnaAgarwal2206/ci-desk-contextcon03

## Demo video
<LOOM/YOUTUBE LINK>

## How does your product work?

**(a) The service it replaces.** Competitive-intelligence analysts and research services: someone resolves which companies a brief means, pulls headcount, funding, hiring, leadership and news, and writes separate takeaways for strategy, investors, R&D, sales and recruiting. It takes days, sources get lost, and one feedback comment quietly changes everyone's output.

**(b) Engineering approach and models.** A FastAPI + SQLite/SQLAlchemy app (HTTPX, Jinja2 + vanilla JS, 20 pytest tests). Claude (`claude-sonnet-5-5`) does three bounded jobs: plan the research, write rich briefs for all five stakeholders (Strategy/CI Lead, VC Partner, R&D/Technology, Sales/Marketing, Talent/Recruiting), and turn feedback into a typed policy proposal. Spend is capped at $5, with a labelled deterministic fallback when the LLM is unavailable. Crustdata calls, all live-verified: Company Identify, Search and Enrich, Person Search, Job Search, Web Search, account credits/endpoints, and a shared company Watcher (create, read-back, run-history reconciliation). Every evidence record keeps its source and retrieval time. Claims are deduplicated into shared events, then each persona's versioned policy scores them. Brief citations are checked against stored records, and uncited insights are dropped. A fresh run costs about 15 Crustdata credits and $0.04–0.05 of LLM. Feedback goes through a governed flow: natural-language feedback → pending proposal → deterministic validation → diff → replay on stored events → approval by a named reviewer → a new immutable policy version for that persona only.

What failed and what we learned: name-only lookup is unreliable. "Sierra" returned 12 candidates, all at confidence 1.0, so we never guess; a reviewer picks one. Enrich news mixed in GMC Sierra truck stories, and Crustdata's per-article match confidence let us filter them (we keep ≥0.93). Early LLM calls hit max_tokens and schema-size limits; an array schema and a fallback fixed that.

**(c) With more time.** Receive and score real Watcher change events through a public webhook. Add Person Enrich, Web Fetch, and person/job watches with credit approval. Add alert delivery, auth/RBAC for reviewers, more personas (e.g. supply chain), historical backtesting of policy changes, and an LLM-as-a-judge quality check.

## High-level diagram
https://github.com/KrishnaAgarwal2206/ci-desk-contextcon03/blob/master/docs/ARCHITECTURE_DIAGRAM.md

(Note: this link works only after `docs/ARCHITECTURE_DIAGRAM.md` is committed and pushed to `master`.)
