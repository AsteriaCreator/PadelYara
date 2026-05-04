IMPORTANT:
Eversports availability is NOT reliable.
Never treat "free" as actual availability.
Always map to platform_check_required unless proven otherwise.

Current state:
- Eversports availability marked as platform_check_required
- Backend stable after clean restart
- eTennis working

Known issues:
- Concurrency / multiple scrape batches unclear
- Some Eversports still return pending or check_failed

Next tasks:
1. Ensure only ONE scrape batch per request globally
2. Remove any leftover background polling
3. Optimize response time (<5s target)
4. Verify Eversports fallback behavior cleanly

Constraints:
- Do NOT rework Eversports scraping logic
- Do NOT rewrite backend
- Work incrementally