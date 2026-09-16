var _BASE = '{BASE_URL}';

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

var extension = {
  async search(query, page) {
    var pageStr = (page || 1) > 1 ? ('/page/' + page) : '';
    var doc = await _fetchDoc(_BASE + pageStr + '/?s=' + encodeURIComponent(query));
    var results = [];
    var seen = {};
    doc.querySelectorAll('.utao .uta, .listupd .bs, .bsx, .bs').forEach(function(card) {
      var a = card.querySelector('.tt a, h4 a, .title a, a');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var slug = href.replace(/\/$/, '').split('/').pop();
      if (!slug || seen[slug]) return;
      seen[slug] = true;
      var img = card.querySelector('img');
      results.push({
        id: slug,
        title: a.textContent.trim(),
        cover_url: img ? (img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-lazy-src')) : null,
        provider: 'mangathemesia',
        url: href,
        status: null,
      });
    });
    return results;
  },

  async getMangaDetail(mangaId) {
    var doc = await _fetchDoc(_BASE + '/manga/' + mangaId);
    var titleEl = doc.querySelector('h1.entry-title, h1');
    var title = titleEl ? titleEl.textContent.trim() : mangaId;
    var img = doc.querySelector('.thumb img, .info-image img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-lazy-src')) : null;
    var descEl = doc.querySelector('.entry-content, .synopsis, [itemprop="description"]');
    var desc = descEl ? descEl.textContent.trim() : null;

    var genres = [];
    doc.querySelectorAll('.mgen a, a[href*="manga-genre"]').forEach(function(a) {
      genres.push(a.textContent.trim());
    });

    var chapters = [];
    var seen = {};
    doc.querySelectorAll('.clcontent a, #chapterlist a, .eplister a').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      var slug = href.replace(/\/$/, '').split('/').pop();
      var fullId = mangaId + '/chapter/' + slug;
      if (seen[fullId]) return;
      seen[fullId] = true;
      var numMatch = slug.match(/([\d.]+)/);
      var num = numMatch ? parseFloat(numMatch[1]) : 0;
      chapters.push({
        id: href.replace(_BASE, ''),
        title: a.textContent.trim() || ('Chapter ' + num),
        number: num,
        published_at: null,
      });
    });
    chapters.sort(function(a, b) { return b.number - a.number; });

    return {
      id: mangaId,
      title: title,
      cover_url: cover,
      description: desc,
      status: null,
      genres: genres,
      authors: [],
      provider: 'mangathemesia',
      url: _BASE + '/manga/' + mangaId,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var doc = await _fetchDoc(_BASE + chapterId);
    var pages = [];
    doc.querySelectorAll('#readerarea img').forEach(function(img) {
      var src = img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-lazy-src') || img.getAttribute('data-cdn-src');
      if (src) {
         src = src.trim();
         if (src.startsWith('//')) src = 'https:' + src;
         pages.push(src);
      }
    });
    return pages;
  },

  async getPopular(page) {
    var doc = await _fetchDoc(_BASE + '/manga/?page=' + (page || 1) + '&order=popular');
    var results = [];
    var seen = {};
    doc.querySelectorAll('.utao .uta, .listupd .bs, .bsx, .bs').forEach(function(card) {
      var a = card.querySelector('.tt a, h4 a, .title a, a');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var slug = href.replace(/\/$/, '').split('/').pop();
      if (!slug || seen[slug]) return;
      seen[slug] = true;
      var img = card.querySelector('img');
      results.push({
        id: slug,
        title: a.textContent.trim(),
        cover_url: img ? (img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-lazy-src')) : null,
        provider: 'mangathemesia',
        url: href,
        status: null,
      });
    });
    return results;
  },

  async getLatest(page) {
    var doc = await _fetchDoc(_BASE + '/manga/?page=' + (page || 1) + '&order=update');
    var results = [];
    var seen = {};
    doc.querySelectorAll('.utao .uta, .listupd .bs, .bsx, .bs').forEach(function(card) {
      var a = card.querySelector('.tt a, h4 a, .title a, a');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var slug = href.replace(/\/$/, '').split('/').pop();
      if (!slug || seen[slug]) return;
      seen[slug] = true;
      var img = card.querySelector('img');
      results.push({
        id: slug,
        title: a.textContent.trim(),
        cover_url: img ? (img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-lazy-src')) : null,
        provider: 'mangathemesia',
        url: href,
        status: null,
      });
    });
    return results;
  },
};
