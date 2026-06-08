import asyncio, re
from curl_cffi.requests import AsyncSession

async def fetch():
    url = "https://www.eversports.at/sb/padelzone-traiskirchen"
    async with AsyncSession(impersonate="chrome124") as s:
        r = await s.get(url, timeout=15)
    print("HTTP:", r.status_code)
    print("Content-Length:", len(r.text))
    text = r.text

    patterns = [
        (r'window\.__[A-Z_]+__\s*=\s*\{.{0,200}', "window.__STATE__"),
        (r'"slots"', "slots keyword"),
        (r'"booked"', "booked keyword"),
        (r'"free"', "free keyword"),
        (r'data-state=.(free|busy|booked)', "data-state attrs"),
        (r'data-date=.([\d-]+)', "data-date attrs"),
        (r'data-start=.([\d:]+)', "data-start attrs"),
        (r'initialState|__NUXT__|__NEXT_DATA__|pageProps', "framework state"),
        (r'"availab', "availab keyword"),
        (r'calendar', "calendar keyword"),
    ]

    for pattern, label in patterns:
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        print(f"{'FOUND' if m else 'NOT FOUND':10} [{label}]" + (f": {m.group(0)[:120]!r}" if m else ""))

    print("\n--- body start (500 chars) ---")
    print(text[:500])
    print("\n--- body end (500 chars) ---")
    print(text[-500:])

asyncio.run(fetch())
