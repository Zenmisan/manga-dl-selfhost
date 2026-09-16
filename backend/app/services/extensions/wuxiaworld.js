var _WW = 'https://www.wuxiaworld.com';

function _wwSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

function _wwParseCards(doc, provider) {
  var results = [];
  doc.querySelectorAll('.novel-item, .book-item, .fiction-item, article').forEach(function(item) {
    var a = item.querySelector('a[href*="/novel/"]');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var slug = href.split('/novel/').pop().replace(/\/$/, '').split('/')[0];
    if (!slug || slug.length < 2) return;
    var title = (item.querySelector('h3, h2, .novel-title, .title') || a).textContent.trim();
    var img = item.querySelector('img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;
    results.push({ id: slug, title: title, cover_url: cover, provider: provider || 'wuxiaworld', url: _WW + '/novel/' + slug, status: null });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_WW + '/search?query=' + encodeURIComponent(query)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _wwParseCards(doc, 'wuxiaworld');
  },

  async getMangaDetail(novelId) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_WW + '/novel/' + novelId));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('h1, .novel-title');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('.novel-cover img, .book-cover img, img.thumbnail');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;

    var descEl = doc.querySelector('.novel-desc, .description, .summary');
    var desc = descEl ? descEl.textContent.trim() : null;

    var genres = [];
    doc.querySelectorAll('.genre a, .tag a, .categories a').forEach(function(el) {
      var g = el.textContent.trim();
      if (g) genres.push(g);
    });

    var authorEl = doc.querySelector('.author, .translator');
    var authors = authorEl ? [authorEl.textContent.replace(/author[:\s]*/i, '').trim()] : [];

    var chapters = [];
    doc.querySelectorAll('.chapter-item a, .chapter-list a').forEach(function(a, i) {
      var href = a.getAttribute('href') || '';
      var slug = href.split('/novel/' + novelId + '/').pop().replace(/\/$/, '');
      if (!slug || slug === href) return;
      var chId = novelId + '/' + slug;
      var chTitle = a.textContent.trim();
      var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chTitle.match(/([\d.]+)/);
      var num = numMatch ? parseFloat(numMatch[1]) : (i + 1);
      chapters.push({ id: chId, title: chTitle, number: num, published_at: null });
    });
    chapters.reverse();

    return { id: novelId, title: title, cover_url: cover, description: desc, status: null, genres: genres, authors: authors, provider: 'wuxiaworld', url: _WW + '/novel/' + novelId, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var novelSlug = parts[0];
    var chSlug = parts.slice(1).join('/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_WW + '/novel/' + novelSlug + '/' + chSlug));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('.chapter-content, .fr-view, #chapter-output, .content-text');
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _wwSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_WW + '/novels?orderby=ratingpoints&status=all'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _wwParseCards(doc, 'wuxiaworld');
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_WW + '/novels?orderby=lastactive&status=all'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _wwParseCards(doc, 'wuxiaworld');
  },
};
