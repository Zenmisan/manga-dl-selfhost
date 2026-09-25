// Based on QuickNovel RanobesProvider (https://ranobes.net)
var _BASE = 'https://ranobes.net';

function _ranobesSanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '');
}

function _parseCards(doc) {
  var results = [];
  var seen = {};
  doc.querySelectorAll('div.short-cont').forEach(function(h) {
    var a = h.querySelector('h2.title > a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var slugMatch = href.match(/\/novels\/([^/]+?)(?:\.html)?$/);
    var slug = slugMatch ? slugMatch[1] : href.replace(_BASE, '').replace(/^\//, '').replace(/\.html$/, '');
    if (!slug || seen[slug]) return;
    seen[slug] = true;

    var title = a.textContent.trim();
    var fig = h.querySelector('div.cont.showcont figure, figure[style*="background-image"]');
    var cover = null;
    if (fig) {
      var style = fig.getAttribute('style') || '';
      var m = style.match(/url\(['"]?(.*?)['"]?\)/);
      if (m) cover = m[1];
    }
    if (!cover) {
      var img = h.querySelector('div.poster img, img');
      if (img) cover = img.getAttribute('src') || img.getAttribute('data-src');
    }
    if (cover && cover.startsWith('/')) cover = _BASE + cover;

    results.push({
      id: slug,
      title: title,
      cover_url: cover,
      provider: 'ranobes',
      url: href.startsWith('http') ? href : _BASE + href,
      status: null,
    });
  });
  return results;
}

var extension = {
  async search(query, page) {
    var p = page || 1;
    var body = 'do=search&subaction=search&search_start=' + ((p - 1) * 15) + '&full_search=0&result_from=' + (((p - 1) * 15) + 1) + '&story=' + encodeURIComponent(query.trim()) + '&dosearch=' + encodeURIComponent('Start search');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_BASE + '/index.php?do=search/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body,
    });
    var doc = new DOMParser().parseFromString(data.html || '', 'text/html');
    return _parseCards(doc);
  },

  async getMangaDetail(novelId) {
    var slug = novelId.replace(/^\//, '').replace(/\.html$/, '');
    var detailUrl = _BASE + '/novels/' + slug + '.html';
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(detailUrl));
    var doc = new DOMParser().parseFromString(data.html || '', 'text/html');

    var titleEl = doc.querySelector('h1.title');
    var title = titleEl ? titleEl.childNodes[0].textContent.trim() : slug;

    var coverEl = doc.querySelector('div.poster img, .r-fullstory-poster img');
    var cover = coverEl ? (coverEl.getAttribute('src') || coverEl.getAttribute('data-src')) : null;
    if (cover && cover.startsWith('/')) cover = _BASE + cover;

    var descEl = doc.querySelector('div.moreless, #fs-info div.text');
    var desc = descEl ? descEl.textContent.trim() : null;

    var authorEl = doc.querySelector('h1.title span, #fs-info li[title*="Author"] span');
    var authors = authorEl ? [authorEl.textContent.trim()] : [];

    var genres = [];
    doc.querySelectorAll('#mc-fs-genre a, a[href*="/tags/genre/"]').forEach(function(a) {
      var g = a.textContent.trim();
      if (g && genres.indexOf(g) === -1) genres.push(g);
    });

    var statusEl = doc.querySelector('li[title*="Original status"] span, li[title*="original"] span');
    var status = statusEl ? statusEl.textContent.trim() : 'Ongoing';

    // Extract book ID (e.g. from 1207214-make-the-immortal-sect...)
    var newsIdInput = doc.querySelector('input[name="newsid"]');
    var bookId = newsIdInput ? newsIdInput.getAttribute('value') : null;
    if (!bookId) {
      var idMatch = slug.match(/^(\d+)/);
      if (idMatch) bookId = idMatch[1];
    }

    var chapters = [];
    var seen = {};

    // 1. Fetch full chapters list from Ranobes TOC page (__DATA__ JSON)
    if (bookId) {
      try {
        var tocUrl = _BASE + '/chapters/' + bookId + '/';
        var tocData = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(tocUrl));
        var tocHtml = tocData.html || '';
        if (tocHtml.indexOf('window.__DATA__ =') !== -1) {
          var after = tocHtml.split('window.__DATA__ =')[1];
          var scriptPart = after.split('</script>')[0].trim();
          if (scriptPart.endsWith(';')) scriptPart = scriptPart.slice(0, -1).trim();
          var tocJson = JSON.parse(scriptPart);
          var chList = tocJson.chapters || [];
          // Ranobes TOC is descending (latest first); reverse for chronological order
          chList.slice().reverse().forEach(function(ch, idx) {
            var href = ch.link || '';
            var chSlug = href.replace(_BASE, '').replace(/^\//, '').replace(/\.html$/, '');
            if (!chSlug || seen[chSlug]) return;
            seen[chSlug] = true;
            var numMatch = ch.title.match(/chapter\s+([\d.]+)/i) || ch.title.match(/^(\d+)/);
            var num = numMatch ? parseFloat(numMatch[1]) : (idx + 1);
            chapters.push({
              id: chSlug,
              title: ch.title,
              number: num,
              published_at: ch.date ? ch.date.split(' ')[0] : null,
            });
          });

          // If multi-page TOC exists (pages_count > 1), fetch page 2 to load more chapters
          var totalPages = tocJson.pages_count || 1;
          if (totalPages > 1 && chapters.length < 100) {
            try {
              var p2Url = _BASE + '/chapters/' + bookId + '/page/2/';
              var p2Data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(p2Url));
              var p2Html = p2Data.html || '';
              if (p2Html.indexOf('window.__DATA__ =') !== -1) {
                var p2After = p2Html.split('window.__DATA__ =')[1];
                var p2Script = p2After.split('</script>')[0].trim();
                if (p2Script.endsWith(';')) p2Script = p2Script.slice(0, -1).trim();
                var p2Json = JSON.parse(p2Script);
                (p2Json.chapters || []).slice().reverse().forEach(function(ch, idx) {
                  var href = ch.link || '';
                  var chSlug = href.replace(_BASE, '').replace(/^\//, '').replace(/\.html$/, '');
                  if (!chSlug || seen[chSlug]) return;
                  seen[chSlug] = true;
                  var numMatch = ch.title.match(/chapter\s+([\d.]+)/i) || ch.title.match(/^(\d+)/);
                  var num = numMatch ? parseFloat(numMatch[1]) : (chapters.length + 1);
                  chapters.push({
                    id: chSlug,
                    title: ch.title,
                    number: num,
                    published_at: ch.date ? ch.date.split(' ')[0] : null,
                  });
                });
              }
            } catch(e) {}
          }
        }
      } catch(e) {
        console.warn('[Ranobes] TOC fetch error:', e);
      }
    }

    // 2. Fallback: Parse chapters present directly on the detail page scroll list
    if (chapters.length === 0) {
      doc.querySelectorAll('ul.chapters-scroll-list li a, a.chapter-item').forEach(function(a, idx) {
        var href = a.getAttribute('href') || '';
        var chSlug = href.replace(_BASE, '').replace(/^\//, '').replace(/\.html$/, '');
        if (!chSlug || seen[chSlug]) return;
        seen[chSlug] = true;
        var titleEl = a.querySelector('.title, span') || a;
        var chTitle = titleEl.textContent.trim() || ('Chapter ' + (idx + 1));
        var numMatch = chTitle.match(/chapter\s+([\d.]+)/i) || chSlug.match(/chapter-([\d]+)/i);
        var num = numMatch ? parseFloat(numMatch[1]) : (idx + 1);
        chapters.push({
          id: chSlug,
          title: chTitle,
          number: num,
          published_at: null,
        });
      });
      chapters.sort(function(a, b) { return a.number - b.number; });
    }

    return {
      id: slug,
      title: title,
      cover_url: cover,
      description: desc,
      status: status,
      genres: genres,
      authors: authors,
      provider: 'ranobes',
      url: detailUrl,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    return [];
  },

  async getChapterText(chapterId) {
    var url = chapterId.startsWith('http') ? chapterId : _BASE + '/' + chapterId + (chapterId.endsWith('.html') ? '' : '.html');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html || '', 'text/html');

    var contentEl = doc.querySelector('#arrticle, div.text#arrticle, article.story');
    if (!contentEl) return { content: '<p>Chapter content not found.</p>', format: 'html' };

    // Strip ads, banners, and third-party scripts
    contentEl.querySelectorAll('.free-support-top, .free-support, script, style, iframe, #podium-spot, [id*="pubadx"], [id*="ssp"], .adv-block, div.alert').forEach(function(el) {
      el.remove();
    });

    // Fix relative image URLs (light novel illustrations)
    contentEl.querySelectorAll('img').forEach(function(img) {
      var src = img.getAttribute('src') || '';
      if (src && src.startsWith('/')) {
        img.setAttribute('src', _BASE + src);
      }
    });

    var content = contentEl.innerHTML;
    return { content: _ranobesSanitize(content), format: 'html' };
  },

  async getPopular(page) {
    var p = page || 1;
    var url = _BASE + (p <= 1 ? '/tags/genre/All/' : '/tags/genre/All/page/' + p + '/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html || '', 'text/html');
    return _parseCards(doc);
  },

  async getLatest(page) {
    var p = page || 1;
    var url = _BASE + (p <= 1 ? '/novels/' : '/novels/page/' + p + '/');
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
    var doc = new DOMParser().parseFromString(data.html || '', 'text/html');
    return _parseCards(doc);
  },
};
