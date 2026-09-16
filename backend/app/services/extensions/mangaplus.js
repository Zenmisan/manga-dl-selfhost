// MANGA Plus by Shueisha — uses a public REST API (no protobuf needed for browse/search)
var _MPS = 'https://jumpg-webapi.tokyo-cdn.com/api';
var _MPWEB = 'https://mangaplus.shueisha.co.jp';

async function _api(path) {
  return apiFetch('/manga/proxy/json?url=' + encodeURIComponent(_MPS + path + (path.includes('?') ? '&' : '?') + 'format=json'));
}

function _thumbUrl(titleId) {
  return 'https://mangaplus.shueisha.co.jp/thumbnail/thumbnail_' + titleId + '.jpg';
}

var extension = {
  async search(query, page) {
    var data = await _api('/title_list/allV2');
    var q = query.toLowerCase();
    var titles = (data?.success?.allTitlesViewV2?.AllTitlesGroup || [])
      .flatMap(function(g) { return g.titles || []; })
      .filter(function(t) { return (t.name || '').toLowerCase().includes(q); })
      .slice(0, 20);
    return titles.map(function(t) {
      return {
        id: String(t.titleId),
        title: t.name,
        cover_url: _thumbUrl(t.titleId),
        provider: 'mangaplus',
        url: _MPWEB + '/titles/' + t.titleId,
        status: null,
      };
    });
  },

  async getMangaDetail(mangaId) {
    var data = await _api('/title_detailV3?title_id=' + mangaId);
    var titleDetail = data?.success?.titleDetailView;
    if (!titleDetail) throw new Error('Manga not found');
    var t = titleDetail.title || {};
    var chapters = [];
    var addChapters = function(list, label) {
      (list || []).forEach(function(ch) {
        chapters.push({
          id: String(ch.chapterId),
          title: ch.subTitle || ch.name || label,
          number: parseFloat(ch.chapterNumberDouble || ch.chapterNumber || 0),
          published_at: ch.startTimeStamp ? new Date(ch.startTimeStamp * 1000).toISOString() : null,
        });
      });
    };
    addChapters(titleDetail.firstChapterList, 'Chapter');
    addChapters(titleDetail.lastChapterList, 'Chapter');
    // Sort by chapter number descending (newest first, matching provider convention)
    chapters.sort(function(a, b) { return b.number - a.number; });
    return {
      id: mangaId,
      title: t.name || mangaId,
      cover_url: _thumbUrl(mangaId),
      description: titleDetail.overview || null,
      status: null,
      genres: titleDetail.label ? [titleDetail.label.label] : [],
      authors: t.author ? [t.author] : [],
      provider: 'mangaplus',
      url: _MPWEB + '/titles/' + mangaId,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var data = await _api('/manga_viewer?chapter_id=' + chapterId + '&split=no&img_quality=super_high');
    var pages = data?.success?.mangaViewer?.pages || [];
    return pages
      .filter(function(p) { return p.mangaPage && p.mangaPage.imageUrl; })
      .map(function(p) { return p.mangaPage.imageUrl; });
  },

  async getPopular(page) {
    var data = await _api('/title_list/ranking');
    var titles = data?.success?.titleRankingView?.titles || [];
    return titles.slice(0, 20).map(function(t) {
      return {
        id: String(t.titleId),
        title: t.name,
        cover_url: _thumbUrl(t.titleId),
        provider: 'mangaplus',
        url: _MPWEB + '/titles/' + t.titleId,
        status: null,
      };
    });
  },

  async getLatest(page) {
    var data = await _api('/web/web_homeV4?lang=eng');
    var groups = data?.success?.webHomeViewV4?.groups || [];
    var results = [];
    var seen = {};
    groups.forEach(function(g) {
      (g.titleGroups || []).forEach(function(tg) {
        (tg.titles || []).forEach(function(t) {
          var id = String(t.titleId);
          if (seen[id]) return;
          seen[id] = true;
          results.push({ id: id, title: t.name, cover_url: _thumbUrl(id), provider: 'mangaplus', url: _MPWEB + '/titles/' + id, status: null });
        });
      });
    });
    return results.slice(0, 20);
  },
};
