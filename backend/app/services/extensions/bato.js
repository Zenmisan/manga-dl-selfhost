var _BA = 'https://bato.to';

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

function _parseCards(doc, provider) {
  var results = [];
  var seen = {};
  doc.querySelectorAll('a[href*="/title/"], a[href*="/series/"]').forEach(function(a) {
    var href = a.getAttribute('href') || '';
    var match = href.match(/\/(title|series)\/([\w-]+)/);
    if (!match) return;
    var id = match[2];
    if (seen[id]) return;
    seen[id] = true;
    var img = a.querySelector('img') || a.closest('div')?.querySelector('img');
    var titleEl = a.querySelector('[class*="title"], h3, p') || a;
    results.push({
      id: id,
      title: (titleEl.textContent || '').trim() || id,
      cover_url: img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null,
      provider: 'bato',
      url: _BA + '/title/' + id,
      status: null,
    });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var p = page || 1;
    var doc = await _fetchDoc(_BA + '/search?word=' + encodeURIComponent(query) + '&page=' + p);
    return _parseCards(doc);
  },

  async getMangaDetail(mangaId) {
    var doc = await _fetchDoc(_BA + '/title/' + mangaId);
    var title = (doc.querySelector('h3.item-title, h1, [class*="title"]') || {}).textContent || mangaId;
    var cover = doc.querySelector('.detail-set img, [class*="cover"] img, img[alt]');
    var desc = doc.querySelector('[class*="summary"], [class*="description"], .limit-html');
    var genres = [];
    doc.querySelectorAll('[class*="genre"] a, [class*="tag"] a').forEach(function(a) { genres.push(a.textContent.trim()); });
    var chapters = [];
    doc.querySelectorAll('a[href*="/chapter"]').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      var chId = href.split('/').pop()?.replace(/\?.*/, '') || '';
      if (!chId || chId === mangaId) return;
      var text = a.textContent.trim();
      var numM = text.match(/([\d.]+)/);
      var dateEl = a.closest('li,div')?.querySelector('time, [class*="date"]');
      chapters.push({
        id: chId,
        title: text,
        number: numM ? parseFloat(numM[1]) : 0,
        published_at: dateEl ? (dateEl.getAttribute('datetime') || dateEl.textContent.trim()) : null,
      });
    });
    return {
      id: mangaId,
      title: title.trim(),
      cover_url: cover ? (cover.getAttribute('src') || cover.getAttribute('data-src')) : null,
      description: desc ? desc.textContent.trim() : null,
      status: null, genres: genres, authors: [],
      provider: 'bato',
      url: _BA + '/title/' + mangaId,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_BA + '/chapter/' + chapterId));
    var html = data.html;
    var pages = [];
    // Bato embeds image list in a script: var imgHttpLis = [...]
    var m = html.match(/var\s+imgHttpLis\s*=\s*(\[[^\]]+\])/);
    if (m) {
      try {
        var arr = JSON.parse(m[1].replace(/'/g, '"'));
        if (Array.isArray(arr)) return arr.filter(Boolean);
      } catch(e) {}
    }
    // Fallback: DOM scrape
    var doc = new DOMParser().parseFromString(html, 'text/html');
    doc.querySelectorAll('img[class*="page"], .viewer img, [data-index] img').forEach(function(img) {
      var src = img.getAttribute('src') || img.getAttribute('data-src');
      if (src && src.startsWith('http')) pages.push(src);
    });
    return pages;
  },

  async getPopular(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_BA + '/browse?sort=views_w&page=' + p);
    return _parseCards(doc);
  },

  async getLatest(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_BA + '/browse?sort=update&page=' + p);
    return _parseCards(doc);
  },
};
