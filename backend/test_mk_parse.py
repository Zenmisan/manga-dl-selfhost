from bs4 import BeautifulSoup

with open("mk_resp.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
for item in soup.select('#book_list .item'):
    a = item.select_one('.text h3.title a')
    if a:
        title = a.text.strip()
        url = a.get('href')
        slug = url.split('/')[-1]
        img = item.select_one('.media .wrap_img img')
        img_url = img.get('src') or img.get('data-src') if img else None
        print(f"Title: {title}, Slug: {slug}, Image: {img_url}")

