// Based on QuickNovel NovelsOnlineProvider (https://novelsonline.net)
var _BASE = 'https://novelsonline.net';

function _noSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

function _parseCards(doc) {
  var results = [];
  var seen = {};
  doc.querySelectorAll('li, div.top-novel-block').forEach(function(el) {
    var a = el.querySelector('a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    if (!href.startsWith('http')) href = _BASE + (href.startsWith('/') ? '' : '/') + href;
    var slug = href.replace(/^https?:\/\/[^/]+\//, '').replace(/\/$/, '');
    if (!slug || seen[slug] || slug.indexOf('/') !== -1 || slug.indexOf('?') !== -1) return;
    seen[slug] = true;

    var titleEl = el.querySelector('.title, h2, h3') || a;
    var title = titleEl ? titleEl.textContent.trim() : slug;
    var img = el.querySelector('img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;

    results.push({
      id: slug,
      title: title,
      cover_url: cover,
      provider: 'novelsonline',
      url: href,
      status: null,
    });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_BASE + '/sResults.php'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'q=' + encodeURIComponent(query.trim()),
    });
    var doc = new DOMParser().parseFromString(data.html || '', 'text/html');
    return _parseCards(doc);
  },

  async getMangaDetail(novelId) {
    var slug = novelId.replace(/^\//, '').replace(/\/$/, '');
    var detailUrl = _BASE + '/' + slug;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(detailUrl));
    var doc = new DOMParser().parseFromString(data.html || '', 'text/html');

    var titleEl = doc.querySelector('h1, h3.title, .novel-title h1');
    var title = titleEl ? titleEl.textContent.trim() : slug;

    var img = doc.querySelector('div.novel-cover img, div.novel-left img, img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;

    var descEl = doc.querySelector('div.novel-right > div > div:first-child > div.novel-detail-body, .desc-text, .description');
    var desc = descEl ? descEl.textContent.trim() : null;

    var genres = [];
    doc.querySelectorAll('div.novel-details > div:nth-child(2) > div.novel-detail-body li, a[href*="/genre/"]').forEach(function(el) {
      var g = el.textContent.trim();
      if (g && genres.indexOf(g) === -1) genres.push(g);
    });

    var authorEl = doc.querySelector('div.novel-details > div:nth-child(5) > div.novel-detail-body li, a[href*="/author/"]');
    var authors = authorEl ? [authorEl.textContent.trim()] : [];

    var chapters = [];
    var seen = {};
    doc.querySelectorAll('ul.chapter-chs > li > a, div.tab-content a').forEach(function(a, idx) {
      var href = a.getAttribute('href') || '';
      if (!href) return;
      var chSlug = href.replace(/^https?:\/\/[^/]+\//, '').replace(slug + '/', '').replace(/\/$/, '');
      if (!chSlug || seen[chSlug]) return;
      seen[chSlug] = true;
      var chTitle = a.textContent.trim() || ('Chapter ' + (idx + 1));
      var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
      var num = numMatch ? parseFloat(numMatch[1]) : (idx + 1);
      chapters.push({
        id: slug + '/' + chSlug,
        title: chTitle,
        number: num,
        published_at: null,
      });
    });

    return {
      id: slug,
      title: title,
      cover_url: cover,
      description: desc,
      status: null,
      genres: genres,
      authors: authors,
      provider: 'novelsonline',
      url: detailUrl,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    return [];
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var url = chapterId.startsWith('http') ? chapterId : _BASE + '/' + parts.join('/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html || '', 'text/html');

    var contentEl = doc.querySelector('#contentall, #chapter-content, div.chapter-content');
    if (!contentEl) return { content: '<p>Chapter content not found.</p>', format: 'html' };

    contentEl.querySelectorAll('script, style, iframe, .ads, .adv-block, div.alert, #podium-spot').forEach(function(el) {
      el.remove();
    });

    contentEl.querySelectorAll('img').forEach(function(img) {
      var src = img.getAttribute('src') || '';
      if (src && src.startsWith('/')) {
        img.setAttribute('src', _BASE + src);
      }
    });

    var content = contentEl.innerHTML;
    return { content: _noSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var p = page || 1;
    var url = _BASE + '/top-novel/' + p;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html || '', 'text/html');
    return _parseCards(doc);
  },

  async getLatest(page) {
    var p = page || 1;
    var url = _BASE + '/latest-release-novel/' + p;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html || '', 'text/html');
    return _parseCards(doc);
  },
};
