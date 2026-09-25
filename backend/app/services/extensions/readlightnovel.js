// Based on QuickNovel ReadLightNovelProvider
var _RLN = 'https://www.readlightnovel.me';

function _rlnSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '')
    .replace(/<p[^>]*>.*?(?:readlightnovel|lightnovelpub).*?<\/p>/gi, '');
}

function _rlnParseCards(doc) {
  var results = [];
  doc.querySelectorAll('div.top-novel-block').forEach(function(item) {
    var a = item.querySelector('div.top-novel-header > h2 > a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var title = a.textContent.trim();
    var img = item.querySelector('img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;
    var slug = href.replace(_RLN, '').replace(/^\//, '').replace(/\/$/, '');
    if (!slug) return;
    results.push({ id: slug, title: title, cover_url: cover, provider: 'readlightnovel', url: href, status: null });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_RLN + '/search/autocomplete'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest' },
      body: 'q=' + encodeURIComponent(query),
    });
    var json = null;
    try { json = JSON.parse(data.html || data.text || ''); } catch(e) {}
    if (!Array.isArray(json)) {
      // Fallback: try regular search page
      var fallback = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_RLN + '/search?keyword=' + encodeURIComponent(query)));
      var doc2 = new DOMParser().parseFromString(fallback.html, 'text/html');
      return _rlnParseCards(doc2);
    }
    return json.map(function(item) {
      var href = item.url || item.link || '';
      var slug = href.replace(_RLN, '').replace(/^\//, '').replace(/\/$/, '');
      return { id: slug, title: item.label || item.title || item.name || slug, cover_url: item.image || null, provider: 'readlightnovel', url: href, status: null };
    });
  },

  async getMangaDetail(novelId) {
    var url = novelId.startsWith('http') ? novelId : _RLN + '/' + novelId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('h1.novel-title, h1, .novel-title h1');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('.novel-cover img, .novel-main-img img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;

    var descEl = doc.querySelector('.novel-body .novel-right, div.novel-detail-body');
    var desc = descEl ? descEl.textContent.trim() : null;

    var authors = [];
    var authorEl = doc.querySelector('div.novel-detail-item a.novel-detail-body-link-a');
    if (authorEl) authors = [authorEl.textContent.trim()];

    var chapters = [];
    // Chapter list from panel/tab structure
    doc.querySelectorAll('div.panel-collapse a, ul.chapter-chs > li > a').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      var chSlug = href.replace(_RLN, '').replace(/^\//, '').replace(/\/$/, '');
      var chTitle = a.textContent.trim();
      if (!chSlug) return;
      var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
      var num = numMatch ? parseFloat(numMatch[1]) : (chapters.length + 1);
      chapters.push({ id: chSlug, title: chTitle, number: num, published_at: null });
    });

    return { id: novelId, title: title, cover_url: cover, description: desc, status: null, genres: [], authors: authors, provider: 'readlightnovel', url: url, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var url = chapterId.startsWith('http') ? chapterId : _RLN + '/' + chapterId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('div.chapter-content3 > div.desc, div.chapter-content, .chapter-body');
    if (contentEl) {
      contentEl.querySelectorAll('script, style, iframe, .ads, .blocker, div.alert, #podium-spot, small.ads-title, p.hid, .hidden').forEach(function(el) { el.remove(); });
    }
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _rlnSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var url = _RLN + '/top-novels/top-rated/' + (page || 1);
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _rlnParseCards(doc);
  },

  async getLatest(page) {
    var url = _RLN + '/top-novels/most-viewed/' + (page || 1);
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _rlnParseCards(doc);
  },
};
