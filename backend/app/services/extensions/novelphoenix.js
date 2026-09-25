// Based on QuickNovel NovelPhoenixProvider (extends NovelFireProvider, sectionUrl="novel")
var _NPX = 'https://novelphoenix.com';

function _npxSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

function _npxParseCards(doc) {
  var results = [];
  doc.querySelectorAll('li.novel-item').forEach(function(item) {
    var a = item.querySelector('a[title], a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var slug = href.replace(/.*\/novel\//, '').replace(/\/$/, '');
    if (!slug || slug.length < 2) return;
    var title = a.getAttribute('title') || (item.querySelector('h4.novel-title, h5') || a).textContent.trim();
    var img = item.querySelector('img');
    var cover = img ? (img.getAttribute('data-src') || img.getAttribute('src')) : null;
    results.push({ id: slug, title: title, cover_url: cover, provider: 'novelphoenix', url: _NPX + '/novel/' + slug, status: null });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var url = _NPX + '/search/?keyword=' + encodeURIComponent(query.trim()) + '&page=' + (page || 1);
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _npxParseCards(doc);
  },

  async getMangaDetail(novelId) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_NPX + '/novel/' + novelId));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('h1.novel-title');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('figure.cover img, .cover img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;

    var desc = doc.querySelector('meta[itemprop="description"]')?.getAttribute('content') || '';

    var genres = [];
    doc.querySelectorAll('div.categories ul li, div.tags ul li').forEach(function(el) {
      var g = el.textContent.trim(); if (g) genres.push(g);
    });

    var authorEl = doc.querySelector('div.novel-info div.author a, div.author a');
    var authors = authorEl ? [authorEl.textContent.trim()] : [];

    var reportEl = doc.querySelector('a#novel-report');
    var postId = reportEl ? reportEl.getAttribute('report-post_id') : null;

    var chapters = [];
    if (postId) {
      var ajaxParams = 'draw=1&columns%5B0%5D%5Bdata%5D=n_sort&order%5B0%5D%5Bcolumn%5D=0&order%5B0%5D%5Bdir%5D=asc&start=0&length=-1&search%5Bvalue%5D=&post_id=' + encodeURIComponent(postId) + '&only_bookmark=false';
      try {
        var chData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_NPX + '/ajax/listChapterDataAjax?' + ajaxParams));
        var parsed = null;
        try { parsed = JSON.parse(chData.html || chData.text || ''); } catch(e) {}
        if (parsed && parsed.data) {
          parsed.data.forEach(function(item) {
            var n = item.n_sort;
            if (!n) return;
            var chTitle = item.title || ('Chapter ' + n);
            var chId = novelId + '/chapter-' + n;
            chapters.push({ id: chId, title: chTitle, number: n, published_at: null });
          });
        }
      } catch(e) {}
    }

    return { id: novelId, title: title, cover_url: cover, description: desc, status: null, genres: genres, authors: authors, provider: 'novelphoenix', url: _NPX + '/novel/' + novelId, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var slug = parts[0];
    var chPart = parts.slice(1).join('/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_NPX + '/novel/' + slug + '/' + chPart));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('div#content');
    if (contentEl) {
      var firstP = contentEl.querySelector('p');
      var titleEl2 = doc.querySelector('span.chapter-title');
      if (firstP && titleEl2 && firstP.textContent.trim().toLowerCase() === titleEl2.textContent.trim().toLowerCase()) {
        firstP.remove();
      }
      contentEl.querySelectorAll('img[src*="disable-blocker"]').forEach(function(el) { el.remove(); });
    }
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _npxSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var url = _NPX + '/genre-all/sort-popular/status-all/all-novel?page=' + (page || 1);
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _npxParseCards(doc);
  },

  async getLatest(page) {
    var url = _NPX + '/genre-all/sort-latest-release/status-all/all-novel?page=' + (page || 1);
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _npxParseCards(doc);
  },
};
