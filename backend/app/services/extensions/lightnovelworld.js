var _LNW = 'https://www.lightnovelworld.com';

function _lnwSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

function _lnwParseCards(doc, provider) {
  var results = [];
  doc.querySelectorAll('.novel-item, .book-item, li.novel').forEach(function(item) {
    var a = item.querySelector('a.novel-title, h3 a, .title a, a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var slug = href.split('/novel/').pop().replace(/\/$/, '').split('/')[0];
    if (!slug || slug.length < 2) return;
    var title = (item.querySelector('.novel-title, h3, .title') || a).textContent.trim();
    var img = item.querySelector('img');
    var cover = img ? (img.getAttribute('data-src') || img.getAttribute('src')) : null;
    results.push({ id: slug, title: title, cover_url: cover, provider: provider || 'lightnovelworld', url: _LNW + '/novel/' + slug, status: null });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LNW + '/search?keywords=' + encodeURIComponent(query) + '&page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _lnwParseCards(doc, 'lightnovelworld');
  },

  async getMangaDetail(novelId) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LNW + '/novel/' + novelId));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('h1.novel-title, .novel-info h1');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('.novel-cover img, .book-cover img');
    var cover = img ? (img.getAttribute('data-src') || img.getAttribute('src')) : null;

    var descEl = doc.querySelector('.summary .content, .novel-summary, .description');
    var desc = descEl ? descEl.textContent.trim() : null;

    var genres = [];
    doc.querySelectorAll('.categories a, .genre-item a, .tag').forEach(function(el) {
      var g = el.textContent.trim();
      if (g) genres.push(g);
    });

    var statusEl = doc.querySelector('.header-stats .active, .novel-status');
    var status = statusEl ? statusEl.textContent.trim() : null;

    var authorEl = doc.querySelector('.author a, .novel-author a');
    var authors = authorEl ? [authorEl.textContent.trim()] : [];

    var chapters = [];
    doc.querySelectorAll('#chapter-list li, .chapter-list li').forEach(function(li, i) {
      var a = li.querySelector('a');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var slug = href.split('/novel/' + novelId + '/').pop().replace(/\/$/, '');
      if (!slug) return;
      var chId = novelId + '/' + slug;
      var chTitle = (li.querySelector('.chapter-title, span') || a).textContent.trim();
      var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chTitle.match(/([\d.]+)/);
      var num = numMatch ? parseFloat(numMatch[1]) : (i + 1);
      chapters.push({ id: chId, title: chTitle, number: num, published_at: null });
    });
    chapters.reverse();

    return { id: novelId, title: title, cover_url: cover, description: desc, status: status, genres: genres, authors: authors, provider: 'lightnovelworld', url: _LNW + '/novel/' + novelId, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var novelSlug = parts[0];
    var chSlug = parts.slice(1).join('/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LNW + '/novel/' + novelSlug + '/' + chSlug));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('#chapter-container, .chapter-content, .text-left');
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _lnwSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LNW + '/genre/all/popular?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _lnwParseCards(doc, 'lightnovelworld');
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LNW + '/genre/all/latest?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _lnwParseCards(doc, 'lightnovelworld');
  },
};
