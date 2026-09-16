var _WT = 'https://www.webtoons.com';
var _WTA = 'https://global.apis.naver.com/webtoon/webtoon/v1.0';

async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

async function _fetchJson(url) {
  return apiFetch('/manga/proxy/json?url=' + encodeURIComponent(url));
}

var extension = {
  async search(query, page) {
    var doc = await _fetchDoc(_WT + '/en/search?keyword=' + encodeURIComponent(query));
    var results = [];
    var seen = {};
    doc.querySelectorAll('.card_item, .info_area, li[class*="card"]').forEach(function(el) {
      var a = el.querySelector('a[href*="list?title_no="], a[href*="/en/"]');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var m = href.match(/title_no=(\d+)/);
      if (!m) return;
      var id = m[1];
      if (seen[id]) return;
      seen[id] = true;
      var img = el.querySelector('img');
      var titleEl = el.querySelector('.subj, .title, p.subj, .info_area strong');
      results.push({
        id: id,
        title: titleEl ? titleEl.textContent.trim() : id,
        cover_url: img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null,
        provider: 'webtoons',
        url: href,
        status: null,
      });
    });
    return results;
  },

  async getMangaDetail(mangaId) {
    // mangaId = "genre/title-slug/title_no" or just titleNo
    var titleNo = mangaId.split('/').pop() || mangaId;
    var doc = await _fetchDoc(_WT + '/en/action/titledetail?title_no=' + titleNo);
    var title = (doc.querySelector('.subj, h1.subj, .title') || {}).textContent || mangaId;
    var cover = doc.querySelector('#content img.detail_thumbnail, .detail_info img');
    var desc = doc.querySelector('.summary p, .grade_area p, .detail_summary');
    var genres = [];
    doc.querySelectorAll('.genre, .sub_genre').forEach(function(el) { genres.push(el.textContent.trim()); });
    var chapters = [];
    doc.querySelectorAll('#_listUl li, .detail_lst li').forEach(function(li) {
      var a = li.querySelector('a');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var epM = href.match(/episode_no=(\d+)/);
      if (!epM) return;
      var epNo = epM[1];
      var epTitle = li.querySelector('.subj span, .episode_num') || li.querySelector('a');
      var dateEl = li.querySelector('.date, .col_date');
      chapters.push({
        id: titleNo + '/' + epNo,
        title: epTitle ? epTitle.textContent.trim() : 'Episode ' + epNo,
        number: parseInt(epNo) || 0,
        published_at: dateEl ? dateEl.textContent.trim() : null,
      });
    });
    return {
      id: mangaId,
      title: title.trim(),
      cover_url: cover ? (cover.getAttribute('src') || cover.getAttribute('data-src')) : null,
      description: desc ? desc.textContent.trim() : null,
      status: null, genres: genres, authors: [],
      provider: 'webtoons',
      url: _WT + '/en/action/titledetail?title_no=' + titleNo,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    // chapterId = "titleNo/episodeNo"
    var parts = chapterId.split('/');
    var episodeNo = parts.pop();
    var titleNo = parts.join('/');
    var doc = await _fetchDoc(_WT + '/en/viewer?title_no=' + titleNo + '&episode_no=' + episodeNo);
    var pages = [];
    doc.querySelectorAll('#_imageList img, .viewer_img img, ._images img').forEach(function(img) {
      var src = img.getAttribute('data-url') || img.getAttribute('src') || img.getAttribute('data-src');
      if (src && src.startsWith('http')) pages.push(src);
    });
    return pages;
  },

  async getPopular(page) {
    var doc = await _fetchDoc(_WT + '/en/top?period=WEEK');
    var results = [];
    var seen = {};
    doc.querySelectorAll('.card_item, li[class*="card"]').forEach(function(el) {
      var a = el.querySelector('a[href*="title_no="]');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var m = href.match(/title_no=(\d+)/);
      if (!m) return;
      var id = m[1];
      if (seen[id]) return;
      seen[id] = true;
      var img = el.querySelector('img');
      var titleEl = el.querySelector('.subj, .title');
      results.push({ id: id, title: titleEl ? titleEl.textContent.trim() : id, cover_url: img ? img.getAttribute('src') : null, provider: 'webtoons', url: href, status: null });
    });
    return results;
  },

  async getLatest(page) {
    var doc = await _fetchDoc(_WT + '/en/new');
    var results = [];
    var seen = {};
    doc.querySelectorAll('a[href*="title_no="]').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      var m = href.match(/title_no=(\d+)/);
      if (!m) return;
      var id = m[1];
      if (seen[id]) return;
      seen[id] = true;
      results.push({ id: id, title: a.textContent.trim() || id, cover_url: null, provider: 'webtoons', url: href, status: null });
    });
    return results;
  },
};
