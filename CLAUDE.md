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
- **Local UI verification:** use the **Claude Preview** tools (`preview_*`) — they start the dev server, read console/network/server logs, and inspect the DOM. Never ask the user to check the browser manually.
  - **Screenshots: don't use `preview_screenshot` locally — it hangs/times out on Windows.** The preview renders in a hidden Electron window; Windows freezes the renderer when the window is hidden (rAF stops, no frame to capture). To *see* the local site, drive **Playwright MCP** against `http://localhost:5173` (`browser_navigate` + `browser_take_screenshot`) — verified working. The other `preview_*` tools (console/network/DOM/eval) are fine.
- **Live / deployed URLs** (padelyara.at, Vercel previews): use the **Playwright** MCP to navigate and inspect.
- **Database:** query MongoDB via the **MongoDB MCP**, not throwaway Python scripts.
- **Deploys & logs:** use the **Railway** and **Vercel** MCPs to check deploy status and runtime logs instead of guessing.

## Scraper consistency rule
When fixing or adding a feature in any scraper (`eversports_service.py`, `eversports_prices.py`, `etennis_checker.py`, `tennis04_checker.py`) — **always check whether the same fix or feature is needed in all other scrapers too**, and apply it if so. Examples: a parsing bug, a URL date param, a missing field, a caching pattern. Don't assume platforms behave differently without checking.

Also applies to the **Dockerfile**: any new Backend `.py` file must get a `COPY` line and be added to the build-time import check.

## Working style & permissions
General working-style and permission rules live in the **global `~/.claude/CLAUDE.md`** (plain-language command verdicts, batch mechanical actions without asking, commit+push agreed changes together, and the stop-and-ask list). PadelYara specifics on top of that:
- **"Verified" before push** = typecheck + preview pass.
- **After push:** the change is live on **padelyara.at** in ~1–3 min (push → GitHub → Vercel/Railway auto-deploy).
- **The production database to never touch carelessly** is MongoDB Atlas `padel_checker`.

## Voice
User-facing copy is in German, written in **Yara's voice** (see `.agents/yara-voice.md`): mean, competent, unbothered.
