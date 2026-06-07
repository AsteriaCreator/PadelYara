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

## Voice
User-facing copy is in German, written in **Yara's voice** (see `.agents/yara-voice.md`): mean, competent, unbothered.
