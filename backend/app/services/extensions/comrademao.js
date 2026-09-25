// Based on QuickNovel ComrademaoProvider (WordPress Buku/BS theme)
var _CM = 'https://comrademao.com';

function _cmSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '')
    .replace(/\(end of this chapter\)/gi, '');
}

function _cmParseCards(doc) {
  var results = [];
  doc.querySelectorAll('.bs').forEach(function(item) {
    var a = item.querySelector('a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var title = a.textContent.trim() || a.getAttribute('title') || '';
    var img = item.querySelector('img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;
    var slug = href.replace(_CM, '').replace(/^\//, '').replace(/\/$/, '');
    if (!slug) return;
    results.push({ id: slug, title: title, cover_url: cover, provider: 'comrademao', url: href, status: null });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var url = _CM + '/?s=' + encodeURIComponent(query) + '&post_type=novel';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _cmParseCards(doc);
  },

  async getMangaDetail(novelId) {
    var url = novelId.startsWith('http') ? novelId : _CM + '/' + novelId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var imgEl = doc.querySelector('div.thumb > img');
    var title = (imgEl ? imgEl.getAttribute('title') : null) || novelId;
    title = title.replace(/\s*[–-]\s*Comrade Mao$/i, '').trim();

    var cover = imgEl ? imgEl.getAttribute('src') : null;

    var genres = [];
    var authors = [];
    var status = null;
    doc.querySelectorAll('div.infox .wd-full').forEach(function(el) {
      var txt = el.textContent || '';
      if (/Genre/i.test(txt)) {
        el.querySelectorAll('a').forEach(function(a) { var g = a.textContent.trim(); if (g) genres.push(g); });
      } else if (/Tag/i.test(txt)) {
        el.querySelectorAll('a').forEach(function(a) { var g = a.textContent.trim(); if (g && !genres.includes(g)) genres.push(g); });
      } else if (/Publisher/i.test(txt)) {
        var a = el.querySelector('a');
        if (a) authors = [a.textContent.trim()];
      } else if (/Status/i.test(txt)) {
        var a = el.querySelector('a');
        if (a) status = a.textContent.trim();
      }
    });

    var synopsis = null;
    var lastP = doc.querySelectorAll('div.wd-full p');
    if (lastP.length > 0) synopsis = lastP[lastP.length - 1].textContent.trim();

    var chapters = [];
    doc.querySelectorAll('li[data-num]').forEach(function(li) {
      var a = li.querySelector('a');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var chSlug = href.replace(_CM, '').replace(/^\//, '').replace(/\/$/, '');
      var chTitle = li.querySelector('.chapternum') ? li.querySelector('.chapternum').textContent.trim() : a.textContent.trim();
      var num = li.getAttribute('data-num') ? parseFloat(li.getAttribute('data-num')) : (chapters.length + 1);
      chapters.push({ id: chSlug, title: chTitle, number: num, published_at: null });
    });
    chapters.reverse();

    return { id: novelId, title: title, cover_url: cover, description: synopsis, status: status, genres: genres, authors: authors, provider: 'comrademao', url: url, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var url = chapterId.startsWith('http') ? chapterId : _CM + '/' + chapterId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('div[readability]');
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _cmSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_CM + '/novel/?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _cmParseCards(doc);
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_CM + '/novel/?page=' + (page || 1) + '&order=update'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _cmParseCards(doc);
  },
};
