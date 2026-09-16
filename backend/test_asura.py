import asyncio
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

async def test():
    async with AsyncSession(impersonate="chrome110") as client:
        # Search test
        url = "https://asuracomic.net/series?page=1&name=solo%20leveling"
        resp = await client.get(url, allow_redirects=True)
        print(f"Asura Search Status: {resp.status_code}")
        if resp.status_code == 200:
            with open("asura_search.html", "w") as f:
                f.write(resp.text)
            soup = BeautifulSoup(resp.text, 'html.parser')
            links = soup.select("a[href*='/series/']")
            print(f"Found {len(links)} links with /series/")
            for a in links[:5]:
                print(f"Link: {a.get('href')}")

asyncio.run(test())
