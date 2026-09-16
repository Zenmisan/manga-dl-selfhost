var _MK = 'https://mangakatana.com';

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

async function _fetchHtml(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return data.html;
}

function _mkParseItems(doc) {
  var results = [];
  var seen = {};
  doc.querySelectorAll('#book_list .item, .manga_list-sbs .item, .item').forEach(function(item) {
    var a = item.querySelector('h3.title a, .text h3 a, .title a, .text .title a, .info .title a, h3 a');
    var href = '';
    var rawTitle = '';
    if (a) {
      href = a.getAttribute('href') || '';
      rawTitle = a.textContent.trim();
    }
    if (!href) {
      var anyA = item.querySelector('a[href*="/manga/"]');
      if (anyA) {
        href = anyA.getAttribute('href') || '';
        if (!rawTitle) rawTitle = anyA.textContent.trim();
      }
    }
    if (!href || !href.includes('/manga/')) return;
    var slug = href.replace(/\/$/, '').split('/').pop();
    if (!slug || seen[slug]) return;
    seen[slug] = true;
    var img = item.querySelector('.media .wrap_img img, img');
    var title = rawTitle || slug.replace(/\.\d+$/, '').replace(/-/g, ' ');
    if (title) {
      title = title.split(' ').map(function(w) { return w.charAt(0).toUpperCase() + w.slice(1); }).join(' ');
    }
    results.push({
      id: slug,
      title: title,
      cover_url: img ? (img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-lazy-src')) : null,
      provider: 'mangakatana',
      url: href.startsWith('http') ? href : (_MK + href),
      status: null,
    });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var pageStr = (page || 1) > 1 ? ('/page/' + page) : '';
    var doc = await _fetchDoc(_MK + pageStr + '?search=' + encodeURIComponent(query) + '&search_by=m_name');
    return _mkParseItems(doc);
  },

  async getMangaDetail(mangaId) {
    var doc = await _fetchDoc(_MK + '/manga/' + mangaId);
    var titleEl = doc.querySelector('h1.heading, .info .heading, .heading, h1, .info h1');
    var rawTitle = titleEl ? titleEl.textContent.trim() : '';
    var title = rawTitle || mangaId.replace(/\.\d+$/, '').replace(/-/g, ' ');
    if (title) {
      title = title.split(' ').map(function(w) { return w.charAt(0).toUpperCase() + w.slice(1); }).join(' ');
    }
    var coverEl = doc.querySelector('.cover img, .media .wrap_img img');
    var cover = coverEl ? (coverEl.getAttribute('src') || coverEl.getAttribute('data-src') || coverEl.getAttribute('data-lazy-src')) : null;
    var desc = null;
    var descEl = doc.querySelector('.summary p, .summary, .description');
    if (descEl) desc = descEl.textContent.trim();
    var genres = [];
    doc.querySelectorAll('.genres a, .genre a').forEach(function(a) { genres.push(a.textContent.trim()); });
    var authors = [];
    doc.querySelectorAll('.author a, .authors a').forEach(function(a) { authors.push(a.textContent.trim()); });

    var chapters = [];
    doc.querySelectorAll('.chapters tr, .chapter_list tr').forEach(function(row) {
      var a = row.querySelector('a');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var slug = href.replace(/\/$/, '').split('/').pop();
      var numMatch = slug.match(/([\d.]+)/);
      var num = numMatch ? parseFloat(numMatch[1]) : 0;
      var dateEl = row.querySelector('.update_time, time, td:last-child');
      chapters.push({
        id: mangaId + '/' + slug,
        title: a.textContent.trim() || ('Chapter ' + num),
        number: num,
        published_at: dateEl ? dateEl.textContent.trim() : null,
      });
    });

    return {
      id: mangaId, title: title,
      cover_url: cover, description: desc,
      status: null, genres: genres, authors: authors,
      provider: 'mangakatana',
      url: _MK + '/manga/' + mangaId,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var html = await _fetchHtml(_MK + '/manga/' + chapterId);
    var best = [];
    var re = /var\s+\w+\s*=\s*(\['[^']*'(?:,'[^']*')*,?\])\s*;/g;
    var m;
    while ((m = re.exec(html)) !== null) {
      try {
        var str = m[1].replace(/'/g, '"').replace(/,\s*\]/, ']');
        if (!str.endsWith(']')) str += ']';
        var arr = JSON.parse(str);
        if (Array.isArray(arr) && arr.length > best.length && typeof arr[0] === 'string' && arr[0].startsWith('http')) {
          best = arr;
        }
      } catch(e) {}
    }
    if (best.length) return best;

    var doc = new DOMParser().parseFromString(html, 'text/html');
    var pages = [];
    doc.querySelectorAll('.wrap_warpper img[data-src], #img_list img, .rd-content img').forEach(function(img) {
      var src = img.getAttribute('data-src') || img.getAttribute('src');
      if (src) pages.push(src);
    });
    return pages;
  },

  async getPopular(page) {
    var p = page || 1;
    var url = p > 1 ? (_MK + '/manga/page/' + p) : (_MK + '/manga');
    var doc = await _fetchDoc(url);
    return _mkParseItems(doc);
  },

  async getLatest(page) {
    var p = page || 1;
    var url = p > 1 ? (_MK + '/latest/page/' + p) : (_MK + '/latest');
    var doc = await _fetchDoc(url);
    return _mkParseItems(doc);
  },
};
