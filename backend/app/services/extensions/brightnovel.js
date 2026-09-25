// Based on QuickNovel BrightNovelProvider (Inertia/Laravel app)
var _BN = 'https://brightnovels.com';

function _bnSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

var extension = {
  async search(query, page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_BN + '/api/search?query=' + encodeURIComponent(query)));
    var json = null;
    try { json = JSON.parse(data.html || data.text || ''); } catch(e) {}
    if (!json || !json.data || !json.data.series) return [];
    return json.data.series.map(function(s) {
      return { id: s.slug, title: s.title, cover_url: s.cover ? s.cover.url : null, provider: 'brightnovel', url: _BN + '/series/' + s.slug, status: null };
    });
  },

  async getMangaDetail(novelId) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_BN + '/series/' + novelId));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var dataPageEl = doc.querySelector('div#app');
    var dataPage = dataPageEl ? dataPageEl.getAttribute('data-page') : null;
    var json = null;
    if (dataPage) { try { json = JSON.parse(dataPage); } catch(e) {} }

    var title = novelId;
    var cover = null;
    var desc = null;
    var genres = [];
    var authors = [];
    var status = null;

    if (json && json.props && json.props.series) {
      var s = json.props.series;
      title = s.title || novelId;
      cover = s.cover ? s.cover.url : null;
      desc = s.description || null;
      status = s.story_state || null;
      if (s.genres) genres = s.genres.map(function(g) { return g.name; });
      if (s.user) authors = [s.user.username];
    }

    var chapters = [];
    try {
      var chData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_BN + '/series/' + novelId + '/chapters/free?loaded=0&sort_order=desc'));
      var chJson = null;
      try { chJson = JSON.parse(chData.html || chData.text || ''); } catch(e) {}
      if (chJson && chJson.chapters) {
        var chArr = chJson.chapters.slice().reverse();
        chArr.forEach(function(ch, i) {
          if (ch.is_premium) return;
          var chId = novelId + '/' + ch.slug;
          chapters.push({ id: chId, title: ch.name, number: i + 1, published_at: ch.updated_at ? ch.updated_at.split('T')[0] : null });
        });
      }
    } catch(e) {}

    return { id: novelId, title: title, cover_url: cover, description: desc, status: status, genres: genres, authors: authors, provider: 'brightnovel', url: _BN + '/series/' + novelId, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var seriesSlug = parts[0];
    var chSlug = parts.slice(1).join('/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_BN + '/series/' + seriesSlug + '/' + chSlug));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var dataPageEl = doc.querySelector('div#app');
    var dataPage = dataPageEl ? dataPageEl.getAttribute('data-page') : null;
    if (dataPage) {
      try {
        var json = JSON.parse(dataPage);
        if (json && json.props && json.props.chapter && json.props.chapter.content) {
          return { content: _bnSanitize(json.props.chapter.content), format: 'html' };
        }
      } catch(e) {}
    }
    return { content: '<p>Chapter content not found.</p>', format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_BN + '/series?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var dataPageEl = doc.querySelector('div#app');
    var dataPage = dataPageEl ? dataPageEl.getAttribute('data-page') : null;
    if (!dataPage) return [];
    var json = null;
    try { json = JSON.parse(dataPage); } catch(e) {}
    if (!json || !json.props || !json.props.seriesList || !json.props.seriesList.data) return [];
    return json.props.seriesList.data.map(function(s) {
      return { id: s.slug, title: s.title, cover_url: s.cover ? s.cover.url : null, provider: 'brightnovel', url: _BN + '/series/' + s.slug, status: null };
    });
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_BN + '/series?page=' + (page || 1) + '&order=desc'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var dataPageEl = doc.querySelector('div#app');
    var dataPage = dataPageEl ? dataPageEl.getAttribute('data-page') : null;
    if (!dataPage) return [];
    var json = null;
    try { json = JSON.parse(dataPage); } catch(e) {}
    if (!json || !json.props || !json.props.seriesList || !json.props.seriesList.data) return [];
    return json.props.seriesList.data.map(function(s) {
      return { id: s.slug, title: s.title, cover_url: s.cover ? s.cover.url : null, provider: 'brightnovel', url: _BN + '/series/' + s.slug, status: null };
    });
  },
};
