var _MP = 'https://mangapill.com';

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

function _parseCards(doc) {
  var results = [];
  doc.querySelectorAll('.grid a[href*="/manga/"]').forEach(function(a) {
    var href = a.getAttribute('href') || '';
    var id = href.split('/manga/')[1]?.replace(/\/$/, '') || '';
    if (!id) return;
    var img = a.querySelector('img');
    var titleEl = a.querySelector('.text-sm, p, .line-clamp-2');
    results.push({
      id: id,
      title: titleEl ? titleEl.textContent.trim() : id,
      cover_url: img ? (img.getAttribute('data-src') || img.getAttribute('src')) : null,
      provider: 'mangapill',
      url: _MP + href,
      status: null,
    });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var p = page || 1;
    var url = _MP + '/search?q=' + encodeURIComponent(query) + '&page=' + p;
    var doc = await _fetchDoc(url);
    return _parseCards(doc);
  },

  async getMangaDetail(mangaId) {
    var doc = await _fetchDoc(_MP + '/manga/' + mangaId);
    var title = (doc.querySelector('h1, .font-bold') || {}).textContent || mangaId;
    var cover = doc.querySelector('.flex img, [class*="cover"] img');
    var desc = doc.querySelector('[class*="description"], .prose');
    var chapters = [];
    doc.querySelectorAll('#chapters a[href*="/chapters/"]').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      var chId = href.split('/chapters/')[1]?.replace(/\/$/, '') || '';
      var text = a.textContent.trim();
      var numM = text.match(/([\d.]+)/);
      chapters.push({
        id: chId,
        title: text,
        number: numM ? parseFloat(numM[1]) : 0,
        published_at: null,
      });
    });
    return {
      id: mangaId,
      title: title.trim(),
      cover_url: cover ? (cover.getAttribute('data-src') || cover.getAttribute('src')) : null,
      description: desc ? desc.textContent.trim() : null,
      status: null, genres: [], authors: [],
      provider: 'mangapill',
      url: _MP + '/manga/' + mangaId,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var doc = await _fetchDoc(_MP + '/chapters/' + chapterId);
    var pages = [];
    doc.querySelectorAll('chapter-page img[data-src], .reading-content img').forEach(function(img) {
      var src = img.getAttribute('data-src') || img.getAttribute('src');
      if (src && src.startsWith('http')) pages.push(src);
    });
    return pages;
  },

  async getPopular(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_MP + '/search?status=&type=&page=' + p);
    return _parseCards(doc);
  },

  async getLatest(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_MP + '/chapters?page=' + p);
    // Latest page lists recent chapters — extract unique manga
    var results = [];
    var seen = {};
    doc.querySelectorAll('a[href*="/manga/"]').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      var id = href.split('/manga/')[1]?.replace(/\/$/, '') || '';
      if (!id || seen[id] || href.includes('/chapters/')) return;
      seen[id] = true;
      results.push({ id: id, title: a.textContent.trim(), cover_url: null, provider: 'mangapill', url: _MP + href, status: null });
    });
    return results;
  },
};
