// Based on QuickNovel AllNovelProvider
var _AN = 'https://allnovel.org';

function _anSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

function _anFixCover(url) {
  if (!url) return url;
  return url
    .replace('fc05345726d3e134d2f7187dc70f047b', '4d27e0af8cf6e971f7ee3c995fc55190')
    .replace('9798407846f8032e6a88fa71b2c62ce9', '9c3d392ccc7c95187a8c6e37c6bdac6f');
}

function _anParseCards(doc) {
  var results = [];
  doc.querySelectorAll('#list-page > .archive > .list > .row, div.list > div.row').forEach(function(h) {
    var a = h.querySelector('div > div > h3.truyen-title > a, div > div > h3.novel-title > a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var slug = href.replace(/^\//, '').replace(/\.html$/, '');
    if (!slug || slug.length < 2) return;
    var title = a.textContent.trim();
    var img = h.querySelector('img');
    var cover = img ? _anFixCover(img.getAttribute('src') || img.getAttribute('data-src')) : null;
    if (cover && cover.startsWith('/')) cover = _AN + cover;
    results.push({ id: slug, title: title, cover_url: cover, provider: 'allnovel', url: _AN + '/' + slug + '.html', status: null });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var url = _AN + '/search?keyword=' + encodeURIComponent(query);
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _anParseCards(doc);
  },

  async getMangaDetail(novelId) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_AN + '/' + novelId + '.html'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('h3.title, h1.title');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('div.book img, .books img');
    var cover = _anFixCover(img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null);
    if (cover && cover.startsWith('/')) cover = _AN + cover;

    var descEl = doc.querySelector('div.desc-text, .description-text');
    var desc = descEl ? descEl.textContent.trim() : null;

    var genres = [];
    var authors = [];
    var status = null;
    doc.querySelectorAll('div.info > div, ul.info > li').forEach(function(div) {
      var text = div.textContent || '';
      if (/genre/i.test(text)) {
        div.querySelectorAll('a').forEach(function(a) { var g = a.textContent.trim(); if (g) genres.push(g); });
      } else if (/author/i.test(text)) {
        var a = div.querySelector('a');
        if (a) authors = [a.textContent.trim()];
      } else if (/status/i.test(text)) {
        var a = div.querySelector('a');
        if (a) status = a.textContent.trim();
      }
    });

    var ratingEl = doc.querySelector('#rating');
    var novelIdNum = ratingEl ? ratingEl.getAttribute('data-novel-id') : null;
    var chapters = [];

    if (novelIdNum) {
      try {
        var chData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_AN + '/ajax-chapter-option?novelId=' + novelIdNum));
        var chDoc = new DOMParser().parseFromString(chData.html, 'text/html');
        chDoc.querySelectorAll('select > option, li > a').forEach(function(el) {
          var val = el.getAttribute('value') || el.getAttribute('href') || '';
          if (!val) return;
          var parts = val.replace(/^\//, '').replace(/\.html$/, '').split('/');
          if (parts.length < 2) return;
          var chSlug = parts.slice(1).join('/');
          var chId = novelId + '/' + chSlug;
          var chTitle = el.textContent.trim() || ('Chapter ' + (chapters.length + 1));
          var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
          var num = numMatch ? parseFloat(numMatch[1]) : (chapters.length + 1);
          chapters.push({ id: chId, title: chTitle, number: num, published_at: null });
        });
      } catch(e) {}
    }

    return { id: novelId, title: title, cover_url: cover, description: desc, status: status, genres: genres, authors: authors, provider: 'allnovel', url: _AN + '/' + novelId + '.html', chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var slug = parts[0];
    var chSlug = parts.slice(1).join('/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_AN + '/' + slug + '/' + chSlug + '.html'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('#chapter-content, #chr-content');
    if (contentEl) {
      contentEl.querySelectorAll('script, style, .ads').forEach(function(el) { el.remove(); });
    }
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _anSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_AN + '/hot-novel?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _anParseCards(doc);
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_AN + '/latest-release-novel?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _anParseCards(doc);
  },
};
