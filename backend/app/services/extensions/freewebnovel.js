// Based on QuickNovel FreewebnovelProvider
var _FWN = 'https://freewebnovel.com';

function _fwnSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '')
    .replace(/New novel chapters are published on Freewebnovel\.com\./g, '')
    .replace(/The source of this content is Freewebn.*?vel\.com\./g, '')
    .replace(/☞.*?☜/g, '');
}

function _fwnParseCards(doc, provider) {
  var results = [];
  doc.querySelectorAll('div.ul-list1 > div.li-row, div.li-row').forEach(function(h) {
    var a = h.querySelector('h3.tit > a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    // href like /slug or /slug.html
    var slug = href.replace(/^\//, '').replace(/\.html$/, '');
    if (!slug || slug.length < 2) return;
    var title = a.getAttribute('title') || a.textContent.trim();
    var img = h.querySelector('picture source, div.pic img');
    var cover = null;
    if (img) {
      var srcset = img.getAttribute('srcset') || '';
      if (srcset) {
        // Take last srcset entry
        var parts = srcset.split(',');
        cover = parts[parts.length - 1].trim().split(' ')[0];
      }
      if (!cover) cover = img.getAttribute('src');
    }
    if (!cover) {
      var picImg = h.querySelector('div.pic img');
      if (picImg) cover = picImg.getAttribute('src');
    }
    results.push({ id: slug, title: title, cover_url: cover, provider: provider || 'freewebnovel', url: _FWN + '/' + slug, status: null });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var url = _FWN + '/search?keyword=' + encodeURIComponent(query.trim());
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _fwnParseCards(doc, 'freewebnovel');
  },

  async getMangaDetail(novelId) {
    var url = _FWN + '/' + novelId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('h1.tit');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('picture source');
    var cover = null;
    if (img) {
      var srcset = img.getAttribute('srcset') || '';
      if (srcset) cover = srcset.split(',').pop().trim().split(' ')[0];
    }
    if (!cover) {
      var picImg = doc.querySelector('div.pic img');
      if (picImg) cover = picImg.getAttribute('src');
    }

    var descEl = doc.querySelector('div.inner');
    var desc = descEl ? descEl.textContent.trim() : null;

    var genres = [];
    var tagsEl = doc.querySelector('span.glyphicon-th-list');
    if (tagsEl) {
      var tagsParent = tagsEl.parentElement;
      if (tagsParent) {
        tagsParent.querySelectorAll('a').forEach(function(a) { var g = a.textContent.trim(); if (g) genres.push(g); });
      }
    }

    var authorEl = doc.querySelector('span.glyphicon-user');
    var authors = [];
    if (authorEl) {
      var authorText = authorEl.nextElementSibling;
      if (authorText) authors = [authorText.textContent.trim()];
    }

    var status = null;
    var statusEl = doc.querySelector('span.s1.s3 > a, span.s1.s2 > a');
    if (statusEl) status = statusEl.textContent.trim();

    // Novel ID for chapter list API
    var addEl = doc.querySelector('a.set-case.add');
    var articleId = addEl ? addEl.getAttribute('data-articleid') : null;
    if (!articleId) {
      // Fallback: extract from image URL pattern like "12345s.jpg"
      var imgUrl = cover || '';
      var m = imgUrl.match(/\/(\d+)s\.(?:jpg|png|webp)/i);
      if (m) articleId = m[1];
    }

    var chapters = [];
    if (articleId) {
      try {
        var chData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_FWN + '/api/chapterlist.php'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'aid=' + encodeURIComponent(articleId) + '&acode=' + encodeURIComponent(novelId) + '&cid=1',
        });
        var chDoc = new DOMParser().parseFromString(chData.html || '', 'text/html');
        chDoc.querySelectorAll('option').forEach(function(opt, i) {
          var val = opt.getAttribute('value') || '';
          if (!val) return;
          // val like /novel/slug/chapter-1 or /slug/chapter-1
          var chSlug = val.split('/novel/' + novelId + '/').pop();
          if (!chSlug || chSlug === val) chSlug = val.split('/' + novelId + '/').pop();
          if (!chSlug || chSlug === val) chSlug = val.replace(/^\//, '').split('/').pop();
          var chId = novelId + '/' + chSlug;
          var chTitle = opt.textContent.trim() || ('Chapter ' + (i + 1));
          var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
          var num = numMatch ? parseFloat(numMatch[1]) : (i + 1);
          chapters.push({ id: chId, title: chTitle, number: num, published_at: null });
        });
      } catch(e) {}
    }

    return { id: novelId, title: title, cover_url: cover, description: desc, status: status, genres: genres, authors: authors, provider: 'freewebnovel', url: _FWN + '/' + novelId, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var slug = parts[0];
    var chSlug = parts.slice(1).join('/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_FWN + '/novel/' + slug + '/' + chSlug));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('div.txt');
    if (contentEl) {
      contentEl.querySelector('.notice-text')?.remove();
      contentEl.querySelectorAll('.slot-frame, div.reader-ad-skip, script, style').forEach(function(el) { el.remove(); });
    }
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _fwnSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_FWN + '/sort/most-popular/' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _fwnParseCards(doc, 'freewebnovel');
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_FWN + '/sort/latest-release/' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _fwnParseCards(doc, 'freewebnovel');
  },
};
