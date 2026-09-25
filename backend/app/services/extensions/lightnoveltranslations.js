// Based on QuickNovel LightNovelTranslationsProvider
var _LNT = 'https://lightnovelstranslations.com';

function _lntSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

function _lntParseCards(doc) {
  var results = [];
  doc.querySelectorAll('div.read_list-story-item').forEach(function(el) {
    var a = el.querySelector('.item_thumb a');
    if (!a) return;
    var img = el.querySelector('.item_thumb img');
    var cover = img ? img.getAttribute('src') : null;
    var title = a.getAttribute('title') || a.textContent.trim();
    var href = a.getAttribute('href') || '';
    var slug = href.replace(_LNT, '').replace(/^\//, '').replace(/\/$/, '');
    if (!slug) return;
    results.push({ id: slug, title: title, cover_url: cover, provider: 'lightnoveltranslations', url: href, status: null });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LNT + '/read'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'field-search=' + encodeURIComponent(query),
    });
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _lntParseCards(doc);
  },

  async getMangaDetail(novelId) {
    var url = novelId.startsWith('http') ? novelId : _LNT + '/' + novelId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');

    var titleEl = doc.querySelector('div.novel_title h3');
    var title = titleEl ? titleEl.textContent.trim() : novelId;

    var img = doc.querySelector('div.novel-image img');
    var cover = img ? img.getAttribute('src') : null;

    var descEl = doc.querySelector('div.novel_synopsis p, div.description p');
    var desc = descEl ? descEl.textContent.trim() : null;

    var authorEl = doc.querySelector('div.novel_detail_info li');
    var authors = [];
    if (authorEl && /Author/i.test(authorEl.textContent)) {
      var a = authorEl.querySelector('a, span');
      if (a) authors = [a.textContent.trim()];
    }

    var status = null;
    var statusEl = doc.querySelector('div.novel_status');
    if (statusEl) status = statusEl.textContent.trim();

    var chapters = [];
    doc.querySelectorAll('li.chapter-item.unlock').forEach(function(li) {
      var a = li.querySelector('a');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var chSlug = href.replace(_LNT, '').replace(/^\//, '').replace(/\/$/, '');
      var chTitle = a.textContent.trim();
      if (!chSlug) return;
      var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
      var num = numMatch ? parseFloat(numMatch[1]) : (chapters.length + 1);
      chapters.push({ id: chSlug, title: chTitle, number: num, published_at: null });
    });

    return { id: novelId, title: title, cover_url: cover, description: desc, status: status, genres: [], authors: authors, provider: 'lightnoveltranslations', url: url, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var url = chapterId.startsWith('http') ? chapterId : _LNT + '/' + chapterId;
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var contentEl = doc.querySelector('div.text_story');
    if (contentEl) {
      contentEl.querySelectorAll('div.ads_content, script, style').forEach(function(el) { el.remove(); });
    }
    var content = contentEl ? contentEl.innerHTML : '<p>Chapter content not found.</p>';
    return { content: _lntSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var url = _LNT + '/read/page/' + (page || 1) + '?sortby=most-liked';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _lntParseCards(doc);
  },

  async getLatest(page) {
    var url = _LNT + '/read/page/' + (page || 1) + '?sortby=most-recent';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _lntParseCards(doc);
  },
};
