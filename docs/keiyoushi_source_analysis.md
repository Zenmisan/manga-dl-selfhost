# Keiyoushi Extension Source Analysis

This report analyzes the architecture, scraping techniques, and protection workarounds utilized by the **Keiyoushi** (Tachiyomi/Mihon compatible) extension codebase and provides concrete strategies for integrating these patterns into `manga-dl`.

---

## 1. Repository Structure Overview

* **[extensions](file:///home/zenmi/Projects/extensions)**: The compiled output repository. It hosts the package index (`index.json`) and pre-built Android APK binaries.
* **[extensions-source](file:///home/zenmi/Projects/extensions-source)**: A Gradle-based Kotlin monorepo hosting the source files for 400+ extensions categorized by language (under `src/`), along with shared libraries and templates (`lib-multisrc/`).

---

## 2. Key Architectural Patterns

### A. The Multi-Source Architecture (`lib-multisrc`)
Instead of rewriting scraping logic for every single website, Keiyoushi groups sites by the underlying WordPress theme or CMS engine they use:
* **Madara** (webtoon theme used by hundreds of sites)
* **MangaThemesia**
* **FoolSlide**
* **WpComics**

#### Integration Strategy for `manga-dl`
Currently, `manga-dl` implements individual scraper scripts in `sources.py`. We can implement a similar **Template-based JS Extension Class** pattern in the frontend:
```javascript
// Generic Madara theme scraper
class MadaraExtension {
  constructor(baseUrl, providerId) {
    this.baseUrl = baseUrl;
    this.provider = providerId;
  }
  
  async search(query, page) {
    // Generic Madara search query selector
    var doc = await _fetchDoc(this.baseUrl + '/?s=' + encodeURIComponent(query) + '&post_type=wp-manga');
    // Map standard Madara elements...
  }
  
  async getPages(chapterId) {
    // Madara standard chapter page parsing logic...
  }
}

// Then defining a new source is as simple as:
const extension = new MadaraExtension('https://mangafast.net', 'mangafast');
```
This single class would instantly unlock support for dozens of Madara-based scanlation sites.

---

## 3. Advanced Bypass and Scraping Techniques

Analyzing the [AsuraScans.kt](file:///home/zenmi/Projects/extensions-source/src/en/asurascans/src/eu/kanade/tachiyomi/extension/en/asurascans/AsuraScans.kt) source code reveals two advanced patterns used to scrape the modern Astro-based Asura Scans platform:

### A. Astro Prop Extraction & Deserialization
Astro pages hydrate client-side interactive elements (like the reader) by serializing the component state inside `<astro-island>` tags as a JSON `props` attribute.
However, Astro wraps these props in custom serialization arrays to retain type metadata (e.g. `[0, "string"]` or `[1, [array]]`). Keiyoushi extracts these raw props and unwraps them recursively:

```kotlin
private fun JsonElement.unwrapAstro(): JsonElement = when (this) {
    is JsonArray -> when {
        size == 2 && this[0] is JsonPrimitive -> this[1].unwrapAstro()
        else -> JsonArray(map { it.unwrapAstro() })
    }
    is JsonObject -> JsonObject(mapValues { it.value.unwrapAstro() })
    else -> this
}
```

#### Integration Strategy for `manga-dl`
If Asura Scans updates their DOM structure in a way that breaks plain `<img>` scraping, we can implement `unwrapAstro` in our JS extensions to extract metadata/pages directly from the `<astro-island props="...">` attribute:
```javascript
function unwrapAstro(el) {
  if (Array.isArray(el)) {
    if (el.length === 2 && typeof el[0] === 'number') {
      return unwrapAstro(el[1]);
    }
    return el.map(unwrapAstro);
  }
  if (typeof el === 'object' && el !== null) {
    var out = {};
    for (var k in el) {
      out[k] = unwrapAstro(el[k]);
    }
    return out;
  }
  return el;
}
```

### B. Image Scrambling / De-obfuscation
To prevent hotlinking and direct downloading, Asura Scans scrambled some of their page images. The page JSON contains grid reconstruction metadata (`tiles` mapping array, `tile_cols`, and `tile_rows`).
Keiyoushi embeds this data in the URL fragment/hash (e.g. `https://domain.com/image.webp#{"tiles":[...],"tileCols":4,"tileRows":5}`) and descrambles the image on the fly:

```kotlin
val tileW = source.width / pageData.tileCols
val tileH = source.height / pageData.tileRows
// Draw source pieces to reconstructed canvas coordinates:
canvas.drawBitmap(source, srcRect, dstRect, null)
```

#### Integration Strategy for `manga-dl`
We can implement this client-side directly in the `manga-dl` reader component!
If the page URL contains descrambling metadata inside its hash/fragment:
1. The reader loads the image into a hidden `Image` element.
2. Creates an HTML5 `<canvas>` with the correct final dimensions.
3. Obtains the 2D context and uses `ctx.drawImage(img, sx, sy, sw, sh, dx, dy, dw, dh)` to copy the tiles into the descrambled layout.
4. Renders the canvas to the user or downloads it as a Blob.

This provides seamless webtoon reading for encrypted sources without any server-side computing overhead.
