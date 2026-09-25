// Bun HTTP server — generates comixto _= tokens.
// POST /token  body: {"path": "/api/v1/chapters/5662950"}
// response: {"token": "IQ6wvJBq..."}
//
// Handles only paths matching /chapters/{digits} at the end.
// Tokens are deterministic (stream cipher over path), so we cache them.

import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dir = path.dirname(fileURLToPath(import.meta.url));

// Suppress all console output from bytecode internals
const noop = () => {};
globalThis.console = { log: noop, warn: noop, error: noop, info: noop, debug: noop, trace: noop };

// Suppress uncaught errors from bytecode background tasks (setInterval workers etc.)
process.on("uncaughtException", (err) => {
  // Only suppress errors from the bytecode VM; let our own errors propagate
  if (err && err.stack && err.stack.includes("secure-chunk.js")) return;
  process.stderr.write("uncaughtException: " + String(err) + "\n");
  process.exit(1);
});
process.on("unhandledRejection", (reason) => {
  if (reason && String(reason.stack || "").includes("secure-chunk.js")) return;
  process.stderr.write("unhandledRejection: " + String(reason) + "\n");
  process.exit(1);
});

// --- browser stubs needed by secure-chunk.js ---

globalThis.navigator = { appCodeName: "Mozilla", userAgent: "Mozilla/5.0", platform: "Linux" };
globalThis.window = globalThis;
globalThis.self = globalThis;
globalThis.location = {
  href: "https://comix.to/", protocol: "https:", host: "comix.to",
  hostname: "comix.to", pathname: "/", search: "", hash: "", origin: "https://comix.to",
  toString: () => "https://comix.to/",
};
globalThis.ImageData = class ImageData {};
const _store = {};
globalThis.localStorage = {
  getItem: (k) => _store[k] ?? null, setItem: (k, v) => { _store[k] = v; },
  removeItem: (k) => { delete _store[k]; }, clear: () => {},
};
globalThis.sessionStorage = globalThis.localStorage;
globalThis.history = { pushState: () => {}, replaceState: () => {}, back: () => {}, forward: () => {} };
globalThis.screen = { width: 1920, height: 1080, availWidth: 1920, availHeight: 1080, colorDepth: 24 };

const el = (tag = "div") => ({
  tagName: tag, style: {}, className: "", value: "", textContent: "",
  innerHTML: "", id: "", href: "", src: "", dataset: {},
  setAttribute: () => {}, getAttribute: () => null, hasAttribute: () => false,
  addEventListener: () => {}, removeEventListener: () => {},
  appendChild: () => null, removeChild: () => null, insertBefore: () => null,
  classList: { add: () => {}, remove: () => {}, contains: () => false, toggle: () => {} },
  children: [], childNodes: [], parentNode: null, offsetParent: null,
  getBoundingClientRect: () => ({ top: 0, left: 0, bottom: 0, right: 0, width: 0, height: 0 }),
  focus: () => {}, blur: () => {}, click: () => {}, dispatchEvent: () => true,
  querySelectorAll: () => [], querySelector: () => null,
});
globalThis.document = {
  createElement: el, getElementById: () => el(),
  querySelector: () => el(), querySelectorAll: () => [],
  addEventListener: () => {}, removeEventListener: () => {},
  readyState: "complete", body: el("body"), head: el("head"),
  documentElement: el("html"), title: "comixto", cookie: "",
  createTextNode: () => el("text"), createComment: () => el("comment"),
  URL: "https://comix.to/", referrer: "", domain: "comix.to",
};

// ------------------------------------------------

let _interceptor = null;
let _responseInterceptor = null;

async function init() {
  const mod = await import(path.join(__dir, "secure-chunk.js"));
  const P6 = mod.i;
  const mockAxios = {
    interceptors: {
      request: { use: (fn) => { _interceptor = fn; return 0; } },
      response: { use: (fn) => { _responseInterceptor = fn; return 0; } },
    },
    defaults: { baseURL: "https://comix.to", headers: { common: {}, get: {}, post: {} } },
  };
  P6(mockAxios);
}

const _cache = new Map();

async function generateToken(urlPath) {
  if (_cache.has(urlPath)) return _cache.get(urlPath);
  if (!_interceptor) return null;
  const config = { url: urlPath, baseURL: "https://comix.to", method: "get", params: {}, headers: {} };
  const result = await _interceptor(config);
  const token = result?.params?._ ?? null;
  if (token) _cache.set(urlPath, token);
  return token;
}

async function fetchAndDecrypt(fullUrl, cookie) {
  // Build a config object as the request interceptor would see it
  const urlObj = new URL(fullUrl);
  const config = {
    url: urlObj.pathname + urlObj.search,
    baseURL: "https://comix.to",
    method: "get",
    params: {},
    headers: {},
  };

  // Run through request interceptor to get token injected into params
  const modifiedConfig = await _interceptor(config);
  const token = modifiedConfig?.params?._ ?? null;

  // Build fetch URL with token
  const fetchUrl = token
    ? `${urlObj.origin}${urlObj.pathname}?_=${token}`
    : fullUrl;

  const fetchHeaders = {
    "Accept": "application/json",
    "Referer": "https://comix.to/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
  };
  if (cookie) fetchHeaders["Cookie"] = cookie;

  const fetchResp = await fetch(fetchUrl, { headers: fetchHeaders });
  if (!fetchResp.ok) {
    throw new Error(`HTTP ${fetchResp.status}`);
  }

  const rawData = await fetchResp.json();

  // Run through response interceptor to decrypt {"e":"..."} if present
  if (_responseInterceptor && rawData && typeof rawData === "object" && rawData.e) {
    const axiosLike = {
      data: rawData,
      status: fetchResp.status,
      statusText: "OK",
      headers: Object.fromEntries(fetchResp.headers.entries()),
      config: modifiedConfig,
    };
    const decrypted = await _responseInterceptor(axiosLike);
    // axios interceptors return the full response object; .data is the payload
    return decrypted?.data ?? decrypted;
  }

  return rawData;
}

const PORT = 5175;

async function main() {
  await init();

  const server = createServer(async (req, res) => {
    let body = "";
    for await (const chunk of req) body += chunk;

    if (req.method === "POST" && req.url === "/token") {
      let urlPath;
      try { urlPath = JSON.parse(body).path; }
      catch { res.writeHead(400); res.end('{"error":"bad json"}'); return; }
      const token = await generateToken(urlPath);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ token }));
      return;
    }

    if (req.method === "POST" && req.url === "/proxy") {
      let url, cookie;
      try {
        const parsed = JSON.parse(body);
        url = parsed.url;
        cookie = parsed.cookie ?? null;
      } catch {
        res.writeHead(400); res.end('{"error":"bad json"}'); return;
      }
      if (!url) { res.writeHead(400); res.end('{"error":"url required"}'); return; }
      try {
        const data = await fetchAndDecrypt(url, cookie);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify(data));
      } catch (err) {
        res.writeHead(502, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: String(err.message) }));
      }
      return;
    }

    res.writeHead(404);
    res.end('{"error":"not found"}');
  });

  server.listen(PORT, "127.0.0.1", () => {
    process.stdout.write(`ready:${PORT}\n`);
  });
}

main().catch(e => { process.stderr.write(String(e) + "\n"); process.exit(1); });
