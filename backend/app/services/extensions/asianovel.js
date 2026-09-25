// Based on QuickNovel AsianNovelProvider (WordPress/Fictioneer theme)
var _ASN = 'https://www.asianovel.net';

function _asnSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

function _asnParseCards(doc) {
  var results = [];
  doc.querySelectorAll('section.search-results__content > ul > li.card, li.card').forEach(function(card) {
    var a = card.querySelector('a[href*="/story/"]');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var titleEl = card.querySelector('h3, h2, .title');
    var title = titleEl ? titleEl.textContent.trim() : a.textContent.trim();
    var img = card.querySelector('img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;
    var slug = href.replace(_ASN, '').replace(/^\//, '').replace(/\/$/, '');
    if (!slug) return;
    results.push({
      id: slug,
      title: title,
      cover_url: cover,
      provider: 'asianovel',
      url: href,
      status: null,
    });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var url = _ASN + '/?s=' + encodeURIComponent(query.trim()).replace('%20', '+') + '&post_type=any';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _asnParseCards(doc);
  },

  async getMangaDetail(novelId) {
    var url = novelId.startsWith('http') ? novelId : _ASN + '/' + novelId;
    if (!url.endsWith('/')) url += '/';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('h1.story__identity-title, h1');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('img.wp-post-image, .story__identity-thumbnail img');
    var cover = img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null;

    var descEl = doc.querySelector('section.story__summary');
    var desc = descEl ? descEl.textContent.trim() : null;

    var authors = [];
    var authorEl = doc.querySelector('div.story__identity-meta > a.author, a.author');
    if (authorEl) authors = [authorEl.textContent.trim()];

    var genres = [];
    doc.querySelectorAll('div#edit-genre > a, a.genre').forEach(function(g) {
      var name = g.textContent.trim();
      if (name && genres.indexOf(name) === -1) genres.push(name);
    });

    var chapters = [];
    var chList = doc.querySelectorAll('div.chapter-group > ol > li a.chapter-group__list-item-link, a.chapter-group__list-item-link');
    chList.forEach(function(a, idx) {
      var href = a.getAttribute('href') || '';
      var chSlug = href.replace(_ASN, '').replace(/^\//, '').replace(/\/$/, '');
      var chTitle = a.textContent.trim() || ('Chapter ' + (idx + 1));
      var numMatch = chTitle.match(/(?:chapter|\b)\s*([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
      var num = numMatch ? parseFloat(numMatch[1]) : (idx + 1);
      chapters.push({
        id: chSlug,
        title: chTitle,
        number: num,
        published_at: null,
      });
    });

    return {
      id: novelId,
      title: title,
      cover_url: cover,
      description: desc,
      status: 'Ongoing',
      genres: genres,
      authors: authors,
      provider: 'asianovel',
      url: url,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    return [];
  },

  async getChapterText(chapterId) {
    var url = chapterId.startsWith('http') ? chapterId : _ASN + '/' + chapterId;
    if (!url.endsWith('/')) url += '/';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('section#chapter-content > div, section#chapter-content');
    if (contentEl) {
      contentEl.querySelectorAll('script, style, .ads, .chapter-warning').forEach(function(el) { el.remove(); });
    }
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _asnSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var url = _ASN + '/stories/page/' + (page || 1) + '/?order=desc&orderby=modified';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _asnParseCards(doc);
  },

  async getLatest(page) {
    var url = _ASN + '/stories/page/' + (page || 1) + '/?order=desc&orderby=date';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _asnParseCards(doc);
  },
};
