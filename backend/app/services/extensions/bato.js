var _BA = 'https://bato1.com';

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

function _parseCards(doc) {
  var results = [];
  var seen = {};
  doc.querySelectorAll('.original.card-lg .unit, #most-viewed .swiper-slide.unit, .unit, div.unit, a[href*="/manga/"], a[href*="/title/"], a[href*="/series/"]').forEach(function(item) {
    var a = item.tagName === 'A' ? item : (item.querySelector('a.poster, a[href*="/manga/"], a[href*="/title/"], a[href*="/series/"]') || item.querySelector('a'));
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var match = href.match(/\/(manga|title|series)\/([\w-]+)/);
    if (!match) return;
    var id = match[2];
    if (seen[id]) return;
    seen[id] = true;
    var img = item.querySelector('img') || a.querySelector('img');
    var titleEl = item.querySelector('.info > a, [class*="title"], h3, p, span') || a;
    results.push({
      id: id,
      title: (titleEl.textContent || '').trim() || id,
      cover_url: img ? (img.getAttribute('data-src') || img.getAttribute('src')) : null,
      provider: 'bato',
      url: _BA + '/manga/' + id,
      status: null,
    });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var p = page || 1;
    var doc = await _fetchDoc(_BA + '/filter?keyword=' + encodeURIComponent(query) + (p > 1 ? '&page=' + p : ''));
    return _parseCards(doc);
  },

  async getMangaDetail(mangaId) {
    var slug = mangaId.replace(/^https?:\/\/[^/]+\/(manga|title|series)\//, '').replace(/\/$/, '');
    var doc = await _fetchDoc(_BA + '/manga/' + slug);
    var title = (doc.querySelector('h1[itemprop="name"], h1, h3.item-title, [class*="title"]') || {}).textContent || slug;
    var cover = doc.querySelector('.poster img, [class*="poster"] img, .detail-set img, img[alt]');
    var desc = doc.querySelector('.description, [class*="summary"], [class*="description"], .limit-html');
    var genres = [];
    doc.querySelectorAll('.meta div a[href*="/genre/"], [class*="genre"] a, [class*="tag"] a').forEach(function(a) {
      var g = a.textContent.trim();
      if (g && !genres.includes(g)) genres.push(g);
    });
    var authors = [];
    doc.querySelectorAll('.meta div:has(span) a, [class*="author"] a').forEach(function(a) {
      var auth = a.textContent.trim();
      if (auth && !authors.includes(auth)) authors.push(auth);
    });

    // Try modern Bato JSON chapter API first
    var chapters = [];
    try {
      var chApiData = await apiFetch('/manga/proxy/json?url=' + encodeURIComponent(_BA + '/get-chapter-list?slug=' + slug));
      var list = (chApiData && chApiData.data) || (Array.isArray(chApiData) ? chApiData : []);
      list.forEach(function(item) {
        var chSlug = item.chapter_slug || ('chapter-' + item.chapter_num);
        var chId = slug + '/' + chSlug;
        chapters.push({
          id: chId,
          title: item.chapter_name || ('Chapter ' + (item.chapter_num || '')),
          number: typeof item.chapter_num === 'number' ? item.chapter_num : (parseFloat((item.chapter_name || '').match(/[\d.]+/)?.[0]) || 0),
          published_at: item.updated_at || null,
        });
      });
    } catch(e) {
      // Fallback to DOM parsing
    }

    if (chapters.length === 0) {
      doc.querySelectorAll('a[href*="/chapter"], a[href*="/read/"]').forEach(function(a) {
        var href = a.getAttribute('href') || '';
        var chSlug = href.split('/').pop()?.replace(/\?.*/, '') || '';
        if (!chSlug || chSlug === slug) return;
        var text = a.textContent.trim();
        var numM = text.match(/([\d.]+)/);
        var dateEl = a.closest('li,div')?.querySelector('time, [class*="date"]');
        chapters.push({
          id: slug + '/' + chSlug,
          title: text,
          number: numM ? parseFloat(numM[1]) : 0,
          published_at: dateEl ? (dateEl.getAttribute('datetime') || dateEl.textContent.trim()) : null,
        });
      });
    }

    return {
      id: slug,
      title: title.trim(),
      cover_url: cover ? (cover.getAttribute('data-src') || cover.getAttribute('src')) : null,
      description: desc ? desc.textContent.trim() : null,
      status: null,
      genres: genres,
      authors: authors,
      provider: 'bato',
      url: _BA + '/manga/' + slug,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var readUrl = chapterId.startsWith('http')
      ? chapterId
      : (chapterId.includes('/') ? (_BA + '/read/' + chapterId) : (_BA + '/read/' + chapterId));

    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(readUrl));
    var html = (data && data.html) || '';
    var pages = [];

    // Bato embeds image list in script: var imgHttpLis = [...]
    var m = html.match(/var\s+imgHttpLis\s*=\s*(\[[^\]]+\])/);
    if (m) {
      try {
        var arr = JSON.parse(m[1].replace(/'/g, '"'));
        if (Array.isArray(arr) && arr.length > 0) return arr.filter(Boolean);
      } catch(e) {}
    }

    // Modern Bato pages container
    var doc = new DOMParser().parseFromString(html, 'text/html');
    doc.querySelectorAll('.pages .page:not(.notice-page) img, .page:not(.notice-page) img, .viewer img').forEach(function(img) {
      var src = img.getAttribute('data-src') || img.getAttribute('src');
      if (src && !src.includes('/banner/') && !src.includes('banner') && src.startsWith('http')) {
        pages.push(src);
      }
    });

    if (pages.length === 0) {
      doc.querySelectorAll('img[class*="page"], [data-index] img').forEach(function(img) {
        var src = img.getAttribute('data-src') || img.getAttribute('src');
        if (src && src.startsWith('http') && !src.includes('/banner/')) {
          pages.push(src);
        }
      });
    }

    return pages;
  },

  async getPopular(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_BA + '/filter?sort=views' + (p > 1 ? '&page=' + p : ''));
    return _parseCards(doc);
  },

  async getLatest(page) {
    var p = page || 1;
    var path = p === 1 ? '/updated' : ('/updated/page/' + p);
    var doc = await _fetchDoc(_BA + path);
    return _parseCards(doc);
  },
};
