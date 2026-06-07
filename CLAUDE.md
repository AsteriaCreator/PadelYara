# PadelYara — working notes for Claude

## Stack & hosting
- **Frontend:** React + TypeScript + Vite + Tailwind, deployed on **Vercel** (https://www.padelyara.at).
- **Backend:** FastAPI (Python), deployed on **Railway**. **Render is fully retired — never reference, restore, or suggest it.**
- **Database:** MongoDB Atlas (db `padel_checker`).

## Running locally
Both servers must be up or the frontend's API calls fail (the page looks broken):
- **Frontend:** `npm run dev` → http://localhost:5173
- **Backend:** `npm run backend` → http://localhost:8000 (root `.env` points the frontend here)

Both are registered in `.claude/launch.json` (`frontend`, `backend`). The preview tool does **not** auto-start the backend — start it too. Local Python is 3.14: `pip install -r Backend/requirements.txt` fails (`greenlet` has no 3.14 wheel); the backend needs `apscheduler` installed or startup crashes.

## Tooling — prefer MCPs over manual work
- **Local UI verification:** use the **Claude Preview** tools (`preview_*`) — they start the dev server, read console/network/server logs, and screenshot. Never ask the user to check the browser manually.
- **Live / deployed URLs** (padelyara.at, Vercel previews): use the **Playwright** MCP to navigate and inspect.
- **Database:** query MongoDB via the **MongoDB MCP**, not throwaway Python scripts.
- **Deploys & logs:** use the **Railway** and **Vercel** MCPs to check deploy status and runtime logs instead of guessing.

## Scraper consistency rule
When fixing or adding a feature in any scraper (`eversports_service.py`, `eversports_prices.py`, `etennis_checker.py`, `tennis04_checker.py`) — **always check whether the same fix or feature is needed in all other scrapers too**, and apply it if so. Examples: a parsing bug, a URL date param, a missing field, a caching pattern. Don't assume platforms behave differently without checking.

Also applies to the **Dockerfile**: any new Backend `.py` file must get a `COPY` line and be added to the build-time import check.

## Working style & permissions
The user works things out in chat first and finds the harness permission popups redundant. She is a beginner, so don't make her judge flagged commands — give a plain-language safe/unsafe verdict, and rewrite commands that can't be allowlisted (`$()`, backticks, brace expansion, etc.) into a safe equivalent.

**Just do it — batched, no asking:** edit/create/read files, search code, run the app locally, tests, typecheck, read the database, read logs, and local git (`status`, `diff`, `log`, `commit`).

**Commit + push = one step for agreed changes.** When we've discussed a change and it's verified (typecheck/preview passes), commit **and** push it together, then tell her it's deploying and live on padelyara.at in ~1–3 min. Do **not** re-ask about pushing something we already agreed on — that gap (committed but not pushed → "it's not on the site") is the exact thing to avoid. Remember: push → GitHub → auto-deploy is what makes a change go live.

**Stop and ask her in chat first (plain words, not a popup)** only for genuinely consequential or irreversible actions:
- Deleting files, or deleting/clearing/dropping anything in MongoDB
- Mass writes to the **production** database (bulk update/insert/delete)
- `git push --force`, deleting branches, history rewrites
- Risky/experimental changes I'm unsure about, or anything not clearly agreed yet

## Voice
User-facing copy is in German, written in **Yara's voice** (see `.agents/yara-voice.md`): mean, competent, unbothered.
