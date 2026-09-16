var _BASE = '{BASE_URL}';

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

var extension = {
  async search(query, page) {
    var doc = await _fetchDoc(_BASE + '/?s=' + encodeURIComponent(query) + '&post_type=wp-manga');
    var results = [];
    var seen = {};
    doc.querySelectorAll('.c-tabs-item__content, .manga-item, .page-item-detail, .c-blog-post').forEach(function(card) {
      var a = card.querySelector('.post-title a, h3.h4 a, h3 a, h5 a, a[href*="/manga/"], a[href*="/series/"], a[href*="/webtoon/"], a[href*="/serie/"]');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      if (!href.includes('/manga/') && !href.includes('/series/') && !href.includes('/webtoon/') && !href.includes('/serie/')) return;
      var slug = href.replace(/\/$/, '').split('/').pop();
      if (!slug || seen[slug]) return;
      seen[slug] = true;
      var img = card.querySelector('img');
      results.push({
        id: slug,
        title: a.textContent.trim(),
        cover_url: img ? (img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-lazy-src')) : null,
        provider: 'madara',
        url: href,
        status: null,
      });
    });
    return results;
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
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-lazy-src')) : null;
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
      provider: 'madara',
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
    var doc = await _fetchDoc(_BASE + '/manga/page/' + (page || 1) + '/?m_orderby=views');
    var results = [];
    var seen = {};
    doc.querySelectorAll('.c-tabs-item__content, .manga-item, .page-item-detail, .c-blog-post').forEach(function(card) {
      var a = card.querySelector('.post-title a, h3.h4 a, h3 a, h5 a, a[href*="/manga/"], a[href*="/series/"], a[href*="/webtoon/"], a[href*="/serie/"]');
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
        provider: 'madara',
        url: href,
        status: null,
      });
    });
    return results;
  },

  async getLatest(page) {
    var doc = await _fetchDoc(_BASE + '/manga/page/' + (page || 1) + '/?m_orderby=latest');
    var results = [];
    var seen = {};
    doc.querySelectorAll('.c-tabs-item__content, .manga-item, .page-item-detail, .c-blog-post').forEach(function(card) {
      var a = card.querySelector('.post-title a, h3.h4 a, h3 a, h5 a, a[href*="/manga/"], a[href*="/series/"], a[href*="/webtoon/"], a[href*="/serie/"]');
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
        provider: 'madara',
        url: href,
        status: null,
      });
    });
    return results;
  },
};
