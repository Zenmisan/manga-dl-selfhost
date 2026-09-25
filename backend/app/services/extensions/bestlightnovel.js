// Based on QuickNovel BestLightNovelProvider
var _BLN = 'https://bestlightnovel.com';

function _blnSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '')
    .replace(/\[Updated from F r e e w e b n o v e l\. c o m\]/g, '')
    .replace(/Find authorized novels in Webnovel.*?Please click for visiting\./g, '');
}

var extension = {
  async search(query, page) {
    var q = query.trim().replace(/\s+/g, '_');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_BLN + '/search_novels/' + encodeURIComponent(q)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var results = [];
    doc.querySelectorAll('div.danh_sach > div.list_category').forEach(function(item) {
      var a = item.querySelector('> a');
      if (!a) return;
      var name = a.getAttribute('title') || a.textContent.trim();
      var url = a.getAttribute('href') || '';
      var img = a.querySelector('img');
      var cover = img ? img.getAttribute('src') : null;
      var slug = url.replace(_BLN, '').replace(/^\//, '').replace(/\/$/, '');
      results.push({ id: slug, title: name, cover_url: cover, provider: 'bestlightnovel', url: url, status: null });
    });
    return results;
  },

  async getMangaDetail(novelId) {
    var url = novelId.startsWith('http') ? novelId : _BLN + '/' + novelId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var infoItems = doc.querySelectorAll('ul.truyen_info_right > li');
    var h1 = infoItems[0] ? infoItems[0].querySelector('h1') : null;
    var title = h1 ? h1.textContent.trim() : novelId;

    var coverEl = doc.querySelector('span.info_image > img');
    var cover = coverEl ? coverEl.getAttribute('src') : null;

    var genres = [];
    if (infoItems[2]) {
      infoItems[2].querySelectorAll('a').forEach(function(a) { var g = a.textContent.trim(); if (g) genres.push(g); });
    }

    var authors = [];
    if (infoItems[1]) {
      infoItems[1].querySelectorAll('a').forEach(function(a) {
        var href = a.getAttribute('href') || '';
        if (href.includes('search_author')) authors.push(a.textContent.trim());
      });
    }

    var status = null;
    if (infoItems[3]) {
      var statusA = infoItems[3].querySelector('a');
      if (statusA) status = statusA.textContent.trim();
    }

    var descDivs = doc.querySelectorAll('div.entry-header > div');
    var desc = descDivs[1] ? descDivs[1].textContent.trim() : null;

    var chapters = [];
    doc.querySelectorAll('div.chapter-list > div').forEach(function(div) {
      var spans = div.querySelectorAll('> span');
      if (!spans[0]) return;
      var a = spans[0].querySelector('a');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var chSlug = href.replace(_BLN, '').replace(/^\//, '').replace(/\/$/, '');
      var chTitle = a.textContent.trim();
      var date = spans[1] ? spans[1].textContent.trim() : null;
      var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
      var num = numMatch ? parseFloat(numMatch[1]) : (chapters.length + 1);
      chapters.push({ id: chSlug, title: chTitle, number: num, published_at: date });
    });
    chapters.reverse();

    return { id: novelId, title: title, cover_url: cover, description: desc, status: status, genres: genres, authors: authors, provider: 'bestlightnovel', url: url, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var url = chapterId.startsWith('http') ? chapterId : _BLN + '/' + chapterId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('div.vung_doc');
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _blnSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_BLN + '/index-chapter-hot.html?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var results = [];
    doc.querySelectorAll('div.danh_sach > div.list_category').forEach(function(item) {
      var a = item.querySelector('> a');
      if (!a) return;
      var name = a.getAttribute('title') || a.textContent.trim();
      var url = a.getAttribute('href') || '';
      var img = a.querySelector('img');
      var cover = img ? img.getAttribute('src') : null;
      var slug = url.replace(_BLN, '').replace(/^\//, '').replace(/\/$/, '');
      results.push({ id: slug, title: name, cover_url: cover, provider: 'bestlightnovel', url: url, status: null });
    });
    return results;
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_BLN + '/index-latest-chapter-' + (page || 1) + '.html'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var results = [];
    doc.querySelectorAll('div.danh_sach > div.list_category').forEach(function(item) {
      var a = item.querySelector('> a');
      if (!a) return;
      var name = a.getAttribute('title') || a.textContent.trim();
      var url = a.getAttribute('href') || '';
      var img = a.querySelector('img');
      var cover = img ? img.getAttribute('src') : null;
      var slug = url.replace(_BLN, '').replace(/^\//, '').replace(/\/$/, '');
      results.push({ id: slug, title: name, cover_url: cover, provider: 'bestlightnovel', url: url, status: null });
    });
    return results;
  },
};
