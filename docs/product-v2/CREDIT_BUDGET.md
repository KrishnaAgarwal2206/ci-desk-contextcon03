# CREDIT BUDGET

- User-reported entitlement: ~US$4,500 equivalent. **Not converted.** Event deck separately mentions 15,000 credits per builder. Truth = `GET /account/credits` (free).
- Prices: `GET /account/endpoints` (free) for API endpoints; it does **not** include watch prices — use the public pricing table only as an *estimate*, labelled as such, and the watch's own `credits_consumed` counter as actual.
- Actual spend = sum of `X-Credits-Used` per response, stored in `api_call.credits_used`.

## Per-run defaults (configurable in `.env`)
| Control | Default |
|---|---|
| Run cap | 150 credits |
| Companies resolved | ≤ 6 |
| Company enrich | ≤ 6, field groups: basic_info, headcount, funding, news (+people if allowed) |
| Job search | ≤ 25 results / company |
| Person search | ≤ 10 / company; person enrich ≤ 3 total |
| Web search | ≤ 2 queries / company; web fetch ≤ 3 pages total |
| Watches | 1 company entity watch / request, ≤ 10 entities, `every_hours` 168, `max_results_per_run` 25, 30-day SLA |

Public-list estimate for a 6-company run: well under 150 credits [estimate, not account price].

## Hard rules
No `is_realtime`, no `refresh_frequency_days < 30`, no broad discovery watches without explicit separate approval showing the estimate. Use free test/baseline for plumbing; do not create repeated watches to simulate signals. Stop on 402. Cancel/delete demo watches after the event if not needed. Runtime LLM cost is tracked separately and is not part of the Crustdata budget.
