import { Composio } from "@composio/core";

const composio = new Composio();
const userId = "user_urspxg";

const session = await composio.create(userId);
console.log(JSON.stringify(session.mcp, null, 2));
