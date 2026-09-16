import asyncio
from curl_cffi.requests import AsyncSession

async def test():
    async with AsyncSession(impersonate="chrome110") as client:
        resp = await client.get("https://mangakatana.com/manga/aku-no-hana.7862/c1", allow_redirects=True)
        with open("mk_pages.html", "w") as f:
            f.write(resp.text)
        print("Saved to mk_pages.html")

asyncio.run(test())
