// Based on QuickNovel LibReadProvider (extends FreewebnovelProvider)
// Key diff: POST search, getAcode strips last hyphenated segment
var _LR = 'https://libread.com';

function _lrSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '')
    .replace(/libread\.com/gi, '')
    .replace(/freewebnovel\.com/gi, '');
}

function _lrGetAcode(slug) {
  // Strips last hyphen-segment from slug (e.g. "novel-title-12345" → "novel-title")
  return slug.substring(0, slug.lastIndexOf('-')) || slug;
}

function _lrParseCards(doc) {
  var results = [];
  doc.querySelectorAll('div.ul-list1 > div.li-row, div.li-row').forEach(function(h) {
    var a = h.querySelector('h3.tit > a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var slug = href.replace(/^\//, '').replace(/\.html$/, '');
    if (!slug || slug.length < 2) return;
    var title = a.getAttribute('title') || a.textContent.trim();
    var img = h.querySelector('picture source, div.pic img');
    var cover = null;
    if (img) {
      var srcset = img.getAttribute('srcset') || '';
      if (srcset) { var parts = srcset.split(','); cover = parts[parts.length - 1].trim().split(' ')[0]; }
      if (!cover) cover = img.getAttribute('src');
    }
    if (!cover) { var picImg = h.querySelector('div.pic img'); if (picImg) cover = picImg.getAttribute('src'); }
    results.push({ id: slug, title: title, cover_url: cover, provider: 'libread', url: _LR + '/' + slug, status: null });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LR + '/search'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Referer': _LR },
      body: 'searchkey=' + encodeURIComponent(query.trim()),
    });
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _lrParseCards(doc);
  },

  async getMangaDetail(novelId) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LR + '/' + novelId));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('h1.tit');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('picture source');
    var cover = null;
    if (img) {
      var srcset = img.getAttribute('srcset') || '';
      if (srcset) cover = srcset.split(',').pop().trim().split(' ')[0];
    }
    if (!cover) { var picImg = doc.querySelector('div.pic img'); if (picImg) cover = picImg.getAttribute('src'); }

    var descEl = doc.querySelector('div.inner');
    var desc = descEl ? descEl.textContent.trim() : null;

    var addEl = doc.querySelector('a.set-case.add');
    var articleId = addEl ? addEl.getAttribute('data-articleid') : null;
    if (!articleId) {
      var imgUrl = cover || '';
      var m = imgUrl.match(/\/(\d+)s\.(?:jpg|png|webp)/i);
      if (m) articleId = m[1];
    }

    var acode = _lrGetAcode(novelId);
    var chapters = [];
    if (articleId) {
      try {
        var chData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LR + '/api/chapterlist.php'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'aid=' + encodeURIComponent(articleId) + '&acode=' + encodeURIComponent(acode) + '&cid=1',
        });
        var chDoc = new DOMParser().parseFromString(chData.html || '', 'text/html');
        chDoc.querySelectorAll('option').forEach(function(opt, i) {
          var val = opt.getAttribute('value') || '';
          if (!val) return;
          var chSlug = val.split('/' + novelId + '/').pop();
          if (!chSlug || chSlug === val) chSlug = val.replace(/^\//, '').split('/').pop();
          var chId = novelId + '/' + chSlug;
          var chTitle = opt.textContent.trim() || ('Chapter ' + (i + 1));
          var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
          var num = numMatch ? parseFloat(numMatch[1]) : (i + 1);
          chapters.push({ id: chId, title: chTitle, number: num, published_at: null });
        });
      } catch(e) {}
    }

    return { id: novelId, title: title, cover_url: cover, description: desc, status: null, genres: [], authors: [], provider: 'libread', url: _LR + '/' + novelId, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var slug = parts[0];
    var chSlug = parts.slice(1).join('/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LR + '/novel/' + slug + '/' + chSlug));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('div.txt, div.text-left');
    if (contentEl) {
      contentEl.querySelectorAll('.notice-text, .slot-frame, script, style').forEach(function(el) { el.remove(); });
    }
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _lrSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LR + '/sort/most-popular/' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _lrParseCards(doc);
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LR + '/sort/latest-release/' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _lrParseCards(doc);
  },
};
