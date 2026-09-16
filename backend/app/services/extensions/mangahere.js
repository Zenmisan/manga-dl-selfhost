var _MH = 'https://www.mangahere.cc';

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

function _parseCards(doc) {
  var results = [];
  var seen = {};
  doc.querySelectorAll('.manga-list-1-list li, .manga-list-4-list li, .result-list li').forEach(function(el) {
    var a = el.querySelector('a.manga-list-1-cover, a[href*="/manga/"], p.manga-list-1-item-title a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var id = href.replace(/^\/manga\//, '').replace(/\/$/, '');
    if (!id || seen[id]) return;
    seen[id] = true;
    var img = el.querySelector('img.manga-list-1-cover');
    var titleEl = el.querySelector('.manga-list-1-item-title a, a[title]');
    results.push({
      id: id,
      title: titleEl ? (titleEl.getAttribute('title') || titleEl.textContent.trim()) : id,
      cover_url: img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null,
      provider: 'mangahere',
      url: _MH + '/manga/' + id,
      status: null,
    });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var p = page || 1;
    var url = _MH + '/search?title=' + encodeURIComponent(query) + '&page=' + p;
    var doc = await _fetchDoc(url);
    return _parseCards(doc);
  },

  async getMangaDetail(mangaId) {
    var doc = await _fetchDoc(_MH + '/manga/' + mangaId);
    var title = (doc.querySelector('.detail-info-right-title-font, h1.detail-info-right-title') || {}).textContent || mangaId;
    var cover = doc.querySelector('.detail-info-cover img');
    var desc = doc.querySelector('#show, .fullcontent');
    var genres = [];
    doc.querySelectorAll('.detail-info-right-tag-list a').forEach(function(a) { genres.push(a.textContent.trim()); });
    var authors = [];
    doc.querySelectorAll('.detail-info-right-say a').forEach(function(a) { authors.push(a.textContent.trim()); });
    var chapters = [];
    doc.querySelectorAll('.detail-main-list li a').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      var chId = href.replace('/manga/' + mangaId + '/', '').replace(/\/$/, '');
      var titleEl = a.querySelector('.title3');
      var dateEl = a.querySelector('.title2');
      var numM = chId.match(/c([\d.]+)/i);
      chapters.push({
        id: mangaId + '/' + chId,
        title: titleEl ? titleEl.textContent.trim() : chId,
        number: numM ? parseFloat(numM[1]) : 0,
        published_at: dateEl ? dateEl.textContent.trim() : null,
      });
    });
    return {
      id: mangaId,
      title: title.trim(),
      cover_url: cover ? (cover.getAttribute('src') || cover.getAttribute('data-src')) : null,
      description: desc ? desc.textContent.trim() : null,
      status: null, genres: genres, authors: authors,
      provider: 'mangahere',
      url: _MH + '/manga/' + mangaId,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var parts = chapterId.split('/');
    var chSlug = parts.pop();
    var mId = parts.join('/');
    var url = _MH + '/manga/' + mId + '/' + chSlug + '/1.html';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var html = data.html;
    // MangaHere uses JS to load page count
    var totalM = html.match(/"total"\s*:\s*(\d+)/);
    var total = totalM ? parseInt(totalM[1]) : 0;
    if (!total) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      var opts = doc.querySelectorAll('.pager-list-left option');
      total = opts.length || 1;
    }
    var pages = [];
    // Extract from script: var imagecount=N; var guidkey='...';
    var guidM = html.match(/guidkey\s*=\s*'([^']+)'/);
    var imgM = html.match(/imagecount\s*=\s*(\d+)/);
    if (imgM) total = parseInt(imgM[1]);
    if (guidM && total) {
      for (var i = 1; i <= total; i++) {
        pages.push(_MH + '/manga/' + mId + '/' + chSlug + '/' + i + '.html');
      }
      // These are page URLs, not direct images — return them as-is (reader will handle)
      // Actually we need direct image URLs. Re-fetch each page is too slow.
      // Fall back to fetching page 1 and extracting the CDN image pattern.
      var doc2 = new DOMParser().parseFromString(html, 'text/html');
      var img1 = doc2.querySelector('#image');
      if (img1) {
        var src1 = img1.getAttribute('src') || '';
        // Pattern: https://mhcdn.net/store/manga/{id}/{ch}/{N}.jpg
        var base = src1.replace(/\/1\.(jpg|png|webp).*$/, '/');
        pages = [];
        for (var j = 1; j <= total; j++) {
          pages.push(base + j + '.jpg');
        }
      }
    }
    if (!pages.length) {
      var doc3 = new DOMParser().parseFromString(html, 'text/html');
      var imgEl = doc3.querySelector('#image');
      if (imgEl) pages.push(imgEl.getAttribute('src'));
    }
    return pages.filter(Boolean);
  },

  async getPopular(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_MH + '/directory/' + p + '.htm');
    return _parseCards(doc);
  },

  async getLatest(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_MH + '/directory/' + p + '.htm?latest');
    return _parseCards(doc);
  },
};
