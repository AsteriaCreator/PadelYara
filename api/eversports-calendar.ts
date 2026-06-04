export const config = { runtime: "edge" }

/**
 * Proxy for the Eversports booking calendar HTML.
 *
 * The /api/booking/calendar/update endpoint requires:
 *   1. A session established via GET of the booking page (PHPSESSID + XSRF-TOKEN)
 *   2. A CSRF token extracted from the page meta tag
 *
 * Railway's egress IPs get blocked by Cloudflare WAF on these requests.
 * Vercel Edge Functions run on Cloudflare's own network, so CF→CF traffic
 * is allowed through without triggering the WAF.
 *
 * Called by the Railway backend when EVERSPORTS_CALENDAR_PROXY is set.
 * Request body (JSON): { venue_url, facility_id, date, time_hhmm }
 * Response: raw calendar HTML (same as /api/booking/calendar/update returns)
 */

const ES_BASE = "https://www.eversports.at"
const CAL_URL = `${ES_BASE}/api/booking/calendar/update`

const BROWSER_HEADERS = {
  "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

/** Parse name=value pairs out of Set-Cookie headers, drop attributes. */
function extractCookies(headers: Headers): string {
  const pairs: string[] = []
  // CF Workers / Vercel Edge: headers.getAll is available for set-cookie
  const raw: string[] =
    typeof (headers as any).getAll === "function"
      ? (headers as any).getAll("set-cookie")
      : [headers.get("set-cookie") ?? ""].filter(Boolean)

  for (const line of raw) {
    const pair = line.split(";")[0].trim()
    if (pair) pairs.push(pair)
  }
  return pairs.join("; ")
}

/** Extract CSRF token from Laravel meta tag in page HTML. */
function extractCsrf(html: string): string {
  const m =
    html.match(/<meta[^>]+name=["']csrf-token["'][^>]+content=["']([^"']+)/i) ||
    html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+name=["']csrf-token/i)
  return m ? m[1] : ""
}

/** DD/MM/YYYY from YYYY-MM-DD */
function toDatepicker(iso: string): string {
  const [y, m, d] = iso.split("-")
  return `${d}/${m}/${y}`
}

export default async function handler(request: Request): Promise<Response> {
  if (request.method !== "POST") {
    return new Response(JSON.stringify({ error: "method_not_allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    })
  }

  let body: { venue_url: string; facility_id: string; date: string; time_hhmm: string }
  try {
    body = await request.json()
  } catch {
    return new Response(JSON.stringify({ error: "invalid_json" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    })
  }

  const { venue_url, facility_id, date, time_hhmm } = body
  if (!venue_url || !date || !time_hhmm) {
    return new Response(JSON.stringify({ error: "missing_params" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    })
  }

  const facilitySlug = venue_url.replace(/\/$/, "").split("/").pop() ?? ""
  const dp = toDatepicker(date)

  // ── Step 1: GET booking page → session cookies + CSRF token ──────────────
  let getResp: Response
  try {
    getResp = await fetch(venue_url, {
      headers: {
        ...BROWSER_HEADERS,
        Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        Referer: ES_BASE + "/",
      },
    })
  } catch (err) {
    return new Response(
      JSON.stringify({ error: "get_failed", detail: String(err) }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    )
  }

  if (!getResp.ok) {
    return new Response(
      JSON.stringify({ error: "get_non_200", status: getResp.status }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    )
  }

  const pageHtml = await getResp.text()
  const csrfToken = extractCsrf(pageHtml)
  const cookieHeader = extractCookies(getResp.headers)

  console.log(
    JSON.stringify({
      event: "cal_proxy_get",
      venue_url,
      get_status: getResp.status,
      csrf_found: !!csrfToken,
      cookie_count: cookieHeader.split(";").filter(Boolean).length,
    }),
  )

  // ── Step 2: POST to calendar update endpoint ──────────────────────────────
  const postBody = new URLSearchParams({
    date: dp,
    facilityId: facility_id,
    facility: facilitySlug,
  })

  const postHeaders: Record<string, string> = {
    ...BROWSER_HEADERS,
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    Accept: "*/*",
    Referer: venue_url,
    Origin: ES_BASE,
  }
  if (csrfToken) postHeaders["X-CSRF-TOKEN"] = csrfToken
  if (cookieHeader) postHeaders["Cookie"] = cookieHeader

  let postResp: Response
  try {
    postResp = await fetch(CAL_URL, {
      method: "POST",
      headers: postHeaders,
      body: postBody.toString(),
    })
  } catch (err) {
    return new Response(
      JSON.stringify({ error: "post_failed", detail: String(err) }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    )
  }

  const calHtml = await postResp.text()
  const hasTd = calHtml.includes("<td")

  console.log(
    JSON.stringify({
      event: "cal_proxy_post",
      post_status: postResp.status,
      has_td: hasTd,
      html_len: calHtml.length,
      excerpt: calHtml.substring(0, 120),
    }),
  )

  return new Response(calHtml, {
    status: postResp.status,
    headers: {
      "Content-Type": postResp.headers.get("Content-Type") ?? "text/html",
      "X-Proxy-Status": String(postResp.status),
      "X-CSRF-Found": csrfToken ? "1" : "0",
      "X-Has-Td": hasTd ? "1" : "0",
    },
  })
}
