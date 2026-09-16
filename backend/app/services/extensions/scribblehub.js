var _SH = 'https://www.scribblehub.com';

function _shSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

function _shParseCards(doc, provider) {
  var results = [];
  doc.querySelectorAll('.search_main_box, .sb_box, .novel_main').forEach(function(item) {
    var a = item.querySelector('.search_title a, h3 a, .title a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var idMatch = href.match(/scribblehub\.com\/series\/(\d+)/);
    if (!idMatch) return;
    var id = idMatch[1];
    var title = a.textContent.trim();
    var img = item.querySelector('img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;
    results.push({ id: id, title: title, cover_url: cover, provider: provider || 'scribblehub', url: _SH + '/series/' + id + '/', status: null });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_SH + '/?s=' + encodeURIComponent(query) + '&post_type=fictionposts&paged=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _shParseCards(doc, 'scribblehub');
  },

  async getMangaDetail(novelId) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_SH + '/series/' + novelId + '/'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('.fic_title, h1.title');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('.fic_image img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;

    var descEl = doc.querySelector('.wi_fic_desc, .description');
    var desc = descEl ? descEl.textContent.trim() : null;

    var genres = [];
    doc.querySelectorAll('.wi_fic_genre a, .fic_genre a').forEach(function(el) {
      var g = el.textContent.trim();
      if (g) genres.push(g);
    });

    var statusEl = doc.querySelector('.rnd_stats .stat_item:last-child, .fic_stats');
    var status = null;

    var authorEl = doc.querySelector('.auth_name_fic a, .author a');
    var authors = authorEl ? [authorEl.textContent.trim()] : [];

    var chapters = [];
    var chapterData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_SH + '/wp-admin/admin-ajax.php'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'action=wi_getvol&mypostid=' + novelId + '&pageno=1',
    }).catch(function() { return { html: '' }; });

    var chDoc = new DOMParser().parseFromString(chapterData.html || '', 'text/html');
    chDoc.querySelectorAll('.toc_ol li a, .chapter-item a').forEach(function(a, i) {
      var href = a.getAttribute('href') || '';
      var chIdMatch = href.match(/\/read\/(\d+)\/chapter\/(\d+)/);
      if (!chIdMatch) return;
      var chId = chIdMatch[1] + '/chapter/' + chIdMatch[2];
      var chTitle = a.textContent.trim();
      var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chTitle.match(/([\d.]+)/);
      var num = numMatch ? parseFloat(numMatch[1]) : (chapters.length + 1);
      chapters.push({ id: chId, title: chTitle, number: num, published_at: null });
    });

    return { id: novelId, title: title, cover_url: cover, description: desc, status: status, genres: genres, authors: authors, provider: 'scribblehub', url: _SH + '/series/' + novelId + '/', chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/chapter/');
    var seriesId = parts[0];
    var chId = parts[1];
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_SH + '/read/' + seriesId + '/chapter/' + chId + '/'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('#chp_raw, .chapter-content, .wi_fic_story');
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _shSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_SH + '/series-ranking/?sort=toprate&paged=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _shParseCards(doc, 'scribblehub');
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_SH + '/series-ranking/?sort=latest&paged=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _shParseCards(doc, 'scribblehub');
  },
};
