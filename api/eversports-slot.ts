export const config = { runtime: "edge" }

/**
 * Proxy for https://www.eversports.at/api/slot
 *
 * Vercel Edge Functions run on Cloudflare's network, so requests to
 * eversports.at (also behind Cloudflare) are less likely to be blocked
 * than requests from Railway's datacenter IPs.
 *
 * Called by the Railway backend as a drop-in replacement for the slot API.
 * Query params are forwarded as-is (facilityId, startDate, courts[]).
 */
export default async function handler(request: Request): Promise<Response> {
  const incoming = new URL(request.url)
  const target = new URL("https://www.eversports.at/api/slot")
  target.search = incoming.search

  let response: Response
  try {
    response = await fetch(target.toString(), {
      headers: {
        Accept: "application/json, text/plain, */*",
        "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
        Referer: "https://www.eversports.at/",
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      },
    })
  } catch (err) {
    return new Response(JSON.stringify({ error: "proxy_fetch_failed", detail: String(err) }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    })
  }

  const body = await response.text()
  return new Response(body, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("Content-Type") ?? "application/json",
      "X-Proxy-Status": String(response.status),
    },
  })
}
