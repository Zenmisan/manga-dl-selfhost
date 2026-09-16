var _BASE = 'https://flamecomics.xyz';
var _CDN = 'https://cdn.flamecomics.xyz';

function _fcResult(item) {
  var sid = String(item.id || item.series_id || '');
  var title = item.label || item.title || 'Unknown';
  var img = item.image || item.cover || 'thumbnail.webp';
  return {
    id: sid,
    title: title,
    cover_url: _CDN + '/uploads/images/series/' + sid + '/' + img,
    provider: 'flamescans',
    url: _BASE + '/series/' + sid,
    status: item.status || null,
  };
}

function _parseNextData(html) {
  var m = html.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/);
  if (!m) return null;
  try { return JSON.parse(m[1]); } catch (e) { return null; }
}

async function _fetchJson(path) {
  return apiFetch('/manga/proxy/json?url=' + encodeURIComponent(_BASE + path));
}

async function _fetchHtml(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return data.html || '';
}

var extension = {
  async search(query, page) {
    var all = await _fetchJson('/api/series');
    var q = query.toLowerCase();
    var filtered = (Array.isArray(all) ? all : [])
      .filter(function(s) {
        return (s.label || '').toLowerCase().indexOf(q) !== -1;
      })
      .slice(0, 20);
    return filtered.map(_fcResult);
  },

  async getMangaDetail(mangaId) {
    var html = await _fetchHtml(_BASE + '/series/' + mangaId);
    var nd = _parseNextData(html);
    var pp = nd && nd.props && nd.props.pageProps ? nd.props.pageProps : {};
    var series = pp.series || {};
    var chapList = pp.chapters || [];

    var sid = String(series.series_id || mangaId);
    var cover = series.cover || 'thumbnail.webp';

    var chapters = chapList.map(function(ch) {
      var num = parseFloat(ch.chapter) || 0;
      return {
        id: sid + '/' + ch.token,
        title: 'Chapter ' + num + (ch.title ? ' — ' + ch.title : ''),
        number: num,
        published_at: ch.release_date ? new Date(ch.release_date * 1000).toISOString() : null,
      };
    });

    return {
      id: sid,
      title: series.title || 'Unknown',
      cover_url: _CDN + '/uploads/images/series/' + sid + '/' + cover,
      description: series.description
        ? series.description.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
        : null,
      status: (series.status || '').toLowerCase() || null,
      genres: Array.isArray(series.tags) ? series.tags : [],
      authors: Array.isArray(series.author) ? series.author : [],
      provider: 'flamescans',
      url: _BASE + '/series/' + sid,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var parts = chapterId.split('/');
    var sid = parts[0];
    var token = parts[1];
    if (!sid || !token) return [];

    var html = await _fetchHtml(_BASE + '/series/' + sid + '/' + token);
    var nd = _parseNextData(html);
    var pp = nd && nd.props && nd.props.pageProps ? nd.props.pageProps : {};
    var images = pp.chapter && pp.chapter.images ? pp.chapter.images : {};

    var pages = [];
    var i = 0;
    while (images[String(i)] !== undefined) {
      pages.push(_CDN + '/uploads/images/series/' + sid + '/' + token + '/' + images[String(i)].name);
      i++;
    }
    return pages;
  },

  async getPopular(page) {
    var all = await _fetchJson('/api/series?order=trending&page=' + (page || 1));
    return (Array.isArray(all) ? all : []).slice(0, 20).map(_fcResult);
  },

  async getLatest(page) {
    var all = await _fetchJson('/api/series?order=latest&page=' + (page || 1));
    return (Array.isArray(all) ? all : []).slice(0, 20).map(_fcResult);
  },
};
