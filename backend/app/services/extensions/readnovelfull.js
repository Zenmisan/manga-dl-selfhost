// Based on QuickNovel ReadNovelFullProvider
var _RNF = 'https://readnovelfull.com';

function _rnfSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

var extension = {
  async search(query, page) {
    var url = _RNF + '/novel-list/search?keyword=' + encodeURIComponent(query);
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var results = [];
    doc.querySelectorAll('div.col-novel-main > div.list-novel > div.row').forEach(function(h) {
      var divs = h.querySelectorAll('> div > div');
      var poster = null;
      var img = divs[0] ? divs[0].querySelector('img') : null;
      if (img) {
        var src = img.getAttribute('src') || '';
        poster = src.replace('t-200x89', 't-300x439');
      }
      var titleHeader = divs[1] ? divs[1].querySelector('h3.novel-title > a') : null;
      if (!titleHeader) return;
      var href = titleHeader.getAttribute('href');
      var title = titleHeader.textContent.trim();
      var slug = (href || '').replace(/^\//, '').replace(/\.html$/, '');
      if (!slug) return;
      results.push({ id: slug, title: title, cover_url: poster, provider: 'readnovelfull', url: _RNF + '/' + slug + '.html', status: null });
    });
    return results;
  },

  async getMangaDetail(novelId) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_RNF + '/' + novelId + '.html'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('div.books > div.desc > h3.title, h3.title');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('div.books img');
    var cover = img ? img.getAttribute('src') : null;

    var descEl = doc.querySelector('div.desc-text, div.description-text');
    var desc = descEl ? descEl.textContent.trim() : null;

    var ratingEl = doc.querySelector('div#rating');
    var novelIdNum = ratingEl ? ratingEl.getAttribute('data-novel-id') : null;

    var genres = [];
    var authors = [];
    var status = null;
    doc.querySelectorAll('ul.info-meta > li').forEach(function(li) {
      var h3 = li.querySelector('h3');
      if (!h3) return;
      var label = h3.textContent.trim();
      if (/Genre/i.test(label)) {
        li.querySelectorAll('a').forEach(function(a) { var g = a.textContent.trim(); if (g) genres.push(g); });
      } else if (/Author/i.test(label)) {
        var a = li.querySelector('a');
        if (a) authors = [a.textContent.trim()];
      } else if (/Status/i.test(label)) {
        var a = li.querySelector('a');
        if (a) status = a.textContent.trim();
      }
    });

    var chapters = [];
    if (novelIdNum) {
      try {
        var chData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_RNF + '/ajax/chapter-archive?novelId=' + novelIdNum));
        var chDoc = new DOMParser().parseFromString(chData.html, 'text/html');
        chDoc.querySelectorAll('ul.list-chapter li a, ul.list > li > a').forEach(function(a) {
          var href = a.getAttribute('href') || '';
          var slug2 = href.replace(/^\//, '').replace(/\.html$/, '');
          if (!slug2) return;
          var parts = slug2.split('/');
          if (parts.length < 2) return;
          var chSlug = parts.slice(1).join('/');
          var chId = novelId + '/' + chSlug;
          var chTitle = a.textContent.trim() || ('Chapter ' + (chapters.length + 1));
          var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
          var num = numMatch ? parseFloat(numMatch[1]) : (chapters.length + 1);
          chapters.push({ id: chId, title: chTitle, number: num, published_at: null });
        });
      } catch(e) {}
    }

    return { id: novelId, title: title, cover_url: cover, description: desc, status: status, genres: genres, authors: authors, provider: 'readnovelfull', url: _RNF + '/' + novelId + '.html', chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var slug = parts[0];
    var chSlug = parts.slice(1).join('/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_RNF + '/' + slug + '/' + chSlug + '.html'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('div#chr-content');
    if (contentEl) {
      contentEl.querySelectorAll('script, style, .ads').forEach(function(el) { el.remove(); });
    }
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _rnfSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_RNF + '/most-popular-novel?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var results = [];
    doc.querySelectorAll('div.list-novel > div.row').forEach(function(h) {
      var divs = h.querySelectorAll('> div > div');
      var img = divs[0] ? divs[0].querySelector('img') : null;
      var cover = img ? img.getAttribute('src') : null;
      var titleHeader = divs[1] ? divs[1].querySelector('h3.novel-title > a') : null;
      if (!titleHeader) return;
      var href = titleHeader.getAttribute('href');
      var title = titleHeader.textContent.trim();
      var slug = (href || '').replace(/^\//, '').replace(/\.html$/, '');
      if (!slug) return;
      results.push({ id: slug, title: title, cover_url: cover, provider: 'readnovelfull', url: _RNF + '/' + slug + '.html', status: null });
    });
    return results;
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_RNF + '/latest-release-novel?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var results = [];
    doc.querySelectorAll('div.list-novel > div.row').forEach(function(h) {
      var divs = h.querySelectorAll('> div > div');
      var img = divs[0] ? divs[0].querySelector('img') : null;
      var cover = img ? img.getAttribute('src') : null;
      var titleHeader = divs[1] ? divs[1].querySelector('h3.novel-title > a') : null;
      if (!titleHeader) return;
      var href = titleHeader.getAttribute('href');
      var title = titleHeader.textContent.trim();
      var slug = (href || '').replace(/^\//, '').replace(/\.html$/, '');
      if (!slug) return;
      results.push({ id: slug, title: title, cover_url: cover, provider: 'readnovelfull', url: _RNF + '/' + slug + '.html', status: null });
    });
    return results;
  },
};
