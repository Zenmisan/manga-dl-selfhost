from bs4 import BeautifulSoup
import asyncio
from curl_cffi.requests import AsyncSession

async def test():
    async with AsyncSession(impersonate="chrome110") as client:
        resp = await client.get("https://mangakatana.com/manga/aku-no-hana.7862", allow_redirects=True)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Detail parsing
        title_el = soup.select_one('h1.heading')
        title = title_el.text.strip() if title_el else "Unknown"
        
        cover_el = soup.select_one('.cover img')
        cover = cover_el.get('src') or cover_el.get('data-src') if cover_el else None
        
        print(f"Detail -> Title: {title}, Cover: {cover}")
        
        # Chapters
        chapters = soup.select('.chapters tr a')
        print(f"Found {len(chapters)} chapters. First: {chapters[0].text if chapters else 'None'}")
        
        # Pages
        if chapters:
            ch_url = chapters[-1].get('href')
            resp2 = await client.get(ch_url, allow_redirects=True)
            # Look for var thzq=[...]
            import re
            m = re.search(r"var\s+\w+\s*=\s*(\['[^']*'(?:,'[^']*')*\])\s*;", resp2.text)
            if m:
                print("Found page array via regex.")
            else:
                print("Regex failed to find pages.")

asyncio.run(test())
