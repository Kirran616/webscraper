"""
Web Scraper Tool — ONE single file (Python + HTML + JavaScript)
================================================================
Everything is in this one file: the Python scraper, the Flask
backend and the HTML/JS frontend. No scraper.py, no index.html
needed — just this file plus requirements.txt.

What it does: paste a link, it extracts the title, meta tags,
headings, paragraphs, links, images, tables, lists, forms,
emails and phone numbers from that page.

Run it locally:
    pip install -r requirements.txt
    python app.py
    # open http://127.0.0.1:5000

Run it on Render:
    Push this file + requirements.txt + Procfile to GitHub,
    create a Web Service in Render with Start Command:
        gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120
    (render.yaml in this folder does that automatically.)

Only scrape public pages you are allowed to scrape.
"""

import os
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS

# ------------------------------------------------------------------
# 1. PYTHON SCRAPER
# ------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")


def _text(tag):
    """Clean text from a tag: strip whitespace, collapse spaces."""
    return " ".join(tag.get_text(" ", strip=True).split()) if tag else ""


def _absolute(base_url, link):
    """Turn a relative link (/about) into a full URL."""
    return urljoin(base_url, link.strip()) if link else ""


def scrape_url(url):
    """Fetch a URL and return all extracted information as a dict."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    parsed = urlparse(url)

    # --- Meta / head information ---
    title = _text(soup.title)

    def meta_content(name=None, prop=None):
        tag = None
        if name:
            tag = soup.find("meta", attrs={"name": name})
        if tag is None and prop:
            tag = soup.find("meta", attrs={"property": prop})
        return tag.get("content", "").strip() if tag and tag.get("content") else ""

    meta = {
        "description": meta_content(name="description"),
        "keywords": meta_content(name="keywords"),
        "author": meta_content(name="author"),
        "og:title": meta_content(prop="og:title"),
        "og:description": meta_content(prop="og:description"),
        "og:image": meta_content(prop="og:image"),
        "twitter:card": meta_content(name="twitter:card"),
    }

    # --- Headings ---
    headings = {}
    for level in range(1, 7):
        tag_name = "h" + str(level)
        headings[tag_name] = [_text(h) for h in soup.find_all(tag_name)]

    # --- Main text ---
    paragraphs = [_text(p) for p in soup.find_all("p") if _text(p)]
    full_text = soup.get_text(" ", strip=True)
    word_count = len(full_text.split())

    # --- Links ---
    links = []
    for a in soup.find_all("a", href=True):
        href = _absolute(url, a["href"])
        links.append({"text": _text(a), "href": href})
    internal_links = [l for l in links if urlparse(l["href"]).netloc == parsed.netloc]
    external_links = [l for l in links if urlparse(l["href"]).netloc and urlparse(l["href"]).netloc != parsed.netloc]

    # --- Images ---
    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        images.append({"src": _absolute(url, src), "alt": img.get("alt", "")})

    # --- Lists ---
    lists = []
    for ul in soup.find_all(["ul", "ol"]):
        items = [_text(li) for li in ul.find_all("li", recursive=False)]
        if items:
            lists.append({"type": ul.name, "items": items})

    # --- Tables ---
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [_text(c) for c in tr.find_all(["th", "td"])]
            if cells:
                rows.append(cells)
        if rows:
            tables.append({"rows": rows})

    # --- Forms ---
    forms = []
    for form in soup.find_all("form"):
        forms.append({
            "action": _absolute(url, form.get("action", "")),
            "method": (form.get("method") or "get").upper(),
            "inputs": [
                {"name": i.get("name", ""), "type": i.get("type", "text")}
                for i in form.find_all(["input", "select", "textarea"])
            ],
        })

    # --- Scripts / stylesheets ---
    scripts = [_absolute(url, s.get("src")) for s in soup.find_all("script", src=True)]
    stylesheets = [
        _absolute(url, link.get("href"))
        for link in soup.find_all("link", rel="stylesheet")
    ]

    # --- Contact details found in the page text ---
    emails = sorted(set(EMAIL_RE.findall(full_text)))
    phones = sorted(set(p.strip() for p in PHONE_RE.findall(full_text)))

    return {
        "url": url,
        "status_code": response.status_code,
        "title": title,
        "meta": meta,
        "headings": headings,
        "paragraphs": paragraphs,
        "word_count": word_count,
        "links": links,
        "internal_links": internal_links,
        "external_links": external_links,
        "images": images,
        "lists": lists,
        "tables": tables,
        "forms": forms,
        "scripts": scripts,
        "stylesheets": stylesheets,
        "emails": emails,
        "phone_numbers": phones,
        "counts": {
            "paragraphs": len(paragraphs),
            "links": len(links),
            "internal_links": len(internal_links),
            "external_links": len(external_links),
            "images": len(images),
            "tables": len(tables),
            "forms": len(forms),
        },
    }


# ------------------------------------------------------------------
# 2. HTML + JAVASCRIPT FRONTEND (inside the same file)
# ------------------------------------------------------------------

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Web Scraper Tool</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: Arial, Helvetica, sans-serif; margin: 0; background: #f4f6f8; color: #222; }
  header { background: #0a2a5e; color: #fff; padding: 24px 20px; text-align: center; }
  header p { margin: 6px 0 0; opacity: .85; }
  main { max-width: 900px; margin: 24px auto; padding: 0 16px 40px; }
  .card { background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,.08); margin-bottom: 18px; }
  label { font-weight: bold; display: block; margin-bottom: 8px; }
  input[type="url"] { width: 100%; padding: 12px; font-size: 16px; border: 1px solid #ccc; border-radius: 8px; }
  button { margin-top: 12px; padding: 12px 22px; font-size: 16px; border: 0; border-radius: 8px; background: #0a7a3d; color: #fff; cursor: pointer; }
  button:disabled { opacity: .6; cursor: wait; }
  button.secondary { background: #0a2a5e; margin-left: 8px; }
  #status { margin-top: 12px; color: #b00020; }
  .stats { display: flex; flex-wrap: wrap; gap: 10px; margin: 12px 0; }
  .stat { background: #eef4ff; border-radius: 8px; padding: 10px 14px; }
  .stat b { font-size: 20px; display: block; }
  h2 { margin-top: 0; }
  ul { padding-left: 20px; }
  li { margin-bottom: 6px; word-break: break-word; }
  pre { background: #111; color: #d6ffd6; padding: 14px; border-radius: 8px; overflow: auto; max-height: 400px; }
  .hidden { display: none; }
  a { color: #0a2a5e; }
</style>
</head>
<body>
<header>
  <h1>Web Scraper Tool</h1>
  <p>Paste a link &mdash; get the title, headings, text, links, images, tables and more.</p>
</header>
<main>
  <div class="card">
    <label for="url">Website link</label>
    <input type="url" id="url" placeholder="https://example.com" value="https://example.com">
    <button id="scrapeBtn" onclick="scrape()">Scrape this page</button>
    <button id="downloadBtn" class="secondary hidden" onclick="downloadJson()">Download JSON</button>
    <div id="status"></div>
  </div>
  <div id="results" class="hidden">
    <div class="card">
      <h2 id="resultTitle"></h2>
      <p id="resultMeta"></p>
      <div class="stats" id="stats"></div>
    </div>
    <div class="card">
      <h2>Headings</h2>
      <div id="headings"></div>
    </div>
    <div class="card">
      <h2>Links (<span id="linkCount">0</span>)</h2>
      <ul id="links"></ul>
    </div>
    <div class="card">
      <h2>Images (<span id="imageCount">0</span>)</h2>
      <ul id="images"></ul>
    </div>
    <div class="card">
      <h2>Full JSON</h2>
      <pre id="jsonOut"></pre>
    </div>
  </div>
</main>
<script>
let lastData = null;
async function scrape() {
  const url = document.getElementById('url').value.trim();
  const status = document.getElementById('status');
  const btn = document.getElementById('scrapeBtn');
  if (!url) { status.textContent = 'Please paste a link first.'; return; }
  status.textContent = 'Scraping, please wait.';
  btn.disabled = true;
  try {
    const res = await fetch('/api/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Scraping failed.');
    lastData = data;
    showResults(data);
    status.textContent = '';
  } catch (err) {
    status.textContent = 'Error: ' + err.message + ' - make sure you ran "python app.py" first.';
  } finally {
    btn.disabled = false;
  }
}
function showResults(data) {
  document.getElementById('results').classList.remove('hidden');
  document.getElementById('downloadBtn').classList.remove('hidden');
  document.getElementById('resultTitle').textContent = data.title || '(no title)';
  document.getElementById('resultMeta').textContent = (data.meta && data.meta.description) || '';
  document.getElementById('resultMeta').textContent += '  -  ' + data.url;
  const c = data.counts;
  document.getElementById('stats').innerHTML =
    stat(c.links, 'Links') + stat(c.images, 'Images') +
    stat(c.paragraphs, 'Paragraphs') + stat(data.word_count, 'Words') +
    stat(c.tables, 'Tables') + stat(c.forms, 'Forms');
  let headingsHtml = '';
  for (const level in data.headings) {
    data.headings[level].forEach(function (h) {
      headingsHtml += '<p><b>' + level.toUpperCase() + ':</b> ' + escapeHtml(h) + '</p>';
    });
  }
  document.getElementById('headings').innerHTML = headingsHtml || '<p>No headings found.</p>';
  document.getElementById('linkCount').textContent = data.links.length;
  document.getElementById('links').innerHTML = data.links.slice(0, 100).map(function (l) {
    return '<li><a href="' + escapeHtml(l.href) + '" target="_blank" rel="noopener">' + escapeHtml(l.text || l.href) + '</a></li>';
  }).join('') || '<li>No links found.</li>';
  document.getElementById('imageCount').textContent = data.images.length;
  document.getElementById('images').innerHTML = data.images.slice(0, 100).map(function (img) {
    return '<li><a href="' + escapeHtml(img.src) + '" target="_blank" rel="noopener">' + escapeHtml(img.alt || img.src) + '</a></li>';
  }).join('') || '<li>No images found.</li>';
  document.getElementById('jsonOut').textContent = JSON.stringify(data, null, 2);
}
function stat(num, label) {
  return '<div class="stat"><b>' + num + '</b>' + label + '</div>';
}
function downloadJson() {
  if (!lastData) return;
  const blob = new Blob([JSON.stringify(lastData, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'scraped_data.json';
  a.click();
  URL.revokeObjectURL(a.href);
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, function (ch) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
  });
}
document.getElementById('url').addEventListener('keydown', function (e) {
  if (e.key === 'Enter') scrape();
});
</script>
</body>
</html>
"""


# ------------------------------------------------------------------
# 3. FLASK BACKEND
# ------------------------------------------------------------------

app = Flask(__name__)
CORS(app)


@app.route("/")
def home():
    """Serve the HTML + JS frontend (from the string above)."""
    return render_template_string(HTML_PAGE)


@app.route("/health")
def health():
    """Health check for Render — returns 200 when the app is alive."""
    return jsonify({"status": "ok"}), 200


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    """Scrape the URL sent by the frontend and return all info as JSON."""
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()

    if not url:
        return jsonify({"error": "Please provide a URL."}), 400

    try:
        data = scrape_url(url)
    except Exception as exc:  # network error, 404, timeout, bad HTML, ...
        return jsonify({"error": "Could not scrape this page: " + str(exc)}), 500

    return jsonify(data)


if __name__ == "__main__":
    # Local run only. On Render, Gunicorn starts the app instead
    # (see Procfile), so this block never runs there.
    # Render sets PORT itself — locally it falls back to 5000.
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
