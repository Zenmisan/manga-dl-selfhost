// Based on QuickNovel NovelBinProvider (https://novelarrow.com)
// NovelBin uses novelarrow.com JSON API for discovery and RSC for chapter content
var _NB = 'https://novelarrow.com';
var _IMG_BASE = 'https://images.novelarrow.com/novel';

function _nbSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

function _nbFormatCards(items) {
  if (!Array.isArray(items)) return [];
  return items.map(function(item) {
    var id = item.novel_id || item.slug || '';
    var title = item.novel_name || item.title || id;
    var cover = item.novel_cover || (_IMG_BASE + '/' + id + '.jpg');
    var status = item.novel_status === 1 ? 'Completed' : 'Ongoing';
    return {
      id: id,
      title: title,
      cover_url: cover,
      provider: 'novelbin',
      url: _NB + '/novel/' + id,
      status: status,
    };
  });
}

var extension = {
  async search(query, page) {
    var url = _NB + '/api-web/novels?limit=20&page=' + (page || 1) + '&status=all&sort=SEARCH_KEYWORD&genre=ALL&keyword=' + encodeURIComponent(query.trim());
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var json = null;
    try { json = JSON.parse(data.html || data.text || '{}'); } catch(e) {}
    return _nbFormatCards(json ? json.items : []);
  },

  async getMangaDetail(novelId) {
    var slug = novelId.replace(/^\//, '').replace(/\/$/, '');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_NB + '/novel/' + slug));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('h1.font-extrabold, h1.title, h1');
    var title = titleEl ? titleEl.textContent.trim() : slug;

    var coverMeta = doc.querySelector('meta[property="og:image"]');
    var cover = coverMeta ? coverMeta.getAttribute('content') : (_IMG_BASE + '/' + slug + '.jpg');

    var descMeta = doc.querySelector('meta[name="description"]');
    var desc = descMeta ? descMeta.getAttribute('content') : null;

    var authorMeta = doc.querySelector('meta[name="author"]');
    var authors = authorMeta && authorMeta.getAttribute('content') ? [authorMeta.getAttribute('content')] : [];

    var statusMeta = doc.querySelector('meta[name="og:novel:status"]');
    var status = statusMeta ? statusMeta.getAttribute('content') : 'Ongoing';

    var genres = [];
    doc.querySelectorAll('meta[name="category"], a[href*="/genre/"]').forEach(function(el) {
      var g = el.getAttribute('content') || el.textContent.trim();
      if (g && genres.indexOf(g) === -1) genres.push(g);
    });

    var chapters = [];
    try {
      var chUrl = _NB + '/api-web/novels/' + slug + '/chapters?sort=asc';
      var chData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(chUrl));
      var chJson = null;
      try { chJson = JSON.parse(chData.html || chData.text || '{}'); } catch(e) {}
      var items = chJson && chJson.items ? chJson.items : [];
      items.forEach(function(ch, idx) {
        if (ch.premium_content || ch.platinum_content) return;
        var chSlug = ch.chapter_id || ch.chapterId;
        if (!chSlug) return;
        var chTitle = ch.chapter_name || ch.chapterName || ('Chapter ' + (idx + 1));
        var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
        var num = numMatch ? parseFloat(numMatch[1]) : (idx + 1);
        chapters.push({
          id: slug + '/' + chSlug,
          title: chTitle,
          number: num,
          published_at: ch.crawler_date ? ch.crawler_date.split('T')[0] : null,
        });
      });
    } catch(e) {
      console.warn('[NovelBin] Failed to fetch chapters:', e);
    }

    return {
      id: slug,
      title: title,
      cover_url: cover,
      description: desc,
      status: status,
      genres: genres,
      authors: authors,
      provider: 'novelbin',
      url: _NB + '/novel/' + slug,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    return [];
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var novelSlug = parts[0];
    var chSlug = parts.slice(1).join('/');

    // 1. QuickNovel approach: direct JSON API for chapter content
    try {
      var apiUrl = _NB + '/api-web/novels/' + novelSlug + '/chapters/' + chSlug;
      var apiData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(apiUrl));
      var json = null;
      try { json = JSON.parse(apiData.html || apiData.text || '{}'); } catch(e) {}
      var apiContent = json && json.item && json.item.chapterInfo && json.item.chapterInfo.chapter_content;
      if (apiContent && apiContent.length > 50) {
        return { content: _nbSanitize(apiContent), format: 'html' };
      }
    } catch(e) {}

    // 2. Fallback to scraping chapter HTML page
    var url = _NB + '/chapter/' + parts.join('/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var rawHtml = data.html || '';

    var content = '';
    var regex = /self\.__next_f\.push\(\[1,"(.*?)"\]\)/g;
    var match;
    while ((match = regex.exec(rawHtml)) !== null) {
      var raw = match[1];
      if (raw.indexOf('u003cp') !== -1 || raw.indexOf('<p') !== -1) {
        try {
          var unescaped = JSON.parse('"' + raw + '"');
          if (unescaped.indexOf('<p') !== -1) {
            content += unescaped;
          }
        } catch(e) {}
      }
    }

    if (!content) {
      var doc = new DOMParser().parseFromString(rawHtml, 'text/html');
      var el = doc.querySelector('#chr-content, .chr-content, #chapter-content, article');
      if (el) content = el.innerHTML;
    }

    if (!content) content = '<p>Chapter content could not be loaded.</p>';
    return { content: _nbSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var url = _NB + '/api-web/novels?limit=20&page=' + (page || 1) + '&status=all&sort=POPULAR&genre=ALL';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var json = null;
    try { json = JSON.parse(data.html || data.text || '{}'); } catch(e) {}
    return _nbFormatCards(json ? json.items : []);
  },

  async getLatest(page) {
    var url = _NB + '/api-web/novels?limit=20&page=' + (page || 1) + '&status=all&sort=NEW&genre=ALL';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var json = null;
    try { json = JSON.parse(data.html || data.text || '{}'); } catch(e) {}
    return _nbFormatCards(json ? json.items : []);
  },
};
