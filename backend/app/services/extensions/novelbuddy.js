// Based on QuickNovel NovelBuddyProvider
var _NB = 'https://novelbuddy.me';
var _NBA = 'https://api.novelbuddy.me/titles';

function _nbSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

var extension = {
  async search(query, page) {
    var url = _NBA + '/search?page=1&limit=20&q=' + encodeURIComponent(query);
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var json = null;
    try { json = JSON.parse(data.html || data.text || ''); } catch(e) {}
    if (!json) return [];
    var items = json.data || json.titles || json || [];
    if (!Array.isArray(items)) return [];
    return items.map(function(item) {
      var slug = item.slug || item.id || '';
      var title = item.title || item.name || slug;
      var cover = item.cover_url || item.image || item.thumbnail || null;
      return { id: slug, title: title, cover_url: cover, provider: 'novelbuddy', url: _NB + '/novel/' + slug, status: null };
    });
  },

  async getMangaDetail(novelId) {
    var url = _NB + '/novel/' + novelId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var jsonNode = doc.querySelector('script#__NEXT_DATA__');
    var jsonText = jsonNode ? jsonNode.textContent : null;
    var json = null;
    if (jsonText) { try { json = JSON.parse(jsonText); } catch(e) {} }

    var title = novelId;
    var cover = null;
    var desc = null;
    var genres = [];
    var authors = [];
    var bookId = novelId;

    if (json && json.props && json.props.pageProps) {
      var pp = json.props.pageProps;
      var book = pp.book || pp.title || pp.novel || null;
      if (book) {
        title = book.title || book.name || novelId;
        cover = book.cover_url || book.image || book.thumbnail || null;
        desc = book.description || book.synopsis || null;
        bookId = book.id || book.slug || novelId;
        if (book.genres) genres = book.genres.map(function(g) { return g.name || g; });
        if (book.authors) authors = book.authors.map(function(a) { return a.name || a; });
      }
    }

    var chapters = [];
    try {
      var chData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_NBA + '/' + bookId + '/chapters?page=1&limit=9999'));
      var chJson = null;
      try { chJson = JSON.parse(chData.html || chData.text || ''); } catch(e) {}
      var chArr = chJson ? (chJson.data || chJson.chapters || chJson || []) : [];
      if (Array.isArray(chArr)) {
        chArr.forEach(function(ch, i) {
          var chSlug = ch.slug || ch.id || (i + 1);
          var chTitle = ch.title || ch.name || ('Chapter ' + (i + 1));
          var chId = novelId + '/' + chSlug;
          var numMatch = chTitle.match(/chapter\s+([\d.]+)/i);
          var num = numMatch ? parseFloat(numMatch[1]) : (i + 1);
          chapters.push({ id: chId, title: chTitle, number: num, published_at: ch.created_at || ch.date || null });
        });
      }
    } catch(e) {}

    return { id: novelId, title: title, cover_url: cover, description: desc, status: null, genres: genres, authors: authors, provider: 'novelbuddy', url: url, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var slug = parts[0];
    var chSlug = parts.slice(1).join('/');
    var url = _NB + '/novel/' + slug + '/' + chSlug;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('div.novel-tts-content, div.chapter-content, .content');
    if (contentEl) {
      contentEl.querySelectorAll('script, style, .ads, .adsbygoogle').forEach(function(el) { el.remove(); });
    }
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _nbSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var url = _NBA + '?page=' + (page || 1) + '&limit=24&sort=views';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var json = null;
    try { json = JSON.parse(data.html || data.text || ''); } catch(e) {}
    var items = json ? (json.data || json.titles || json || []) : [];
    if (!Array.isArray(items)) return [];
    return items.map(function(item) {
      var s = item.slug || item.id || '';
      return { id: s, title: item.title || item.name || s, cover_url: item.cover_url || item.image || null, provider: 'novelbuddy', url: _NB + '/novel/' + s, status: null };
    });
  },

  async getLatest(page) {
    var url = _NBA + '?page=' + (page || 1) + '&limit=24&sort=updated';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var json = null;
    try { json = JSON.parse(data.html || data.text || ''); } catch(e) {}
    var items = json ? (json.data || json.titles || json || []) : [];
    if (!Array.isArray(items)) return [];
    return items.map(function(item) {
      var s = item.slug || item.id || '';
      return { id: s, title: item.title || item.name || s, cover_url: item.cover_url || item.image || null, provider: 'novelbuddy', url: _NB + '/novel/' + s, status: null };
    });
  },
};
