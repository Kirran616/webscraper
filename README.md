# Web Scraper Tool

Paste a link, get all the information from that page — title, meta tags,
headings, paragraphs, links, images, tables, lists, forms, emails and
phone numbers — as JSON, in the browser or from the command line.

Languages used: **Python** (scraper + backend), **HTML** and **JavaScript** (frontend).

## Files

| File | What it does |
| --- | --- |
| `scraper.py` | The Python scraper. Fetches a page with `requests`, parses it with BeautifulSoup, extracts everything. |
| `app.py` | Flask backend. Serves `index.html` and exposes `POST /api/scrape`. |
| `index.html` | The frontend. URL input, Scrape button, results, Download JSON. |
| `requirements.txt` | Python packages to install. |
| `README.md` | This file. |

## How to run

```bash
# 1. Go into the folder
cd webscraper-tool

# 2. Install the Python packages (once)
pip install -r requirements.txt

# 3a. Use it in the browser (recommended)
python app.py
# then open http://127.0.0.1:5000
# paste a link, click "Scrape this page"

# 3b. Or use it from the command line only
python scraper.py https://example.com
python scraper.py https://example.com --output result.json
python scraper.py https://example.com --output result.json --csv
```

The command-line version saves the full result to `scraped_data.json`
(and, with `--csv`, links + images to `scraped_data.csv`).

## What it extracts

- Page URL, status code, title, word count
- Meta: description, keywords, author, Open Graph, Twitter card, all meta tags
- Headings H1–H6, paragraphs
- Links: all, internal and external, with link text
- Images: full URL + alt text
- Lists, tables, forms (action, method, inputs)
- Scripts and stylesheets
- Emails and phone numbers found in the page text
- Counts for links, images, paragraphs, tables and forms

## Important — use it responsibly

Only scrape public pages you are allowed to scrape. Check the site's
Terms of Service and `robots.txt` first, do not log in to scrape private
data, and do not hammer a site with many requests in a short time.
This tool is for learning and for extracting public information with
permission.

## Limits

- Pages that load content with JavaScript (React, Angular, etc.) will
  return little or no text, because `requests` only gets the first HTML.
  For those sites, use Playwright or Selenium instead — replace the
  `requests.get()` call in `scraper.py` with a headless browser fetch,
  the rest of the extraction code stays the same.
- Some sites block scrapers (403 / CAPTCHA). A browser User-Agent is
  already set in `scraper.py`, but a blocked site may still need a
  different approach or permission.
