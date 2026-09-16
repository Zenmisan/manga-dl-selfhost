var _RR = 'https://www.royalroad.com';

function _rrSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

function _rrParseCards(doc, provider) {
  var results = [];
  doc.querySelectorAll('.fiction-list-item, .row.fiction-item').forEach(function(item) {
    var a = item.querySelector('h2 a, h3 a, .fiction-title a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var idMatch = href.match(/\/fiction\/(\d+)/);
    if (!idMatch) return;
    var id = idMatch[1];
    var title = a.textContent.trim();
    var img = item.querySelector('img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;
    if (cover && cover.startsWith('/')) cover = _RR + cover;
    results.push({ id: id, title: title, cover_url: cover, provider: provider || 'royalroad', url: _RR + '/fiction/' + id, status: null });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_RR + '/fictions/search?title=' + encodeURIComponent(query) + '&page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _rrParseCards(doc, 'royalroad');
  },

  async getMangaDetail(novelId) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_RR + '/fiction/' + novelId));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('h1.font-white');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('.cover-art img, .thumbnail img, img.thumbnail');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;
    if (cover && cover.startsWith('/')) cover = _RR + cover;

    var descEl = doc.querySelector('.description .hidden-content, .description');
    var desc = descEl ? descEl.textContent.trim() : null;

    var genres = [];
    doc.querySelectorAll('.tags .label, .fiction-tag').forEach(function(el) {
      var g = el.textContent.trim();
      if (g) genres.push(g);
    });

    var statusEl = doc.querySelector('.label-default, .label-success');
    var status = statusEl ? statusEl.textContent.trim() : null;

    var authorEl = doc.querySelector('.fic-title h4 a, [property="author"] a');
    var authors = authorEl ? [authorEl.textContent.trim()] : [];

    var chapters = [];
    doc.querySelectorAll('#chapters tr.chapter-row, table#chapters tbody tr').forEach(function(row) {
      var a = row.querySelector('td:first-child a');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var chIdMatch = href.match(/\/chapter\/(\d+)/);
      if (!chIdMatch) return;
      var chId = novelId + '/chapter/' + chIdMatch[1];
      var chTitle = a.textContent.trim();
      var numMatch = chTitle.match(/chapter\s+([\d.]+)/i);
      var num = numMatch ? parseFloat(numMatch[1]) : chapters.length + 1;
      var dateEl = row.querySelector('time');
      chapters.push({ id: chId, title: chTitle, number: num, published_at: dateEl ? dateEl.getAttribute('datetime') : null });
    });
    chapters.reverse();

    return { id: novelId, title: title, cover_url: cover, description: desc, status: status, genres: genres, authors: authors, provider: 'royalroad', url: _RR + '/fiction/' + novelId, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/chapter/');
    var novelId = parts[0];
    var chId = parts[1];
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_RR + '/fiction/' + novelId + '/chapter/' + chId));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('.chapter-content, .chapter-inner, .prose');
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _rrSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_RR + '/fictions/best-rated?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _rrParseCards(doc, 'royalroad');
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_RR + '/fictions/latest-updates?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _rrParseCards(doc, 'royalroad');
  },
};
