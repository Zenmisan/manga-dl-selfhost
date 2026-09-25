// QuickNovel uses lightnovelworld.org (not .com)
var _LNW = 'https://www.lightnovelworld.com';
var _LNW_ORG = 'https://lightnovelworld.org';

function _lnwSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

function _lnwParseCards(doc, baseUrl, provider) {
  var results = [];
  // .org uses div.recommendations-grid > div.recommendation-card
  doc.querySelectorAll('div.recommendation-card, .novel-item, .book-item, li.novel').forEach(function(item) {
    var a = item.querySelector('a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var slug = href.split('/novel/').pop().replace(/\/$/, '').split('/')[0];
    if (!slug || slug.length < 2) return;
    var title = (item.querySelector('h3, .novel-title, .title') || a).textContent.trim();
    var img = item.querySelector('img');
    var cover = img ? (img.getAttribute('data-src') || img.getAttribute('src')) : null;
    if (cover && cover.startsWith('/')) cover = baseUrl + cover;
    results.push({ id: slug, title: title, cover_url: cover, provider: provider || 'lightnovelworld', url: baseUrl + '/novel/' + slug, status: null });
  });
  return results;
}

async function _lnwFetchDetail(baseUrl, novelId) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(baseUrl + '/novel/' + novelId));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

// Extract chapters from a single page; supports onClick='location.href=...' pattern
function _lnwParseChapterPage(doc, baseUrl, novelId) {
  var chapters = [];
  doc.querySelectorAll('div.chapters-grid > div.chapter-card, #chapter-list li, .chapter-list li').forEach(function(item, i) {
    // .org: chapter-card has onClick="location.href='...'"
    var onClick = item.getAttribute('onclick') || item.getAttribute('onClick') || '';
    var hrefFromClick = onClick.match(/location\.href=['"]([^'"]+)['"]/);
    var href = '';
    if (hrefFromClick) {
      href = hrefFromClick[1];
    } else {
      var a = item.querySelector('a');
      if (a) href = a.getAttribute('href') || '';
    }
    if (!href) return;
    var slug = href.split('/novel/' + novelId + '/').pop().replace(/\/$/, '');
    if (!slug || slug === href) return;
    var chId = novelId + '/' + slug;
    var nameEl = item.querySelector('h3, .chapter-title, span');
    var chTitle = nameEl ? nameEl.textContent.trim() : ('Chapter ' + (i + 1));
    var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || slug.match(/chapter-(\d+)/i) || chTitle.match(/([\d.]+)/);
    var num = numMatch ? parseFloat(numMatch[1]) : (i + 1);
    var dateEl = item.querySelector('.chapter-time, p.chapter-time, time');
    chapters.push({ id: chId, title: chTitle, number: num, published_at: dateEl ? dateEl.textContent.trim() : null });
  });
  return chapters;
}

var extension = {
  async search(query, page) {
    // Try JSON API first (QuickNovel approach: /api/search/?q=)
    var base = _LNW_ORG;
    try {
      var apiData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(base + '/api/search/?q=' + encodeURIComponent(query)));
      // The proxy returns {html: "..."} but for JSON endpoints it might be the raw body
      var parsed = null;
      try { parsed = JSON.parse(apiData.html || apiData.text || ''); } catch(e) {}
      if (parsed && parsed.novels && parsed.novels.length > 0) {
        return parsed.novels.map(function(n) {
          var slug = n.slug || '';
          return { id: slug, title: n.title || slug, cover_url: n.cover_path || null, provider: 'lightnovelworld', url: base + '/novel/' + slug, status: null };
        }).filter(function(n) { return n.id; });
      }
    } catch(e) {}
    // Fallback: HTML search
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LNW + '/search?keywords=' + encodeURIComponent(query) + '&page=' + (page || 1)));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    return _lnwParseCards(doc, _LNW, 'lightnovelworld');
  },

  async getMangaDetail(novelId) {
    // Try .org first (QuickNovel's domain), fall back to .com
    var doc = null;
    var base = _LNW_ORG;
    try {
      doc = await _lnwFetchDetail(_LNW_ORG, novelId);
      if (!doc.querySelector('h1')) throw new Error('no title');
    } catch(e) {
      base = _LNW;
      doc = await _lnwFetchDetail(_LNW, novelId);
    }

    var titleEl = doc.querySelector('h1.novel-title, .novel-info h1, meta[property="og:title"]');
    var title = titleEl ? (titleEl.getAttribute('content') || titleEl.textContent.trim()) : novelId;

    var img = doc.querySelector('meta[property="og:image"]') || doc.querySelector('.novel-cover img, .book-cover img');
    var cover = img ? (img.getAttribute('content') || img.getAttribute('data-src') || img.getAttribute('src')) : null;
    if (cover && cover.startsWith('/')) cover = base + cover;

    var descEl = doc.querySelector('div.summary-content, .summary .content, .novel-summary, .description');
    var desc = descEl ? descEl.textContent.trim() : null;

    var genres = [];
    doc.querySelectorAll('div.genre-tags span.genre-tag, .categories a, .genre-item a, .tag').forEach(function(el) {
      var g = el.textContent.trim();
      if (g) genres.push(g);
    });

    var statusEl = doc.querySelector('span.status-badge, .header-stats .active, .novel-status');
    var status = statusEl ? statusEl.textContent.trim() : null;

    var authorEl = doc.querySelector('p.novel-author > a, .author a, .novel-author a');
    var authors = authorEl ? [authorEl.textContent.trim()] : [];

    // Chapters: use chapter-card + onClick pattern
    var chapters = _lnwParseChapterPage(doc, base, novelId);

    // If no chapters found, try fetching /chapters/ sub-page
    if (chapters.length === 0) {
      try {
        var chData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(base + '/novel/' + novelId + '/chapters/?page=1'));
        var chDoc = new DOMParser().parseFromString(chData.html, 'text/html');
        chapters = _lnwParseChapterPage(chDoc, base, novelId);
      } catch(e) {}
    }

    chapters.reverse();

    return { id: novelId, title: title, cover_url: cover, description: desc, status: status, genres: genres, authors: authors, provider: 'lightnovelworld', url: base + '/novel/' + novelId, chapters: chapters };
  },

  async getChapterText(chapterId) {
    var parts = chapterId.split('/');
    var novelSlug = parts[0];
    var chSlug = parts.slice(1).join('/');
    var content = null;
    // Try .org first
    for (var i = 0; i < 2; i++) {
      var base = i === 0 ? _LNW_ORG : _LNW;
      try {
        var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(base + '/novel/' + novelSlug + '/' + chSlug));
        var doc = new DOMParser().parseFromString(data.html, 'text/html');
        // QuickNovel: div.chapter-text; remove ads/nav
        var contentEl = doc.querySelector('div.chapter-text, #chapter-container, .chapter-content, .text-left');
        if (contentEl) {
          contentEl.querySelectorAll('script, style, .ads, .ad, .advertisement, .chapter-nav, [class*="ad-"]').forEach(function(el) { el.remove(); });
          content = contentEl.innerHTML;
          break;
        }
      } catch(e) {}
    }
    return { content: content ? _lnwSanitize(content) : '<p>Chapter content not found.</p>', format: 'html' };
  },

  async getPopular(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LNW_ORG + '/genre/all/?page=' + (page || 1) + '&order=popular'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var results = _lnwParseCards(doc, _LNW_ORG, 'lightnovelworld');
    if (results.length > 0) return results;
    // fallback to .com
    var data2 = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LNW + '/genre/all/popular?page=' + (page || 1)));
    var doc2 = new DOMParser().parseFromString(data2.html, 'text/html');
    return _lnwParseCards(doc2, _LNW, 'lightnovelworld');
  },

  async getLatest(page) {
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LNW_ORG + '/genre/all/?page=' + (page || 1) + '&order=updates'));
    var doc = new DOMParser().parseFromString(data.html, 'text/html');
    var results = _lnwParseCards(doc, _LNW_ORG, 'lightnovelworld');
    if (results.length > 0) return results;
    var data2 = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_LNW + '/genre/all/latest?page=' + (page || 1)));
    var doc2 = new DOMParser().parseFromString(data2.html, 'text/html');
    return _lnwParseCards(doc2, _LNW, 'lightnovelworld');
  },
};
