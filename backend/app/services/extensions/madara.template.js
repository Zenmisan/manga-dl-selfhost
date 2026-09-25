var _BASE = '{BASE_URL}';
var _PROVIDER = '{SOURCE_ID}';
var _genreCache = null; // module-level, persists for the session

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

var _CARD_SEL = '.c-tabs-item__content, .manga-item, .page-item-detail, .c-blog-post';

function _parseCard(card) {
  var a = card.querySelector('.post-title a, h3.h4 a, h3 a, h5 a, a[href*="/manga/"], a[href*="/series/"], a[href*="/webtoon/"], a[href*="/serie/"]');
  if (!a) return null;
  var href = a.getAttribute('href') || '';
  var slug = href.replace(/\/$/, '').split('/').pop();
  if (!slug) return null;
  var titleEl = card.querySelector('.post-title, h3.h4, h3, h5');
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
    doc.querySelectorAll('a[href*="manga-genre"]').forEach(function(a) {
      var href = (a.getAttribute('href') || '').replace(/\/?$/, '/');
      if (!href.includes('/manga-genre/') || seen[href]) return;
      seen[href] = true;
      _genreCache.push(href);
    });
  } catch(e) {}
  return _genreCache;
}

// page 1: sorted listing; pages 2+: round-robin genre pages (5 genres per batch)
// encodes as: batchIdx = floor((page-2)/batchSize), genrePage = batchIdx/ceil(genres/batchSize)
async function _browseByPage(orderBy, page) {
  var p = page || 1;
  var BATCH = 5; // genres per page

  if (p === 1) {
    var doc = await _fetchDoc(_BASE + '/manga/page/1/?m_orderby=' + orderBy);
    var r = _parseCards(doc);
    if (r.length > 0) return r;
    // If sorted page returns nothing, fall through to genre fetch below
  }

  var genres = await _loadGenres();
  if (!genres.length) {
    // No genres — plain pagination fallback
    var doc2 = await _fetchDoc(_BASE + '/manga/page/' + p + '/?m_orderby=' + orderBy);
    return _parseCards(doc2);
  }

  // Page 2+ (or page 1 fallback): cycle genre batches
  // offset = p when p>1, else 1 (to treat empty p1 as first genre batch)
  var offset = (p > 1 ? p : 1) - 1; // 0-indexed
  var totalBatches = Math.ceil(genres.length / BATCH); // batches to exhaust all genres page1
  var batchIdx = (offset - 1) % totalBatches; // which batch of genres
  var genrePage = Math.floor((offset - 1) / totalBatches) + 1; // which page within each genre

  var start = batchIdx * BATCH;
  var batch = genres.slice(start, start + BATCH);
  if (!batch.length) return [];

  // Fetch all genres in this batch in parallel
  var fetches = batch.map(function(gUrl) {
    return _fetchDoc(gUrl + 'page/' + genrePage + '/').then(_parseCards).catch(function() { return []; });
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
    var doc = await _fetchDoc(_BASE + '/?s=' + encodeURIComponent(query) + '&post_type=wp-manga&paged=' + (page || 1));
    return _parseCards(doc);
  },

  async getMangaDetail(mangaId) {
    var paths = ['/manga/', '/series/', '/webtoon/', '/serie/'];
    var doc = null;
    var finalUrl = '';
    for (var i = 0; i < paths.length; i++) {
      try {
        finalUrl = _BASE + paths[i] + mangaId;
        doc = await _fetchDoc(finalUrl);
        if (doc.querySelector('h1')) break;
      } catch(e) {}
    }
    if (!doc) throw new Error('Manga details page not found');

    var titleEl = doc.querySelector('.post-title h1, h1');
    var title = titleEl ? titleEl.textContent.trim() : mangaId;
    var img = doc.querySelector('.summary_image img');
    var cover = img ? (
      img.getAttribute('data-src') || img.getAttribute('data-lazy-src') ||
      img.getAttribute('data-wpfc-original-src') || img.getAttribute('src')
    ) : null;
    var descEl = doc.querySelector('.description-summary, .summary-content, .manga-excerpt, .post-content_item p');
    var desc = descEl ? descEl.textContent.trim() : null;

    var genres = [];
    doc.querySelectorAll('.genres-content a, a[href*="manga-genre"]').forEach(function(a) {
      genres.push(a.textContent.trim());
    });

    var chapters = [];
    var seen = {};
    doc.querySelectorAll('.wp-manga-chapter a').forEach(function(a) {
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
      url: finalUrl,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var doc = await _fetchDoc(_BASE + chapterId);
    var pages = [];
    doc.querySelectorAll('.page-break img, img.wp-manga-chapter-img').forEach(function(img) {
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
    return _browseByPage('views', page);
  },

  async getLatest(page) {
    return _browseByPage('latest', page);
  },
};
