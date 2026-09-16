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
    return {
      id: String(m.id || m.slug || ''),
      title: m.name || m.title || '',
      cover_url: m.poster?.large || m.poster?.medium || m.poster?.small || null,
      provider: 'comixto',
      url: _CX + '/title/' + (m.id || m.slug),
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
    var doc = await _fetchDoc(_CX + '/title/' + mangaId);
    var init = _extractInitialData(doc);
    var manga = null;
    if (init) {
      var queries = init.queries || {};
      for (var key in queries) {
        var q = queries[key];
        if (q && q.result && q.result.manga) { manga = q.result.manga; break; }
      }
    }
    var title = manga?.name || (doc.querySelector('h1') || {}).textContent || mangaId;
    var cover = manga?.poster?.large || doc.querySelector('img[class*="cover"]')?.getAttribute('src');
    var desc = manga?.description || (doc.querySelector('[class*="synopsis"], [class*="description"]') || {}).textContent;
    var chapters = [];
    (manga?.chapters || []).forEach(function(ch) {
      chapters.push({
        id: String(ch.id || ch.slug),
        title: ch.name || ('Chapter ' + ch.number),
        number: parseFloat(ch.number || ch.chapterNumber || 0),
        published_at: ch.publishedAt || ch.createdAt || null,
      });
    });
    if (!chapters.length) {
      doc.querySelectorAll('a[href*="/chapter/"]').forEach(function(a) {
        var href = a.getAttribute('href') || '';
        var chId = href.split('/chapter/')[1]?.replace(/\/$/, '') || '';
        if (!chId) return;
        var text = a.textContent.trim();
        var numM = text.match(/([\d.]+)/);
        chapters.push({ id: chId, title: text, number: numM ? parseFloat(numM[1]) : 0, published_at: null });
      });
    }
    return {
      id: mangaId, title: title.trim(), cover_url: cover || null,
      description: desc ? desc.trim() : null,
      status: manga?.status || null,
      genres: (manga?.tags || []).map(function(t) { return t.name || t; }),
      authors: manga?.authors ? [manga.authors] : [],
      provider: 'comixto',
      url: _CX + '/title/' + mangaId,
      chapters: chapters,
    };
  },

  async getPages(chapterId) {
    // Comix.to loads pages via JS — fetch the chapter page and extract from SSR data
    var data = await apiFetch('/manga/proxy/html?url=' + encodeURIComponent(_CX + '/chapter/' + chapterId));
    var html = data.html;
    var doc = new DOMParser().parseFromString(html, 'text/html');
    var init = _extractInitialData(doc);

    // Extract from SSR
    var pages = [];
    if (init) {
      var queries = init.queries || {};
      for (var key in queries) {
        var q = queries[key];
        if (q && q.result && q.result.pages) {
          var pagesData = q.result.pages;
          var base = (pagesData.baseUrl || '').replace(/\/$/, '');
          (pagesData.items || []).forEach(function(img, idx) {
            // Determine if V3 (grid-scramble) or legacy XOR
            var isV3 = img.s === 1;
            var full = base + '/' + img.url;
            if (isV3) full += (full.includes('?') ? '&' : '?') + 'v3';
            pages.push(wrapPageUrl(full, null, null, null, null, null));
          });
          if (pages.length) return pages;
        }
      }
    }

    // DOM fallback
    doc.querySelectorAll('img[class*="page"], .reading-content img, [data-page] img').forEach(function(img) {
      var src = img.getAttribute('src') || img.getAttribute('data-src');
      if (src && src.startsWith('http')) pages.push(src);
    });
    return pages;
  },

  async getPopular(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_CX + '/browse?order[score]=desc&page=' + p);
    var init = _extractInitialData(doc);
    if (init) {
      for (var key in (init.queries || {})) {
        var q = init.queries[key];
        if (q && q.result && Array.isArray(q.result.items) && q.result.items.length) return _parseBrowseManga(q.result.items);
      }
    }
    return [];
  },

  async getLatest(page) {
    var p = page || 1;
    var doc = await _fetchDoc(_CX + '/browse?order[chapter_updated_at]=desc&page=' + p);
    var init = _extractInitialData(doc);
    if (init) {
      for (var key in (init.queries || {})) {
        var q = init.queries[key];
        if (q && q.result && Array.isArray(q.result.items) && q.result.items.length) return _parseBrowseManga(q.result.items);
      }
    }
    return [];
  },

  // Exposed so the reader can call it on comixto://img? URLs
  descrambleImageBuffer: descrambleImageBuffer,
};
