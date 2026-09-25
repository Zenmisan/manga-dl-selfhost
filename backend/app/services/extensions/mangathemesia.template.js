var _BASE = '{BASE_URL}';
var _PROVIDER = '{SOURCE_ID}';
var _genreCache = null;

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

function _getImg(el) {
  if (!el) return null;
  var img = el.querySelector('img');
  if (!img) return null;
  return img.getAttribute('data-src') ||
    img.getAttribute('data-lazy-src') ||
    img.getAttribute('data-wpfc-original-src') ||
    img.getAttribute('src') ||
    (img.getAttribute('srcset') || '').split(' ')[0] ||
    null;
}

var _CARD_SEL = '.utao .uta, .listupd .bs, .bsx, .bs';

function _parseCard(card) {
  var a = card.querySelector('.tt a, h4 a, .title a, a');
  if (!a) return null;
  var href = a.getAttribute('href') || '';
  var slug = href.replace(/\/$/, '').split('/').pop();
  if (!slug) return null;
  var titleEl = card.querySelector('.tt, h4, .title');
  var title = (titleEl ? titleEl.textContent.trim() : '') || a.textContent.trim();
  return {
    id: slug,
    title: title,
    cover_url: _getImg(card),
    provider: _PROVIDER,
    url: href,
    status: null,
  };
}

function _parseCards(doc) {
  var results = []; var seen = {};
  doc.querySelectorAll(_CARD_SEL).forEach(function(card) {
    var r = _parseCard(card);
    if (r && !seen[r.id]) { seen[r.id] = true; results.push(r); }
  });
  return results;
}

async function _loadGenres() {
  if (_genreCache !== null) return _genreCache;
  _genreCache = [];
  try {
    var doc = await _fetchDoc(_BASE + '/manga/?page=1');
    var seen = {};
    doc.querySelectorAll('a[href*="/genre"], a[href*="/genres"]').forEach(function(a) {
      var href = (a.getAttribute('href') || '').replace(/\/?$/, '/');
      if (!href || seen[href]) return;
      // exclude the genre index page itself
      if (href.endsWith('/genre/') || href.endsWith('/genres/')) return;
      seen[href] = true;
      _genreCache.push(href);
    });
  } catch(e) {}
  return _genreCache;
}

async function _browseByPage(orderBy, page) {
  var p = page || 1;
  var BATCH = 5;

  if (p === 1) {
    var doc = await _fetchDoc(_BASE + '/manga/?page=1&order=' + orderBy);
    var r = _parseCards(doc);
    if (r.length > 0) return r;
  }

  var genres = await _loadGenres();
  if (!genres.length) {
    var doc2 = await _fetchDoc(_BASE + '/manga/?page=' + p + '&order=' + orderBy);
    return _parseCards(doc2);
  }

  var offset = (p > 1 ? p : 1) - 1;
  var totalBatches = Math.ceil(genres.length / BATCH);
  var batchIdx = (offset - 1) % totalBatches;
  var genrePage = Math.floor((offset - 1) / totalBatches) + 1;

  var start = batchIdx * BATCH;
  var batch = genres.slice(start, start + BATCH);
  if (!batch.length) return [];

  var fetches = batch.map(function(gUrl) {
    var url = gUrl + 'page/' + genrePage + '/?order=' + orderBy;
    return _fetchDoc(url).then(_parseCards).catch(function() { return []; });
  });
  var pages = await Promise.all(fetches);
  var merged = []; var seen = {};
  pages.forEach(function(arr) {
    arr.forEach(function(r) {
      if (!seen[r.id]) { seen[r.id] = true; merged.push(r); }
    });
  });
  return merged;
}

var extension = {
  async search(query, page) {
    var pageStr = (page || 1) > 1 ? ('/page/' + page) : '';
    var doc = await _fetchDoc(_BASE + pageStr + '/?s=' + encodeURIComponent(query));
    return _parseCards(doc);
  },

  async getMangaDetail(mangaId) {
    var doc = await _fetchDoc(_BASE + '/manga/' + mangaId);
    var titleEl = doc.querySelector('h1.entry-title, h1');
    var title = titleEl ? titleEl.textContent.trim() : mangaId;
    var img = doc.querySelector('.thumb img, .info-image img');
    var cover = img ? (
      img.getAttribute('data-src') || img.getAttribute('data-lazy-src') ||
      img.getAttribute('data-wpfc-original-src') || img.getAttribute('src')
    ) : null;
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
      provider: _PROVIDER,
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
    return _browseByPage('popular', page);
  },

  async getLatest(page) {
    return _browseByPage('update', page);
  },
};
