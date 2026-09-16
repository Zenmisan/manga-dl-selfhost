import asyncio
from curl_cffi.requests import AsyncSession

async def test():
    async with AsyncSession(impersonate="chrome110") as client:
        resp = await client.get("https://mangakatana.com/?search=aku%20no%20hana&search_by=m_name", allow_redirects=True)
        print(resp.status_code)
        if "aku no hana" in resp.text.lower():
            print("Found search term in response.")
        if "manga_list" in resp.text:
            print("Found manga_list class.")
        else:
            print("manga_list not found.")
            with open("mk_resp.html", "w") as f:
                f.write(resp.text)

asyncio.run(test())
