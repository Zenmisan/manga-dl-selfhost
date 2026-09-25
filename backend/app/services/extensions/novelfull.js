// Based on QuickNovel AllNovelProvider + NovelFullProvider
// NovelFull uses mobile UA; chapter list comes from AJAX endpoint using data-novel-id
var _NF = 'https://novelfull.com';

function _nfSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

// Image URL fix: QuickNovel replaces certain hash segments to get full-size covers
function _nfFixCover(url) {
  if (!url) return url;
  return url
    .replace('fc05345726d3e134d2f7187dc70f047b', '4d27e0af8cf6e971f7ee3c995fc55190')
    .replace('9798407846f8032e6a88fa71b2c62ce9', '9c3d392ccc7c95187a8c6e37c6bdac6f');
}

function _nfParseCards(doc, provider) {
  var results = [];
  // Both AllNovel and NovelFull share this structure
  doc.querySelectorAll('#list-page > .archive > .list > .row, div.list > div.row').forEach(function(h) {
    var a = h.querySelector('div > div > h3.truyen-title > a, div > div > h3.novel-title > a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    // href is like /slug.html or /slug
    var slug = href.replace(/^\//, '').replace(/\.html$/, '');
    if (!slug || slug.length < 2) return;
    var title = a.textContent.trim();
    var img = h.querySelector('img');
    var cover = img ? _nfFixCover(img.getAttribute('src') || img.getAttribute('data-src')) : null;
    if (cover && cover.startsWith('/')) cover = _NF + cover;
    results.push({ id: slug, title: title, cover_url: cover, provider: provider || 'novelfull', url: _NF + '/' + slug + '.html', status: null });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var url = _NF + '/search?keyword=' + encodeURIComponent(query);
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _nfParseCards(doc, 'novelfull');
  },

  async getMangaDetail(novelId) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_NF + '/' + novelId + '.html'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('h3.title, h1.title');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('div.book img, .books img');
    var cover = _nfFixCover(img ? (img.getAttribute('src') || img.getAttribute('data-src')) : null);
    if (cover && cover.startsWith('/')) cover = _NF + cover;

    var descEl = doc.querySelector('div.desc-text, .description-text');
    var desc = descEl ? descEl.textContent.trim() : null;

    var genres = [];
    var authors = [];
    var status = null;
    doc.querySelectorAll('div.info > div, ul.info > li').forEach(function(div) {
      var text = div.textContent || '';
      if (/genre/i.test(text)) {
        div.querySelectorAll('a').forEach(function(a) { var g = a.textContent.trim(); if (g) genres.push(g); });
      } else if (/author/i.test(text)) {
        var a = div.querySelector('a');
        if (a) authors = [a.textContent.trim()];
      } else if (/status/i.test(text)) {
        var a = div.querySelector('a');
        if (a) status = a.textContent.trim();
      }
    });

    // Chapter list via AJAX — data-novel-id from #rating element
    var ratingEl = doc.querySelector('#rating');
    var novelIdNum = ratingEl ? ratingEl.getAttribute('data-novel-id') : null;
    var chapters = [];

    if (novelIdNum) {
      var fetchChapterPage = async function(ajaxUrl) {
        var chData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(ajaxUrl));
        var chDoc = new DOMParser().parseFromString(chData.html, 'text/html');
        chDoc.querySelectorAll('select > option, li[data-chapter-item] > a').forEach(function(el) {
          var val = el.getAttribute('value') || el.getAttribute('href') || '';
          if (!val) return;
          // val like /novel-slug/chapter-1-title.html
          var parts = val.replace(/^\//, '').replace(/\.html$/, '').split('/');
          if (parts.length < 2) return;
          var chSlug = parts.slice(1).join('/');
          var chId = novelId + '/' + chSlug;
          var chTitle = el.textContent.trim() || ('Chapter ' + (chapters.length + 1));
          var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
          var num = numMatch ? parseFloat(numMatch[1]) : (chapters.length + 1);
          chapters.push({ id: chId, title: chTitle, number: num, published_at: null });
        });
      };
      try {
        await fetchChapterPage(_NF + '/ajax-chapter-option?novelId=' + novelIdNum);
      } catch(e) {}
    }

    return { id: novelId, title: title, cover_url: cover, description: desc, status: status, genres: genres, authors: authors, provider: 'novelfull', url: _NF + '/' + novelId + '.html', chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var slug = parts[0];
    var chSlug = parts.slice(1).join('/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_NF + '/' + slug + '/' + chSlug + '.html'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('#chapter-content, #chr-content');
    if (contentEl) {
      contentEl.querySelectorAll('script, style, .ads').forEach(function(el) { el.remove(); });
      // Remove ad iframes
      contentEl.innerHTML = contentEl.innerHTML
        .replace(/<iframe[^>]*src="\/\/ad[^"]*"[^>]*><\/iframe>/gi, '')
        .replace('If you find any errors ( broken links, non-standard content, etc.. ), Please let us know &lt; report chapter &gt; so we can fix it as soon as possible.', '')
        .replace('If you find any errors ( Ads popup, ads redirect, broken links, non-standard content, etc.. ), Please let us know &lt; report chapter &gt; so we can fix it as soon as possible.', '');
    }
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _nfSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_NF + '/most-popular?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _nfParseCards(doc, 'novelfull');
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_NF + '/latest-release-novel?page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _nfParseCards(doc, 'novelfull');
  },
};
