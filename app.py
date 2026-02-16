import json
import os
import re
import time
import xml.etree.ElementTree as ET

import anthropic
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app, origins=[
    "https://geoff.lovable.app",
    r"https://.*\.lovableproject\.com",
    r"https://.*\.lovable\.dev",
    r"https://.*\.lovable\.app",
])

GOODREADS_USER_ID = os.environ.get("GOODREADS_USER_ID", "219870")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CACHE_TTL = 3600  # 1 hour
SAVED_LIST_PATH = os.path.join(os.path.dirname(__file__), "saved_list.json")

# Simple in-memory cache
_cache = {"recommendations": None, "timestamp": 0}


def load_saved_list():
    """Load the user's saved book list from disk."""
    try:
        with open(SAVED_LIST_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_list(books):
    """Save the user's book list to disk."""
    with open(SAVED_LIST_PATH, "w") as f:
        json.dump(books, f, indent=2)

# ---------------------------------------------------------------------------
# Goodreads RSS helpers
# ---------------------------------------------------------------------------

GOODREADS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml",
}


def fetch_goodreads_shelf(shelf, pages=3):
    """Fetch books from a Goodreads RSS shelf. Returns list of dicts."""
    books = []
    for page in range(1, pages + 1):
        url = (
            f"https://www.goodreads.com/review/list_rss/{GOODREADS_USER_ID}"
            f"?shelf={shelf}&page={page}"
        )
        try:
            resp = requests.get(url, headers=GOODREADS_HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException:
            break

        # Strip undeclared xhtml namespace tag that breaks ElementTree
        content = re.sub(r"<xhtml:meta[^/]*/>", "", resp.text)
        root = ET.fromstring(content)
        items = root.findall(".//item")
        if not items:
            break

        for item in items:
            title = item.findtext("title", "").strip()
            author = item.findtext("author_name", "").strip()
            rating = item.findtext("user_rating", "0").strip()
            avg_rating = item.findtext("average_rating", "0").strip()
            image = item.findtext("book_image_url", "").strip()
            book_id = item.findtext("book_id", "").strip()

            if title:
                books.append({
                    "title": title,
                    "author": author,
                    "user_rating": int(rating) if rating else 0,
                    "avg_rating": float(avg_rating) if avg_rating else 0.0,
                    "image": image,
                    "book_id": book_id,
                })

    return books


def get_to_read_books():
    return fetch_goodreads_shelf("to-read", pages=3)


def get_top_rated_books():
    """Get books the user rated highly (4-5 stars) from their read shelf."""
    books = fetch_goodreads_shelf("read", pages=3)
    return [b for b in books if b["user_rating"] >= 4]


# ---------------------------------------------------------------------------
# Claude API recommendation
# ---------------------------------------------------------------------------

def get_recommendations(to_read, top_rated):
    """Ask Claude to rank the top books from the to-read list.

    Returns AI-ranked top 25 with reasons, plus remaining to-read books
    appended after (up to 100 total).
    """
    to_read_map = {b["title"].lower(): b for b in to_read}

    def _enrich(rec):
        key = rec.get("title", "").lower()
        if key in to_read_map:
            rec["image"] = to_read_map[key].get("image", "")
            rec["avg_rating"] = to_read_map[key].get("avg_rating", 0)
        else:
            rec.setdefault("image", "")
            rec.setdefault("avg_rating", 0)
        return rec

    def _fallback(books):
        return [
            _enrich({
                "title": b["title"],
                "author": b["author"],
                "reason": "",
                "image": b.get("image", ""),
                "avg_rating": b.get("avg_rating", 0),
            })
            for b in books[:100]
        ]

    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.startswith("your-"):
        return _fallback(to_read)

    loved = "\n".join(
        f"- {b['title']} by {b['author']} ({b['user_rating']} stars)"
        for b in top_rated[:30]
    )
    want = "\n".join(
        f"- {b['title']} by {b['author']}"
        for b in to_read[:100]
    )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "I'm heading to the library and want to pick up some books. "
                        "Based on books I've loved (rated 4-5 stars), recommend and rank "
                        "the top 25 I should read next from my to-read list.\n\n"
                        f"## Books I loved\n{loved}\n\n"
                        f"## My to-read list\n{want}\n\n"
                        "Return ONLY a JSON array of 25 objects with keys: "
                        '"title", "author", "reason" (one short sentence why I\'d like it). '
                        "No markdown fences, just the JSON array."
                    ),
                }
            ],
        )

        text = message.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        recs = json.loads(text)
    except Exception:
        return _fallback(to_read)

    # Enrich AI picks with images/ratings
    for rec in recs:
        _enrich(rec)

    # Append remaining to-read books not already in AI picks
    ranked_titles = {r.get("title", "").lower() for r in recs}
    for b in to_read:
        if len(recs) >= 100:
            break
        if b["title"].lower() not in ranked_titles:
            recs.append(_enrich({
                "title": b["title"],
                "author": b["author"],
                "reason": "",
                "image": b.get("image", ""),
                "avg_rating": b.get("avg_rating", 0),
            }))

    return recs[:100]


# ---------------------------------------------------------------------------
# SFPL BiblioCommons search
# ---------------------------------------------------------------------------

SFPL_SEARCH_URL = "https://sfpl.bibliocommons.com/v2/search"
SFPL_ITEM_URL = "https://sfpl.bibliocommons.com"
SFPL_AVAIL_API = "https://gateway.bibliocommons.com/v2/libraries/sfpl/bibs"
PREFERRED_BRANCH = os.environ.get("PREFERRED_BRANCH", "PARK BRANCH")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
        "Mobile/15E148 Safari/604.1"
    )
}


def find_bib_id(title, author):
    """Search SFPL and return the BiblioCommons bib ID + URL for a book."""
    query = f"{title} {author}"
    params = {"query": query, "searchType": "smart"}

    try:
        resp = requests.get(
            SFPL_SEARCH_URL, params=params, headers=BROWSER_HEADERS, timeout=15
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None, ""

    soup = BeautifulSoup(resp.text, "html.parser")
    item = soup.select_one(".cp-search-result-item")
    if not item:
        return None, ""

    # Get the item URL which contains the bib ID (e.g. /v2/record/S93C3536620)
    url = ""
    bib_id = None
    title_link = item.select_one(".title-content a, .cp-title a, a.title")
    if title_link:
        href = title_link.get("href", "")
        if href.startswith("/"):
            url = SFPL_ITEM_URL + href
        elif href.startswith("http"):
            url = href
        # Extract bib ID from URL like /v2/record/S93C3536620
        match = re.search(r"/(S\d+C\d+)", href)
        if match:
            bib_id = match.group(1)

    return bib_id, url


def get_branch_availability(bib_id):
    """Use BiblioCommons JSON API to get per-branch availability."""
    try:
        resp = requests.get(
            f"{SFPL_AVAIL_API}/{bib_id}/availability",
            headers=BROWSER_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None, None, None

    # Overall availability info
    avail_info = list(data.get("entities", {}).get("availabilities", {}).values())
    overall = avail_info[0] if avail_info else {}

    total_copies = overall.get("totalCopies", 0)
    available_copies = overall.get("availableCopies", 0)
    held_copies = overall.get("heldCopies", 0)

    # Per-branch breakdown
    bib_items = data.get("entities", {}).get("bibItems", {})
    branches = []
    for item in bib_items.values():
        branch_name = item.get("branchName", "")
        item_status = item.get("availability", {}).get("status", "UNKNOWN")
        branches.append({
            "branch": branch_name,
            "status": item_status,
            "call_number": item.get("callNumber", ""),
        })

    summary = {
        "total_copies": total_copies,
        "available_copies": available_copies,
        "held_copies": held_copies,
    }

    return summary, branches, overall


def search_sfpl(title, author):
    """Search SFPL for a book with branch-level availability."""
    result = {
        "title": title,
        "author": author,
        "status": "unknown",
        "detail": "",
        "url": "",
        "holds": "",
        "park_branch": False,
        "branches_available": [],
    }

    # Step 1: Search to find the bib ID
    bib_id, url = find_bib_id(title, author)
    result["url"] = url

    if not bib_id:
        result["status"] = "not_found"
        result["detail"] = "No results found at SFPL"
        return result

    # Step 2: Get branch-level availability via JSON API
    summary, branches, overall = get_branch_availability(bib_id)

    if summary is None:
        result["status"] = "check_online"
        result["detail"] = "Could not check availability — try SFPL website"
        return result

    # Find which branches have it available
    available_branches = [
        b["branch"] for b in branches if b["status"] == "AVAILABLE"
    ]
    result["branches_available"] = available_branches

    # Check preferred branch
    preferred_available = PREFERRED_BRANCH.upper() in [
        b.upper() for b in available_branches
    ]
    result["park_branch"] = preferred_available

    if summary["available_copies"] > 0:
        result["status"] = "available"
        if preferred_available:
            other_count = len(available_branches) - 1
            if other_count > 0:
                result["detail"] = (
                    f"At {PREFERRED_BRANCH.title()} + {other_count} other branch{'es' if other_count > 1 else ''}"
                )
            else:
                result["detail"] = f"At {PREFERRED_BRANCH.title()}"
        else:
            branch_list = ", ".join(b.title() for b in available_branches[:3])
            if len(available_branches) > 3:
                branch_list += f" + {len(available_branches) - 3} more"
            result["detail"] = f"Available at: {branch_list}"
    else:
        result["status"] = "in_use"
        held = summary["held_copies"]
        total = summary["total_copies"]
        if held > 0:
            result["holds"] = f"{held} holds on {total} copies"
            result["detail"] = f"All copies in use ({result['holds']})"
        else:
            result["detail"] = "All copies checked out"

    return result


SFPL_BRANCHES = [
    "ANZA BRANCH", "BAYVIEW BRANCH", "BERNAL HEIGHTS BRANCH",
    "CHINATOWN BRANCH", "EUREKA VALLEY BRANCH", "EXCELSIOR BRANCH",
    "GLEN PARK BRANCH", "GOLDEN GATE VALLEY BRANCH", "INGLESIDE BRANCH",
    "MAIN", "MARINA BRANCH", "MERCED BRANCH", "MISSION BRANCH",
    "MISSION BAY BRANCH", "NOE VALLEY BRANCH", "NORTH BEACH BRANCH",
    "OCEAN VIEW BRANCH", "ORTEGA BRANCH", "PARK BRANCH",
    "PARKSIDE BRANCH", "PORTOLA BRANCH", "POTRERO BRANCH",
    "PRESIDIO BRANCH", "RICHMOND BRANCH", "SUNSET BRANCH",
    "VISITACION VALLEY BRANCH", "WEST PORTAL BRANCH",
    "WESTERN ADDITION BRANCH",
]


def check_sfpl_books(books):
    """Check SFPL availability for a list of books. Returns all results."""
    results = []
    for book in books:
        info = search_sfpl(book["title"], book["author"])
        results.append(info)
        time.sleep(0.5)  # Be respectful to SFPL servers
    return results


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/recommendations")
def api_recommendations():
    """Fetch Goodreads shelves and get Claude recommendations."""
    refresh = request.args.get("refresh") == "1"

    # Return saved list if it exists (and not refreshing)
    if not refresh:
        saved = load_saved_list()
        if saved:
            return jsonify({"books": saved, "saved": True})

    # Return cached results if fresh
    if not refresh and _cache["recommendations"] and (time.time() - _cache["timestamp"] < CACHE_TTL):
        return jsonify(_cache["recommendations"])

    to_read = get_to_read_books()
    top_rated = get_top_rated_books()

    if not to_read:
        return jsonify({
            "error": "Could not fetch your Goodreads to-read shelf. "
                     "Make sure your profile is public.",
            "books": [],
        }), 200

    recs = get_recommendations(to_read, top_rated)
    result = {"books": recs, "to_read_count": len(to_read)}

    _cache["recommendations"] = result
    _cache["timestamp"] = time.time()

    return jsonify(result)


@app.route("/api/save-list", methods=["POST"])
def api_save_list():
    """Save the user's current book list order."""
    data = request.get_json()
    books = data.get("books", [])
    save_list(books)
    return jsonify({"ok": True})


@app.route("/api/branches")
def api_branches():
    """Return list of SFPL branches."""
    return jsonify({
        "branches": SFPL_BRANCHES,
        "default": PREFERRED_BRANCH,
    })


@app.route("/api/check-library", methods=["POST"])
def api_check_library():
    """Check SFPL availability for submitted book list."""
    data = request.get_json()
    books = data.get("books", [])

    if not books:
        return jsonify({"error": "No books provided"}), 400

    results = check_sfpl_books(books)
    return jsonify({"results": results})


@app.route("/api/check-book", methods=["POST"])
def api_check_book():
    """Check SFPL availability for a single book."""
    data = request.get_json()
    title = data.get("title", "")
    author = data.get("author", "")

    if not title:
        return jsonify({"error": "No title provided"}), 400

    result = search_sfpl(title, author)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
