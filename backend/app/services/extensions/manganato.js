var _MN = 'https://manganato.com';
var _RMN = 'https://readmanganato.com';

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

function _parseCards(doc) {
  var results = [];
  var seen = {};
  doc.querySelectorAll('.content-genres-item, .story_item, .list-story-item').forEach(function(el) {
    var a = el.querySelector('h3 a, a.genres-item-img, a[href*="readmanganato"], a[href*="chapmanganato"]');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var id = href.replace(/\/$/, '').split('/').pop();
    if (!id || seen[id]) return;
    seen[id] = true;
    var img = el.querySelector('img');
    var titleEl = el.querySelector('h3 a, .genres-item-name');
    results.push({
      id: id,
      title: titleEl ? titleEl.textContent.trim() : id,
      cover_url: img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null,
      provider: 'manganato',
      url: href,
      status: null,
    });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var p = page || 1;
    var q = query.toLowerCase().replace(/\s+/g, '_');
    var doc = await _fetchDoc(_MN + '/search/story/' + encodeURIComponent(q) + (p > 1 ? '?page=' + p : ''));
    return _parseCards(doc);
  },

  async getMangaDetail(mangaId) {
    var url = _RMN + '/manga-' + mangaId;
    var doc = await _fetchDoc(url);
    var title = (doc.querySelector('.story-info-right h1, .manga-info-text h1') || {}).textContent || mangaId;
    var cover = doc.querySelector('.story-info-left img, .manga-info-pic img');
    var desc = doc.querySelector('#panel-story-info-description, #noidungm');
    var chapters = [];
    doc.querySelectorAll('.row-content-chapter li, .chapter-list .row').forEach(function(row) {
      var a = row.querySelector('a');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var chSlug = href.replace(/\/$/, '').split('/').pop();
      var numM = chSlug.match(/([\d.]+)/);
      var dateEl = row.querySelector('span[title], .chapter-time');
      chapters.push({
        id: mangaId + '/' + chSlug,
        title: a.textContent.trim(),
        number: numM ? parseFloat(numM[1]) : 0,
        published_at: dateEl ? (dateEl.getAttribute('title') || dateEl.textContent.trim()) : null,
      });
    });
    return {
      id: mangaId,
      title: title.trim(),
      cover_url: cover ? (cover.getAttribute('src') || cover.getAttribute('data-src')) : null,
      description: desc ? desc.textContent.replace('Description :', '').trim() : null,
      status: null, genres: [], authors: [],
      provider: 'manganato',
      url: url,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var parts = chapterId.split('/');
    var chSlug = parts.pop();
    var mangaId = parts.join('/');
    var url = _RMN + '/manga-' + mangaId + '/' + chSlug;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var pages = [];
    doc.querySelectorAll('.container-chapter-reader img').forEach(function(img) {
      var src = img.getAttribute('src') || img.getAttribute('data-src');
      if (src && src.startsWith('http')) pages.push(src);
    });
    return pages;
  },

  async getPopular(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_MN + '/genre-all/' + p + '?type=topview');
    return _parseCards(doc);
  },

  async getLatest(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_MN + '/genre-all/' + p);
    return _parseCards(doc);
  },
};
