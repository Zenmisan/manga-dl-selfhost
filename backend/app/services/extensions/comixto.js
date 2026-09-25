// Comix.to — custom API with grid-scramble (V3) and byte-XOR (legacy) image DRM.
// Descrambling happens in the browser via Canvas API after fetching through our proxy.
var _CX = 'https://comix.to';

var GRID_COLS = 5;
var GRID_ROWS = 5;
var NUM_TILES = 25;
var ENC_MULTIPLIER = 1000005;
var ENC_INCREMENT = 1234567891;
var LCG_MULTIPLIER = 1664525;
var LCG_INCREMENT = 1013904223;

// ── LCG helpers (32-bit signed, matching Kotlin toInt()) ─────────────────────
function int32(n) { return n | 0; }

function nextXorshift(state) {
  var s = int32(state);
  s = int32(s ^ int32(s << 13));
  s = int32(s ^ (s >>> 17));
  s = int32(s ^ int32(s << 5));
  return s;
}

// Build tile permutation order using xorshift (algo 3)
function buildOrderXorshift(seed, n) {
  var arr = [];
  for (var i = 0; i < n; i++) arr[i] = i;
  var state = int32(seed | 1);
  for (var i = n - 1; i >= 1; i--) {
    state = nextXorshift(state);
    var j = ((state >>> 0) % (i + 1)) | 0;
    var tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
  }
  // Return inverse permutation
  var inv = new Array(n);
  for (var i = 0; i < n; i++) inv[arr[i]] = i;
  return inv;
}

// Build tile permutation order using LCG (algo 1/2/null)
function buildOrderLcg(seed, n) {
  var arr = [];
  for (var i = 0; i < n; i++) arr[i] = i;
  var state = int32(seed);
  for (var i = n - 1; i >= 1; i--) {
    state = int32(int32(state * LCG_MULTIPLIER) + LCG_INCREMENT);
    var j = ((state >>> 0) % (i + 1)) | 0;
    var tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
  }
  var inv = new Array(n);
  for (var i = 0; i < n; i++) inv[arr[i]] = i;
  return inv;
}

// XOR decode using LCG stream (default / algo 1)
function decodeWithLcg(bytes, seed, length) {
  var result = new Uint8Array(bytes);
  var state = int32(seed);
  var limit = Math.min(result.length, length);
  for (var i = 0; i < limit; i++) {
    state = int32(int32(state * ENC_MULTIPLIER) + ENC_INCREMENT);
    result[i] ^= (state >>> 24) & 0xFF;
  }
  return result;
}

// XOR decode using xorshift stream (algo 2)
function decodeWithXorshift(bytes, initialState, length, highByte) {
  var result = new Uint8Array(bytes);
  var state = int32(initialState);
  var limit = Math.min(result.length, length);
  for (var i = 0; i < limit; i++) {
    state = nextXorshift(state);
    var key = highByte ? ((state >>> 24) & 0xFF) : (state & 0xFF);
    result[i] ^= key;
  }
  return result;
}

function hasImageSignature(bytes) {
  if (bytes.length < 12) return false;
  if (bytes[0] === 0xFF && bytes[1] === 0xD8) return true; // JPEG
  if (bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4E && bytes[3] === 0x47) return true; // PNG
  if (bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46 &&
      bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50) return true; // WEBP
  return false;
}

// ── Grid descrambler (runs in browser via Canvas) ─────────────────────────────
function descrambleImageBuffer(arrayBuffer, scrambleSeed, scrambleAlgo, encSeed, encLen, encAlgo) {
  return new Promise(function(resolve, reject) {
    var bytes = new Uint8Array(arrayBuffer);

    // Step 1: XOR decode if needed
    if (encSeed && encSeed !== 0 && encLen) {
      if (encAlgo === '2') {
        var seed32 = int32(encSeed);
        var candidates = [
          decodeWithXorshift(bytes, int32(seed32 | 1), encLen, false),
          decodeWithXorshift(bytes, seed32, encLen, false),
          decodeWithXorshift(bytes, int32(seed32 | 1), encLen, true),
          decodeWithLcg(bytes, seed32, encLen),
        ];
        var found = null;
        for (var i = 0; i < candidates.length; i++) {
          if (hasImageSignature(candidates[i])) { found = candidates[i]; break; }
        }
        bytes = found || candidates[0];
      } else {
        bytes = decodeWithLcg(bytes, int32(encSeed), encLen);
      }
    }

    // Step 2: Grid descramble if needed
    if (scrambleSeed && scrambleSeed !== 0) {
      var blob = new Blob([bytes], { type: 'image/jpeg' });
      var url = URL.createObjectURL(blob);
      var img = new Image();
      img.onload = function() {
        var w = img.naturalWidth;
        var h = img.naturalHeight;
        var tileW = Math.floor(w / GRID_COLS);
        var tileH = Math.floor(h / GRID_ROWS);
        var canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        var order = scrambleAlgo === '3'
          ? buildOrderXorshift(int32(scrambleSeed), NUM_TILES)
          : buildOrderLcg(int32(scrambleSeed), NUM_TILES);
        var out = document.createElement('canvas');
        out.width = w; out.height = h;
        var octx = out.getContext('2d');
        for (var dst = 0; dst < NUM_TILES; dst++) {
          var src = order[dst];
          var srcCol = src % GRID_COLS, srcRow = (src / GRID_COLS) | 0;
          var dstCol = dst % GRID_COLS, dstRow = (dst / GRID_COLS) | 0;
          octx.drawImage(canvas,
            srcCol * tileW, srcRow * tileH, tileW, tileH,
            dstCol * tileW, dstRow * tileH, tileW, tileH
          );
        }
        URL.revokeObjectURL(url);
        out.toBlob(function(b) {
          var fr = new FileReader();
          fr.onload = function() { resolve(fr.result); };
          fr.readAsDataURL(b);
        }, 'image/jpeg', 0.92);
      };
      img.onerror = function() { URL.revokeObjectURL(url); reject(new Error('Image decode failed')); };
      img.src = url;
    } else {
      // No grid scramble, just return decoded bytes as data URL
      var blob2 = new Blob([bytes], { type: 'image/jpeg' });
      var fr2 = new FileReader();
      fr2.onload = function() { resolve(fr2.result); };
      fr2.readAsDataURL(blob2);
    }
  });
}

// ── Page URL wrapper — encodes DRM params so reader can call descrambler ──────
// Format: comixto://img?url=<enc>&seed=<s>&algo=<a>&encSeed=<es>&encLen=<el>&encAlgo=<ea>
function wrapPageUrl(imageUrl, seed, algo, encSeed, encLen, encAlgo) {
  var params = 'url=' + encodeURIComponent(imageUrl);
  if (seed) params += '&seed=' + seed + '&algo=' + (algo || '');
  if (encSeed) params += '&encSeed=' + encSeed + '&encLen=' + (encLen || 0) + '&encAlgo=' + (encAlgo || '');
  return 'comixto://img?' + params;
}

// ── Site data fetching ────────────────────────────────────────────────────────
async function _fetchDoc(url) {
  var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(url));
  return new DOMParser().parseFromString(data.html, 'text/html');
}

function _extractInitialData(doc) {
  var script = doc.querySelector('script#initial-data');
  if (!script) return null;
  try { return JSON.parse(script.textContent); } catch(e) { return null; }
}

function _parseBrowseManga(items) {
  return (items || []).map(function(m) {
    var hid = m.hid || m.slug || '';
    var titleUrl = m.url ? (_CX + m.url) : (_CX + '/title/' + hid);
    var poster = m.poster;
    var cover = typeof poster === 'string' ? poster :
      (poster?.large || poster?.medium || poster?.small || null);
    return {
      id: hid,
      title: m.title || m.name || '',
      cover_url: cover,
      provider: 'comixto',
      url: titleUrl,
      status: m.status || null,
    };
  }).filter(function(m) { return m.id; });
}

var extension = {
  async search(query, page) {
    var p = page || 1;
    var doc = await _fetchDoc(_CX + '/browse?search=' + encodeURIComponent(query) + '&page=' + p);
    var init = _extractInitialData(doc);
    if (init) {
      var queries = init.queries || {};
      for (var key in queries) {
        var q = queries[key];
        if (q && q.result && Array.isArray(q.result.items) && q.result.items.length) {
          return _parseBrowseManga(q.result.items);
        }
      }
    }
    // DOM fallback
    var results = [];
    doc.querySelectorAll('a[href*="/title/"]').forEach(function(a) {
      var href = a.getAttribute('href') || '';
      var id = href.split('/title/')[1]?.replace(/\/$/, '') || '';
      if (!id) return;
      var img = a.querySelector('img');
      var titleEl = a.querySelector('[class*="title"], p, span');
      results.push({ id: id, title: titleEl ? titleEl.textContent.trim() : id, cover_url: img ? img.getAttribute('src') : null, provider: 'comixto', url: _CX + href, status: null });
    });
    return results;
  },

  async getMangaDetail(mangaId) {
    var hid = mangaId.split('-')[0];
    var doc = await _fetchDoc(_CX + '/title/' + mangaId);
    var init = _extractInitialData(doc);
    var manga = null;
    if (init) {
      for (var key in (init.queries || {})) {
        if (key.includes('"manga","detail"')) { manga = init.queries[key]; break; }
      }
    }
    var title = (manga && manga.title) || (doc.querySelector('h1') || {}).textContent || mangaId;
    var poster = manga && manga.poster;
    var cover = poster ? (poster.large || poster.medium || poster.small || null) : null;
    var desc = (manga && manga.synopsis) || '';
    var genres = [];
    ((manga && manga.genres) || []).forEach(function(g) { genres.push(g.title || g.name || g); });
    ((manga && manga.tags) || []).forEach(function(t) { genres.push(t.title || t.name || t); });
    var authors = [];
    ((manga && manga.authors) || []).forEach(function(a) { authors.push(a.title || a.name || a); });

    // Fetch full chapter list via authed API
    var chapters = [];
    try {
      var numericId = (manga && manga.id) || null;
      var apiHid = (manga && manga.hid) || hid;
      var page = 1;
      while (true) {
        var chData = await apiFetch('/manga/proxy/json?url=' + encodeURIComponent(
          _CX + '/api/v1/manga/' + apiHid + '/chapters?page=' + page + '&limit=100&order%5Bnumber%5D=desc'
        ));
        var items = chData.items || [];
        items.forEach(function(ch) {
          var chHid = ch.hid || ch.id || '';
          var num = parseFloat(ch.chap || ch.number || ch.chapter || 0);
          chapters.push({
            id: '/title/' + mangaId + '/' + ch.id + '-chapter-' + (ch.chap || num),
            title: ch.title || ('Chapter ' + (ch.chap || num)),
            number: num,
            published_at: ch.created_at || null,
          });
        });
        if (items.length < 100) break;
        page++;
      }
    } catch(e) {
      // fallback: use first/latest from SSR
      if (manga && manga.latestChapterUrl) {
        chapters.push({ id: manga.latestChapterUrl, title: 'Chapter ' + (manga.latestChapter || '?'), number: parseFloat(manga.latestChapter) || 0, published_at: null });
      }
      if (manga && manga.firstChapterUrl && manga.firstChapterUrl !== manga.latestChapterUrl) {
        chapters.push({ id: manga.firstChapterUrl, title: 'Chapter 1', number: 1, published_at: null });
      }
    }

    return {
      id: mangaId, title: String(title).trim(), cover_url: cover,
      description: desc ? String(desc).trim() : null,
      status: (manga && manga.status) || null,
      genres: genres, authors: authors,
      provider: 'comixto',
      url: _CX + '/title/' + mangaId,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    // chapterId is like "/title/e05zm-.../5578639-chapter-1"
    // Extract the numeric chapter ID from the path
    var parts = chapterId.replace(/^\/title\/[^/]+\//, '').split('-');
    var numericId = parts[0];

    // Fetch pages via authed API
    try {
      var data = await apiFetch('/manga/proxy/json?url=' + encodeURIComponent(
        _CX + '/api/v1/chapters/' + numericId
      ));
      var pagesData = data.pages || data;
      var base = (pagesData.baseUrl || '').replace(/\/$/, '');
      var items = pagesData.items || [];
      if (items.length) {
        return items.map(function(img) {
          var full = base + '/' + img.url;
          if (img.s === 1) full += (full.includes('?') ? '&' : '?') + 'v3';
          return wrapPageUrl(
            full,
            img.scramble_seed || null,
            img.scramble_algo || null,
            img.enc_seed || null,
            img.enc_len || null,
            img.enc_algo || null
          );
        });
      }
    } catch(e) {}

    // Fallback: fetch chapter HTML page and parse SSR
    var doc = await _fetchDoc(_CX + chapterId);
    var init = _extractInitialData(doc);
    if (init) {
      for (var key in (init.queries || {})) {
        var q = init.queries[key];
        if (q && q.pages) {
          var pd = q.pages;
          var b = (pd.baseUrl || '').replace(/\/$/, '');
          var pageList = (pd.items || []).map(function(img) {
            var full = b + '/' + img.url;
            if (img.s === 1) full += (full.includes('?') ? '&' : '?') + 'v3';
            return wrapPageUrl(full, img.scramble_seed || null, img.scramble_algo || null, img.enc_seed || null, img.enc_len || null, img.enc_algo || null);
          });
          if (pageList.length) return pageList;
        }
      }
    }
    return [];
  },

  async getPopular(page) {
    // Browse page items are client-side only (API needs auth).
    // Homepage SSR has 50 trending + 31 hot — only reliable for page 1.
    if ((page || 1) > 1) return [];
    var doc = await _fetchDoc(_CX + '/');
    var init = _extractInitialData(doc);
    if (!init) return [];
    var queries = init.queries || {};
    // trending array (direct array, not {result:{items:[]}})
    for (var key in queries) {
      var val = queries[key];
      if (Array.isArray(val) && val.length && val[0] && val[0].hid) {
        return _parseBrowseManga(val);
      }
    }
    return [];
  },

  async getLatest(page) {
    if ((page || 1) > 1) return [];
    var doc = await _fetchDoc(_CX + '/');
    var init = _extractInitialData(doc);
    if (!init) return [];
    var queries = init.queries || {};
    // hot list with latest chapter updates — stored as {items:[...], meta:{}}
    for (var key in queries) {
      var val = queries[key];
      if (val && Array.isArray(val.items) && val.items.length && val.items[0] && val.items[0].hid) {
        return _parseBrowseManga(val.items);
      }
    }
    return [];
  },

  // Exposed so the reader can call it on comixto://img? URLs
  descrambleImageBuffer: descrambleImageBuffer,
};
