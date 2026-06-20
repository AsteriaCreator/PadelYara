# Yara Social Playbook

Yara's social media setup, connected accounts, and posting workflow.

## Connected Platforms (via Composio MCP)

| Platform | Account | Status |
|---|---|---|
| Instagram | @padelyara | Business account, category: Sport |
| Facebook | Cornelia Mayer (admin) → PadelYara Page | Active |
| LinkedIn | Cornelia Mayer (personal) → PadelYara Page | Active |
| TikTok | — | Not supported by Composio; post manually |

## Composio MCP Setup

- Config: `.mcp.json` in project root (gitignored — contains API key)
- If the MCP URL expires, regenerate it: `node get-composio-mcp.mjs` and update `.mcp.json`
- Composio userId: `user_urspxg`

## Posting Workflow (in Claude Code)

1. Call `COMPOSIO_SEARCH_TOOLS` with the use case
2. Verify connections are active with `COMPOSIO_MANAGE_CONNECTIONS`
3. For Instagram: two-step — `INSTAGRAM_POST_IG_USER_MEDIA` (create container) → `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH`
4. For Facebook: `FACEBOOK_LIST_MANAGED_PAGES` to get Page ID → `FACEBOOK_CREATE_PHOTO_POST`
5. For LinkedIn: `LINKEDIN_GET_MY_INFO` for author URN → `LINKEDIN_CREATE_LINKED_IN_POST`

Always pass `session_id: "seed"` in Composio meta tool calls.

## Image Requirements

- Instagram: public URL, no query parameters (no signed/expiring URLs)
- Facebook: public URL, image must be directly fetchable by Meta
- LinkedIn: upload via `LINKEDIN_REGISTER_IMAGE_UPLOAD` or public URL share

## Voice & Copy

All captions written in Yara's voice — see `.agents/yara-voice.md`. German only for Austrian audience.

## Post Generator

Local image posts are generated with `tools/social/generate.py` + `config.yaml`. Output goes to `brand/social/output/`. Upload the generated image to a public URL before posting via API.
