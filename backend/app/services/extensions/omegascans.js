var _OA = 'https://api.omegascans.org';
var _OS = 'https://omegascans.org';

function _osResult(item) {
  var slug = item.series_slug || item.slug || '';
  return {
    id: slug,
    title: item.title || item.name || 'Unknown',
    cover_url: item.thumbnail || null,
    provider: 'omegascans',
    url: _OS + '/series/' + slug,
    status: item.status || null,
  };
}

async function _oaFetch(path) {
  return apiFetch('/manga/proxy/json?url=' + encodeURIComponent(_OA + path));
}

var extension = {
  async search(query, page) {
    var data = await _oaFetch('/query?adult=true&query_string=' +
      encodeURIComponent(query) + '&page=' + (page || 1) + '&perPage=20');
    return (data.data || [])
      .filter(function(i) { return i.series_type === 'Comic'; })
      .map(_osResult);
  },

  async getMangaDetail(mangaId) {
    var series = await _oaFetch('/series/' + mangaId);
    var chapData = await _oaFetch('/chapter/query?page=1&perPage=1999&series_id=' + series.id).catch(function() { return { data: [] }; });
    var chapters = (chapData.data || []).map(function(item) {
      var slug = item.chapter_slug || item.slug || '';
      var num = 0;
      try { num = parseFloat(slug.replace('chapter-', '')) || 0; } catch(e) {}
      return {
        id: mangaId + '/' + slug,
        title: item.chapter_name || item.name || slug,
        number: num,
        published_at: item.created_at || null,
      };
    });

    return {
      id: mangaId,
      title: series.title || series.name || 'Unknown',
      cover_url: series.thumbnail || null,
      description: series.description || series.summary || null,
      status: series.status || null,
      genres: (series.genres || []).map(function(g) { return g.name || ''; }),
      authors: (series.authors || []).map(function(a) { return a.name || ''; }),
      provider: 'omegascans',
      url: _OS + '/series/' + mangaId,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var parts = chapterId.split('/');
    var seriesSlug = parts[0];
    var chapterSlug = parts.slice(1).join('/');
    var data = await _oaFetch('/chapter/' + seriesSlug + '/' + chapterSlug);
    try { return data.chapter.chapter_data.images || []; }
    catch(e) { return []; }
  },

  async getPopular(page) {
    var data = await _oaFetch('/query?adult=true&page=' + (page || 1) + '&perPage=20&order=desc&orderBy=total_views');
    return (data.data || []).filter(function(i) { return i.series_type === 'Comic'; }).map(_osResult);
  },

  async getLatest(page) {
    var data = await _oaFetch('/query?adult=true&page=' + (page || 1) + '&perPage=20&order=desc&orderBy=created_at');
    return (data.data || []).filter(function(i) { return i.series_type === 'Comic'; }).map(_osResult);
  },
};
