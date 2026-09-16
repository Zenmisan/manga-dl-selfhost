var _MD = 'https://api.mangadex.org';
var _CDN = 'https://uploads.mangadex.org';

async function _mdFetch(path) {
  return apiFetch('/manga/proxy/json?url=' + encodeURIComponent(_MD + path));
}

function _cover(data) {
  var rels = data.relationships || [];
  for (var i = 0; i < rels.length; i++) {
    var r = rels[i];
    if (r.type === 'cover_art' && r.attributes && r.attributes.fileName) {
      return _CDN + '/covers/' + data.id + '/' + r.attributes.fileName;
    }
  }
  return null;
}

function _title(attr) {
  var t = attr.title || {};
  return t.en || Object.values(t)[0] || 'Unknown';
}

function _toResult(item) {
  var attr = item.attributes || {};
  return {
    id: item.id,
    title: _title(attr),
    cover_url: _cover(item),
    provider: 'mangadex',
    url: 'https://mangadex.org/title/' + item.id,
    status: attr.status || null,
  };
}

var extension = {
  async search(query, page) {
    var offset = ((page || 1) - 1) * 20;
    var data = await _mdFetch('/manga?title=' + encodeURIComponent(query) +
      '&limit=20&offset=' + offset +
      '&includes[]=cover_art&availableTranslatedLanguage[]=en' +
      '&contentRating[]=safe&contentRating[]=suggestive' +
      '&contentRating[]=erotica&contentRating[]=pornographic');
    return (data.data || []).map(_toResult);
  },

  async getMangaDetail(mangaId) {
    var det = (await _mdFetch('/manga/' + mangaId +
      '?includes[]=cover_art&includes[]=author&includes[]=artist')).data;
    var attr = det.attributes || {};

    var genres = (attr.tags || [])
      .map(function(t) { return t.attributes && t.attributes.name && t.attributes.name.en; })
      .filter(Boolean);

    var authorMap = {};
    (det.relationships || []).forEach(function(r) {
      if ((r.type === 'author' || r.type === 'artist') && r.attributes && r.attributes.name) {
        authorMap[r.attributes.name] = true;
      }
    });

    var allItems = [];
    var limit = 500;
    var offset = 0;
    while (true) {
      var feedData = await _mdFetch('/manga/' + mangaId +
        '/feed?limit=' + limit + '&offset=' + offset +
        '&translatedLanguage[]=en&order[chapter]=asc' +
        '&contentRating[]=safe&contentRating[]=suggestive' +
        '&contentRating[]=erotica&contentRating[]=pornographic');
      var items = feedData.data || [];
      allItems = allItems.concat(items);
      if (items.length < limit) break;
      offset += limit;
    }

    var chapters = allItems.map(function(item) {
      var a = item.attributes || {};
      var num = parseFloat(a.chapter) || 0;
      var titleText = '';
      if (a.chapter !== null && a.chapter !== undefined && a.chapter !== '') {
        titleText = 'Chapter ' + a.chapter;
        if (a.title) {
          titleText += ': ' + a.title;
        }
      } else if (a.title) {
        titleText = a.title;
      } else {
        titleText = 'Chapter ' + (num || 1);
      }
      return {
        id: item.id,
        title: titleText,
        number: num,
        published_at: a.publishAt || null,
      };
    });

    return {
      id: det.id,
      title: _title(attr),
      cover_url: _cover(det),
      description: (attr.description || {}).en || null,
      status: attr.status || null,
      genres: genres,
      authors: Object.keys(authorMap),
      provider: 'mangadex',
      url: 'https://mangadex.org/title/' + det.id,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    var data = await _mdFetch('/at-home/server/' + chapterId);
    var base = data.baseUrl;
    var hash = data.chapter.hash;
    return (data.chapter.data || []).map(function(f) {
      return base + '/data/' + hash + '/' + f;
    });
  },

  async getPopular(page) {
    var offset = ((page || 1) - 1) * 20;
    var data = await _mdFetch('/manga?limit=20&offset=' + offset +
      '&includes[]=cover_art&availableTranslatedLanguage[]=en' +
      '&contentRating[]=safe&contentRating[]=suggestive' +
      '&order[followedCount]=desc');
    return (data.data || []).map(_toResult);
  },

  async getLatest(page) {
    var offset = ((page || 1) - 1) * 20;
    var data = await _mdFetch('/manga?limit=20&offset=' + offset +
      '&includes[]=cover_art&availableTranslatedLanguage[]=en' +
      '&contentRating[]=safe&contentRating[]=suggestive' +
      '&order[latestUploadedChapter]=desc');
    return (data.data || []).map(_toResult);
  },
};
