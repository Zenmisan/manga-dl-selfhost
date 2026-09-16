var _KK = 'https://www.mangakakalot.gg';

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

function _parseCards(doc) {
  var results = [];
  var seen = {};
  doc.querySelectorAll('.truyen-list .list-truyen-item-wrap, .panel_story_list .story_item, .list-manga-wraper .story_item, .search-story-item').forEach(function(el) {
    var a = el.querySelector('h3 a, .story_name a, a[href*="/manga/"]');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var id = href.replace(/\/$/, '').split('/').pop();
    if (!id || seen[id]) return;
    seen[id] = true;
    var img = el.querySelector('img');
    results.push({
      id: id,
      title: a.textContent.trim(),
      cover_url: img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null,
      provider: 'mangakakalot',
      url: href.startsWith('http') ? href : (_KK + href),
      status: null,
    });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var p = page || 1;
    var q = query.toLowerCase().replace(/\s+/g, '_');
    var url = _KK + '/search/story/' + encodeURIComponent(q) + (p > 1 ? '?page=' + p : '');
    var doc = await _fetchDoc(url);
    return _parseCards(doc);
  },

  async getMangaDetail(mangaId) {
    var doc = await _fetchDoc(_KK + '/manga/' + mangaId);
    var title = (doc.querySelector('.manga-info-text h1, .story-info-right h1') || {}).textContent || mangaId;
    var cover = doc.querySelector('.manga-info-pic img, .story-info-left img');
    var desc = doc.querySelector('#noidungm, .panel-story-info-description');
    var chapters = [];
    // Try API first
    try {
      var apiData = await apiFetch('/manga/proxy/json?url=' + encodeURIComponent(_KK + '/api/manga/' + mangaId + '/chapters?limit=-1'));
      if (apiData && apiData.data && apiData.data.chapters) {
        apiData.data.chapters.forEach(function(ch) {
          if (!ch.chapter_slug) return;
          chapters.push({
            id: mangaId + '/' + ch.chapter_slug,
            title: ch.chapter_name || ('Chapter ' + ch.chapter_num),
            number: parseFloat(ch.chapter_num) || 0,
            published_at: ch.updated_at || null,
          });
        });
      }
    } catch(e) {}
    // Fallback to HTML scraping
    if (!chapters.length) {
      doc.querySelectorAll('.chapter-list .row, .row-content-chapter li').forEach(function(row) {
        var a = row.querySelector('a');
        if (!a) return;
        var href = a.getAttribute('href') || '';
        var parts = href.split('/');
        var chSlug = parts.pop() || parts.pop();
        var numM = chSlug.match(/([\d.]+)/);
        chapters.push({
          id: mangaId + '/' + chSlug,
          title: a.textContent.trim(),
          number: numM ? parseFloat(numM[1]) : 0,
          published_at: null,
        });
      });
    }
    return {
      id: mangaId,
      title: title.trim(),
      cover_url: cover ? (cover.getAttribute('src') || cover.getAttribute('data-src')) : null,
      description: desc ? desc.textContent.replace('Description :', '').trim() : null,
      status: null, genres: [], authors: [],
      provider: 'mangakakalot',
      url: _KK + '/manga/' + mangaId,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var url = _KK + '/manga/' + chapterId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var html = data.html;
    var doc = new DOMParser().parseFromString(html, 'text/html');
    var pages = [];
    doc.querySelectorAll('.container-chapter-reader img, .reading-content img').forEach(function(img) {
      var src = img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-lazy-src');
      if (src && src.startsWith('http')) pages.push(src);
    });
    return pages;
  },

  async getPopular(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_KK + '/manga_list?type=topview&category=all&state=all&page=' + p);
    return _parseCards(doc);
  },

  async getLatest(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_KK + '/manga_list?type=latest&category=all&state=all&page=' + p);
    return _parseCards(doc);
  },
};
