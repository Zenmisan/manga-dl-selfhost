// Azuki — free chapters available publicly; subscription chapters throw 401/404
var _AZ = 'https://www.azuki.co';
var _API = 'https://production.api.azuki.co';

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

async function _fetchJson(path) {
  return apiFetch('/manga/proxy/json?url=' + encodeURIComponent(_API + path));
}

function _parseCards(doc) {
  var results = [];
  var seen = {};
  doc.querySelectorAll('ol.o-series-card-list li, [class*="series"] a[href*="/series/"], a[data-ga-item-id*="series-"]').forEach(function(el) {
    var a = el.querySelector ? el.querySelector('a[href*="/series/"]') : el;
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var id = href.split('/series/')[1]?.replace(/\/$/, '') || '';
    if (!id || seen[id]) return;
    seen[id] = true;
    var img = el.querySelector ? el.querySelector('img') : null;
    var titleEl = el.querySelector ? el.querySelector('[class*="title"], h3, .o-series-card__title') : null;
    results.push({
      id: id,
      title: titleEl ? titleEl.textContent.trim() : id.replace(/-/g, ' '),
      cover_url: img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null,
      provider: 'azuki',
      url: _AZ + '/series/' + id,
      status: null,
    });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var doc = await _fetchDoc(_AZ + '/discover?q=' + encodeURIComponent(query));
    return _parseCards(doc);
  },

  async getMangaDetail(mangaId) {
    // Try API first
    var apiData = null;
    try {
      apiData = await _fetchJson('/manga/slug/' + mangaId + '/v0');
    } catch(e) {}

    if (apiData && apiData.manga) {
      var m = apiData.manga;
      var chapters = (m.chapters || []).map(function(ch) {
        return {
          id: ch.uuid || ch.id,
          title: ch.title || ('Chapter ' + ch.number),
          number: parseFloat(ch.number) || 0,
          published_at: ch.published_at || null,
        };
      });
      return {
        id: mangaId,
        title: m.title || mangaId,
        cover_url: m.cover_image_url || null,
        description: m.description || null,
        status: m.status || null,
        genres: (m.genres || []).map(function(g) { return g.name || g; }),
        authors: (m.authors || []).map(function(a) { return a.name || a; }),
        provider: 'azuki',
        url: _AZ + '/series/' + mangaId,
        chapters: chapters,
      };
    }

    // HTML fallback
    var doc = await _fetchDoc(_AZ + '/series/' + mangaId);
    var title = (doc.querySelector('h1, [class*="series-title"]') || {}).textContent || mangaId;
    var cover = doc.querySelector('img[class*="cover"], [class*="hero"] img');
    var desc = doc.querySelector('[class*="description"], [class*="synopsis"]');
    var chapters = [];
    doc.querySelectorAll('a[href*="/series/' + mangaId + '/"]').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      var parts = href.split('/');
      var chId = parts.pop() || '';
      if (!chId || chId === mangaId) return;
      var text = a.textContent.trim();
      var numM = text.match(/([\d.]+)/);
      chapters.push({ id: chId, title: text, number: numM ? parseFloat(numM[1]) : 0, published_at: null });
    });
    return {
      id: mangaId, title: title.trim(),
      cover_url: cover ? (cover.getAttribute('src') || cover.getAttribute('data-src')) : null,
      description: desc ? desc.textContent.trim() : null,
      status: null, genres: [], authors: [],
      provider: 'azuki',
      url: _AZ + '/series/' + mangaId,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    // Azuki serves pages via API; subscription chapters require auth
    try {
      var data = await _fetchJson('/manga/chapter/' + chapterId + '/pages/v1');
      var pages = data?.pages || data?.data?.pages || [];
      return pages.map(function(p) { return p.url || p.image_url || p; }).filter(function(u) { return typeof u === 'string'; });
    } catch(e) {
      throw new Error('This chapter may require an Azuki subscription.');
    }
  },

  async getPopular(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_AZ + '/discover?sort=popular&page=' + p);
    return _parseCards(doc);
  },

  async getLatest(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_AZ + '/discover?sort=recent_series&page=' + p);
    return _parseCards(doc);
  },
};
