"""
Web Scraper Tool — Python backend (Flask)
===========================================
Runs the HTML/JS frontend and exposes one API endpoint:

    POST /api/scrape   {"url": "https://example.com"}
    -> returns the JSON produced by scraper.py

Run it:
    pip install -r requirements.txt
    python app.py
    # then open http://127.0.0.1:5000 in your browser
"""

import os

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from scraper import scrape_url

app = Flask(__name__)
CORS(app)  # allow the frontend JS to call the API

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route("/")
def home():
    """Serve the HTML + JS frontend."""
    return send_from_directory(BASE_DIR, "index.html")


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
        return jsonify({"error": f"Could not scrape this page: {exc}"}), 500

    return jsonify(data)


if __name__ == "__main__":
    # debug=True reloads the server when you edit the code.
    # Turn it off when you deploy the tool.
    app.run(host="127.0.0.1", port=5000, debug=True)
