"""
Web Scraper Tool — Python (requests + BeautifulSoup)
====================================================
Give it a link, it extracts all the useful information from that page:
title, meta tags, headings, paragraphs, links, images, tables,
lists, forms, emails, phone numbers, scripts and stylesheets.

Usage (command line):
    pip install -r requirements.txt
    python scraper.py https://example.com
    python scraper.py https://example.com --output result.json
    python scraper.py https://example.com --output result.json --csv

Usage (from other Python code):
    from scraper import scrape_url
    data = scrape_url("https://example.com")
    print(data["title"])

Notes:
- Only scrape public pages you are allowed to scrape.
  Check the site's Terms of Service and robots.txt first.
- Pages that load their content with JavaScript (React, etc.)
  will return little or no text here — use Playwright/Selenium
  for those. See README.md.
"""

import argparse
import csv
import json
import re
import sys
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# A real browser User-Agent, so sites do not block the request
# as an unknown bot.
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
    if not link:
        return ""
    return urljoin(base_url, link.strip())


def scrape_url(url):
    """Fetch a URL and return all extracted information as a dict."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    parsed = urlparse(url)

    # --- Meta / head information -------------------------------------
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
    # All meta tags, in case you need a specific one later
    all_meta = [
        {k: v for k, v in tag.attrs.items()}
        for tag in soup.find_all("meta")
    ]

    # --- Headings ------------------------------------------------------
    headings = {}
    for level in range(1, 7):
        tag_name = f"h{level}"
        headings[tag_name] = [_text(h) for h in soup.find_all(tag_name)]

    # --- Main text -----------------------------------------------------
    paragraphs = [_text(p) for p in soup.find_all("p") if _text(p)]
    full_text = soup.get_text(" ", strip=True)
    word_count = len(full_text.split())

    # --- Links ---------------------------------------------------------
    links = []
    for a in soup.find_all("a", href=True):
        href = _absolute(url, a["href"])
        links.append({"text": _text(a), "href": href})
    internal_links = [l for l in links if urlparse(l["href"]).netloc == parsed.netloc]
    external_links = [l for l in links if urlparse(l["href"]).netloc and urlparse(l["href"]).netloc != parsed.netloc]

    # --- Images --------------------------------------------------------
    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        images.append({
            "src": _absolute(url, src),
            "alt": img.get("alt", ""),
        })

    # --- Lists ---------------------------------------------------------
    lists = []
    for ul in soup.find_all(["ul", "ol"]):
        items = [_text(li) for li in ul.find_all("li", recursive=False)]
        if items:
            lists.append({"type": ul.name, "items": items})

    # --- Tables --------------------------------------------------------
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [_text(c) for c in tr.find_all(["th", "td"])]
            if cells:
                rows.append(cells)
        if rows:
            tables.append({"rows": rows})

    # --- Forms ---------------------------------------------------------
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

    # --- Scripts / stylesheets ----------------------------------------
    scripts = [_absolute(url, s.get("src")) for s in soup.find_all("script", src=True)]
    stylesheets = [
        _absolute(url, link.get("href"))
        for link in soup.find_all("link", rel="stylesheet")
    ]

    # --- Contact details found in the page text -----------------------
    emails = sorted(set(EMAIL_RE.findall(full_text)))
    phones = sorted(set(p.strip() for p in PHONE_RE.findall(full_text)))

    return {
        "url": url,
        "status_code": response.status_code,
        "title": title,
        "meta": meta,
        "all_meta": all_meta,
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


def save_csv(data, csv_path):
    """Save links + images to a CSV file (one row per link/image)."""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["type", "text_or_alt", "url"])
        for link in data["links"]:
            writer.writerow(["link", link["text"], link["href"]])
        for img in data["images"]:
            writer.writerow(["image", img["alt"], img["src"]])


def main():
    parser = argparse.ArgumentParser(description="Extract all information from a web page.")
    parser.add_argument("url", help="The page link to scrape, e.g. https://example.com")
    parser.add_argument("--output", "-o", default="scraped_data.json",
                        help="JSON file to save the result to (default: scraped_data.json)")
    parser.add_argument("--csv", action="store_true",
                        help="Also save links + images to scraped_data.csv")
    args = parser.parse_args()

    try:
        data = scrape_url(args.url)
    except requests.RequestException as exc:
        print(f"Error fetching {args.url}: {exc}", file=sys.stderr)
        sys.exit(1)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    if args.csv:
        save_csv(data, "scraped_data.csv")

    print(f"Title: {data['title']}")
    print(f"Status: {data['status_code']} | Words: {data['word_count']}")
    print(f"Links: {data['counts']['links']} | Images: {data['counts']['images']} | Tables: {data['counts']['tables']}")
    print(f"Saved to: {args.output}")


if __name__ == "__main__":
    main()
