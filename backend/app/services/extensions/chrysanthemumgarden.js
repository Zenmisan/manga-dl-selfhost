// Based on QuickNovel ChrysanthemumGardenProvider
var _CG = 'https://chrysanthemumgarden.com';

function _cgSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

var extension = {
  async search(query, page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_CG + '/wp-json/cg/novels'));
    var json = null;
    try { json = JSON.parse(data.html || data.text || ''); } catch(e) {}
    if (!Array.isArray(json)) return [];
    var q = query.toLowerCase();
    return json
      .filter(function(n) { return n.name && n.name.toLowerCase().includes(q); })
      .slice(0, 20)
      .map(function(n) {
        var slug = (n.link || '').replace(_CG, '').replace(/^\//, '').replace(/\/$/, '');
        return { id: slug, title: n.name, cover_url: null, provider: 'chrysanthemumgarden', url: n.link || (_CG + '/' + slug), status: null };
      });
  },

  async getMangaDetail(novelId) {
    var url = novelId.startsWith('http') ? novelId : _CG + '/' + novelId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    doc.querySelectorAll('.novel-raw-title').forEach(function(el) { el.remove(); });
    var titleEl = doc.querySelector('h1.novel-title');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('.novel-cover img');
    var cover = img ? (img.getAttribute('data-breeze') || img.getAttribute('src')) : null;

    var desc = doc.querySelectorAll('.entry-content p');
    var descText = Array.from(desc).map(function(p) { return p.textContent.trim(); }).filter(Boolean).join('\n\n');

    var infoHtml = doc.querySelector('.novel-info') ? doc.querySelector('.novel-info').outerHTML : '';
    var authorMatch = infoHtml.match(/Author:\s*([^<]*)<br/);
    var authors = authorMatch ? [authorMatch[1].trim()] : [];

    var genres = [];
    doc.querySelectorAll('.series-genres a').forEach(function(a) { var g = a.textContent.trim(); if (g) genres.push(g); });

    var chapters = [];
    doc.querySelectorAll('.chapter-item a').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      var chSlug = href.replace(_CG, '').replace(/^\//, '').replace(/\/$/, '');
      var chTitle = a.textContent.trim();
      if (!chSlug) return;
      var chId = chSlug;
      var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
      var num = numMatch ? parseFloat(numMatch[1]) : (chapters.length + 1);
      chapters.push({ id: chId, title: chTitle, number: num, published_at: null });
    });

    return { id: novelId, title: title, cover_url: cover, description: descText || null, status: null, genres: genres, authors: authors, provider: 'chrysanthemumgarden', url: url, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var url = chapterId.startsWith('http') ? chapterId : _CG + '/' + chapterId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('#novel-content');
    if (contentEl) {
      contentEl.querySelectorAll('[style*="display:none"], [style*="display: none"]').forEach(function(el) { el.remove(); });
      contentEl.querySelectorAll('[style*="visibility:hidden"], [style*="visibility: hidden"]').forEach(function(el) { el.remove(); });
      contentEl.querySelectorAll('[style*="font-size:0"], [style*="font-size: 0"]').forEach(function(el) { el.remove(); });
      contentEl.querySelectorAll('[style*="width:0"], [style*="width: 0"]').forEach(function(el) { el.remove(); });
      contentEl.querySelectorAll('.chrys-ads, .announcement, .entry-content_content, script, style, .jum').forEach(function(el) { el.remove(); });
      var cgSpam = contentEl.querySelectorAll('p');
      cgSpam.forEach(function(p) { if (p.textContent.toLowerCase().includes('chrysanthemumgarden')) p.remove(); });
    }
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _cgSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_CG + '/books/page/' + (page || 1) + '/'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var results = [];
    doc.querySelectorAll('article').forEach(function(el) {
      if (el.querySelector('.series-genres a') && el.querySelector('.series-genres a').textContent.toLowerCase().includes('manhua')) return;
      var titleEl = el.querySelector('h2.novel-title > a');
      if (!titleEl) return;
      var name = titleEl.textContent.trim();
      var href = titleEl.getAttribute('href') || '';
      var slug = href.replace(_CG, '').replace(/^\//, '').replace(/\/$/, '');
      var img = el.querySelector('div.novel-cover > img');
      var cover = img ? (img.getAttribute('data-breeze') || img.getAttribute('src')) : null;
      results.push({ id: slug, title: name, cover_url: cover, provider: 'chrysanthemumgarden', url: href, status: null });
    });
    return results;
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_CG + '/books/page/' + (page || 1) + '/'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var results = [];
    doc.querySelectorAll('article').forEach(function(el) {
      var titleEl = el.querySelector('h2.novel-title > a');
      if (!titleEl) return;
      var name = titleEl.textContent.trim();
      var href = titleEl.getAttribute('href') || '';
      var slug = href.replace(_CG, '').replace(/^\//, '').replace(/\/$/, '');
      var img = el.querySelector('div.novel-cover > img');
      var cover = img ? (img.getAttribute('data-breeze') || img.getAttribute('src')) : null;
      results.push({ id: slug, title: name, cover_url: cover, provider: 'chrysanthemumgarden', url: href, status: null });
    });
    return results;
  },
};
