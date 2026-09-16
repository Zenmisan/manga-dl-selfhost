var _TCB = 'https://tcbscans.me';

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

function _parseCards(doc) {
  var results = [];
  var seen = {};
  doc.querySelectorAll('a[href*="/mangas/"]').forEach(function(a) {
    var href = a.getAttribute('href') || '';
    var id = href.split('/mangas/')[1]?.replace(/\/$/, '') || '';
    if (!id || seen[id] || id.includes('/')) return;
    seen[id] = true;
    var img = a.querySelector('img');
    var titleEl = a.querySelector('p, span, .text-sm');
    results.push({
      id: id,
      title: titleEl ? titleEl.textContent.trim() : id.replace(/-/g, ' '),
      cover_url: img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null,
      provider: 'tcbscans',
      url: _TCB + '/mangas/' + id,
      status: null,
    });
  });
  return results;
}

var extension = {
  async search(query, page) {
    // TCB Scans is a small site — filter from projects list
    var doc = await _fetchDoc(_TCB + '/projects');
    var all = _parseCards(doc);
    var q = query.toLowerCase();
    return all.filter(function(m) { return m.title.toLowerCase().includes(q); });
  },

  async getMangaDetail(mangaId) {
    var doc = await _fetchDoc(_TCB + '/mangas/' + mangaId);
    var title = (doc.querySelector('h1, .text-4xl, .font-bold') || {}).textContent || mangaId;
    var cover = doc.querySelector('img[src*="cover"], .rounded img');
    var desc = doc.querySelector('.prose, [class*="description"]');
    var chapters = [];
    doc.querySelectorAll('a[href*="/chapters/"]').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      var chId = href.split('/chapters/')[1]?.replace(/\/$/, '') || '';
      if (!chId) return;
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
      cover_url: cover ? (cover.getAttribute('src') || cover.getAttribute('data-src')) : null,
      description: desc ? desc.textContent.trim() : null,
      status: null, genres: [], authors: [],
      provider: 'tcbscans',
      url: _TCB + '/mangas/' + mangaId,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var doc = await _fetchDoc(_TCB + '/chapters/' + chapterId);
    var pages = [];
    doc.querySelectorAll('picture img, .image-container img, .reader img').forEach(function(img) {
      var src = img.getAttribute('src') || img.getAttribute('data-src');
      if (src && src.startsWith('http')) pages.push(src);
    });
    return pages;
  },

  async getPopular(page) {
    var doc = await _fetchDoc(_TCB + '/projects');
    return _parseCards(doc);
  },

  async getLatest(page) {
    var doc = await _fetchDoc(_TCB);
    return _parseCards(doc);
  },
};
