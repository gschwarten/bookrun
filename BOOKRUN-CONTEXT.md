# BookRun — Development Context

## What It Is
A mobile-friendly web app for picking books at the SFPL Park Branch. It recommends books from your Goodreads to-read list using Claude AI, lets you reorder/favorite them, then checks real-time branch-level availability at SFPL.

Live at: **https://bookrun.onrender.com** (backend + standalone page)
Also embedded at: **https://geoff.lovable.app/bookrun** (Lovable frontend calling Render API)

## Architecture

```
Lovable (geoff.lovable.app/bookrun)     Render (bookrun.onrender.com)
  ┌─────────────────────┐                ┌─────────────────────┐
  │  Static frontend    │  ── API ──►    │  Flask backend      │
  │  (HTML/CSS/JS)      │                │                     │
  │  Calls Render APIs  │                │  /api/recommendations│
  └─────────────────────┘                │  /api/check-book     │
                                         │  /api/save-list      │
                                         │  /api/branches       │
                                         └─────────────────────┘
                                                │
                              ┌─────────────────┼─────────────────┐
                              ▼                 ▼                 ▼
                         Goodreads RSS    Claude API        SFPL BiblioCommons
                         (to-read +       (Haiku 4.5)       (HTML search +
                          read shelves)   ranks top 25       JSON availability API)
```

## Tech Stack
- **Backend**: Python/Flask, hosted on Render free tier
- **Frontend**: Vanilla HTML/CSS/JS (two copies: Flask template + Lovable page)
- **AI**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) for book recommendations
- **Data**: Goodreads RSS feeds, SFPL BiblioCommons catalog
- **Repo**: github.com/gschwarten/bookrun

## Key Files

```
~/library-finder/
├── app.py                      # Flask backend — all routes and logic
├── templates/index.html        # Standalone frontend (served by Render)
├── lovable-bookrun-page.html   # Frontend copy for Lovable (calls Render API)
├── requirements.txt            # flask, flask-cors, anthropic, requests, bs4, gunicorn, python-dotenv
├── render.yaml                 # Render deployment config
├── saved_list.json             # Persisted user book list (gitignored)
├── .env                        # API keys (gitignored)
├── .env.example                # Template for env vars
├── GET_THIS_APP.md             # Setup guide for other users
└── lovable-og-feedback.md      # Product feedback for Lovable re: OG meta tags
```

## Environment Variables
- `ANTHROPIC_API_KEY` — Claude API key
- `GOODREADS_USER_ID` — Default: 219870 (Geoff's)
- `PREFERRED_BRANCH` — Default: "PARK BRANCH"

## Features Implemented
1. **Goodreads integration** — Fetches to-read and read shelves via RSS (with User-Agent headers and xhtml namespace workaround)
2. **AI recommendations** — Claude ranks top 25 books based on reading history, remaining to-read books appended up to 100
3. **Drag-to-reorder** — Live reshuffling with CSS transitions, auto-scrolls when dragging near viewport edges
4. **Up/down arrows** — Simple one-position moves
5. **Tap rank to reposition** — Tap the rank number, type new position, book jumps there
6. **Keep/favorite (♥)** — Green left border, persists across re-rolls
7. **Animated remove (×)** — Fades out and removes from list
8. **Infinite scroll** — Shows 10 at a time, loads more on scroll
9. **Branch selector** — Dropdown defaults to Park Branch, updates CTA button text
10. **Library availability check** — Checks books one at a time via `/api/check-book` with progress ("Checking 3 of 10: Title...")
11. **Tabbed results** — "At [Branch]" tab vs "Not Available" tab
12. **Branch-level availability** — Uses BiblioCommons JSON API (`gateway.bibliocommons.com/v2/libraries/sfpl/bibs/{bib_id}/availability`)
13. **Place Hold links** — Direct link to SFPL book page
14. **List persistence** — Auto-saves to `saved_list.json` with 500ms debounce
15. **Re-roll** — Refreshes recommendations, preserves ♥ kept books at top
16. **CORS** — Allows requests from geoff.lovable.app and Lovable preview domains
17. **OG meta tags** — On Render-served page for proper link previews
18. **Color scheme** — Background #accae5, text #040949, cards #ffffff

## Key Technical Details

### Goodreads RSS
- URL: `goodreads.com/review/list_rss/{user_id}?shelf={shelf}&page={page}`
- Requires browser User-Agent header or returns anti-bot HTML
- Has `<xhtml:meta>` tag with undeclared namespace — stripped with regex before XML parsing
- Paginates 3 pages per shelf

### SFPL Search (2-step process)
1. **HTML search**: `sfpl.bibliocommons.com/v2/search?query={title}+{author}&searchType=smart` → scrape bib ID from result links (format: `S93C3536620`)
2. **JSON API**: `gateway.bibliocommons.com/v2/libraries/sfpl/bibs/{bib_id}/availability` → per-branch, per-item availability data
- Branch names in API are uppercase: "PARK BRANCH", "MARINA BRANCH", "MAIN"
- 0.5s delay between book checks to be respectful to SFPL servers

### Two Frontend Copies
- `templates/index.html` — Served by Flask on Render, uses relative API paths (`/api/...`)
- `lovable-bookrun-page.html` — For Lovable site, uses absolute API paths (`https://bookrun.onrender.com/api/...`), all IDs prefixed with `br-`, JS wrapped in IIFE, CSS scoped under `.bookrun`
- **Must be kept in sync** when making changes

## Known Issues / Future Improvements
- **"PARK BRANCH" not yet verified** in actual API responses — may need adjustment if BiblioCommons uses a different string
- **Render free tier cold starts** — 30-60 sec on first load after 15 min idle. Workaround: UptimeRobot pinging `/api/branches` every 5 min (not yet set up)
- **Lovable OG meta tags don't work** — SPA doesn't serve per-route meta tags server-side. Feedback written in `lovable-og-feedback.md`. Share the Render URL instead for proper link previews.
- **Infinite scroll visibility check** has a minor logic bug (double-checking `style.display`)
- **Two frontend copies to maintain** — changes need to be made in both `templates/index.html` and `lovable-bookrun-page.html`
- Drag-to-reorder improvements from latest session need to be synced to Lovable version via prompt

## Deployment
- **Render**: Auto-deploys on push to `main` branch on GitHub
- **Lovable**: Manual — paste updated code into Lovable editor or use Lovable prompts
- GitHub repo: `gschwarten/bookrun`
- GitHub CLI (`gh`) is installed and authenticated as `gschwarten`

## Bugs Fixed Along the Way
1. Port 5000 conflict with macOS AirPlay → switched to 5001
2. Goodreads anti-bot response → added User-Agent headers
3. XML namespace parse error → regex strip `<xhtml:meta>` tags
4. API key placeholder not caught → added `startswith("your-")` check + try/except
5. Drag-to-reorder "wonky" → rewrote with live reshuffling and absolute positioning
6. Batch library check timeout (~60s) → switched to one-book-at-a-time with progress
7. CORS blocking Lovable → added flask-cors with allowed origins
