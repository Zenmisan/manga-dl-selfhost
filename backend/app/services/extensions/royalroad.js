var _RR = 'https://www.royalroad.com';

function _rrSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

// RoyalRoad injects hidden elements via inline CSS classes to foil scrapers.
// Parse all <style> blocks, find selectors for hidden classes, remove matching elements.
function _rrRemoveHidden(doc, contentEl) {
  var styleBlocks = doc.querySelectorAll('style');
  styleBlocks.forEach(function(style) {
    var text = style.textContent || '';
    var lines = text.split('\n');
    lines.forEach(function(line) {
      var m = line.match(/^\s*(\.[^\s{,]+)/);
      if (!m) return;
      var selector = m[1].trim();
      if (!selector || selector.length < 2) return;
      try {
        contentEl.querySelectorAll(selector).forEach(function(el) { el.remove(); });
      } catch(e) {}
    });
  });
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

    var img = doc.querySelector('.cover-art-container img, .cover-art img, .fic-header img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;
    if (cover && cover.startsWith('/')) cover = _RR + cover;

    var descEl = doc.querySelector('.description .hidden-content, .description');
    var desc = descEl ? descEl.textContent.trim() : null;

    var genres = [];
    doc.querySelectorAll('span.tags > a, .fiction-tag').forEach(function(el) {
      var g = el.textContent.trim();
      if (g) genres.push(g);
    });

    var statusEl = doc.querySelector('div.col-md-8 span.label-default, div.col-md-8 span.label-success, div.col-md-8 span.label');
    var status = statusEl ? statusEl.textContent.trim() : null;

    var authorEl = doc.querySelector('h4.font-white span a, .fic-title h4 a, [property="author"] a');
    var authors = authorEl ? [authorEl.textContent.trim()] : [];

    // Chapters: use data-url on <tr> rows (QuickNovel approach — more reliable than <a> href)
    var chapters = [];
    doc.querySelectorAll('div.portlet-body table tbody tr, #chapters tr.chapter-row, table#chapters tbody tr').forEach(function(row, idx) {
      var url = row.getAttribute('data-url');
      if (!url) {
        var a = row.querySelector('td:first-child a');
        if (!a) return;
        url = a.getAttribute('href');
      }
      if (!url) return;
      var chIdMatch = url.match(/\/chapter\/(\d+)/);
      if (!chIdMatch) return;
      var chId = novelId + '/chapter/' + chIdMatch[1];
      var nameEl = row.querySelector('td:first-child a');
      var chTitle = nameEl ? nameEl.textContent.trim() : ('Chapter ' + chIdMatch[1]);
      var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chTitle.match(/^(\d+(?:\.\d+)?)/) || chTitle.match(/([\d.]+)/);
      var num = numMatch ? parseFloat(numMatch[1]) : (idx + 1);
      var dateEl = row.querySelector('time');
      chapters.push({ id: chId, title: chTitle, number: num, published_at: dateEl ? (dateEl.getAttribute('datetime') || dateEl.textContent.trim()) : null });
    });

    return { id: novelId, title: title, cover_url: cover, description: desc, status: status, genres: genres, authors: authors, provider: 'royalroad', url: _RR + '/fiction/' + novelId, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var url;
    if (chapterId.startsWith('/fiction/')) {
      url = _RR + chapterId;
    } else {
      var parts = chapterId.split('/chapter/');
      var novelId = parts[0];
      var chId = parts[1];
      url = _RR + '/fiction/' + novelId + '/chapter/' + chId;
    }
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('.chapter-content');
    if (!contentEl) contentEl = doc.querySelector('.chapter-inner, .prose');
    if (!contentEl) return { content: '<p>Chapter content not found.</p>', format: 'html' };
    // Remove hidden anti-scraper elements before extracting HTML
    _rrRemoveHidden(doc, contentEl);
    var content = contentEl.innerHTML;
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
