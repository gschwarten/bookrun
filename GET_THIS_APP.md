# Get Your Own Library Book Finder

A personalized app that recommends books from your Goodreads to-read list, then checks if they're available at your local library. Takes about 15 minutes to set up.

---

## What You'll Need

- A **Goodreads account** with books on your "Want to Read" shelf
- An **Anthropic API key** (for AI-powered recommendations) — [get one here](https://console.anthropic.com/)
- A free **Render** account for hosting — [sign up here](https://render.com/)

---

## Step 1: Make Your Goodreads Profile Public

The app reads your bookshelves via Goodreads' public RSS feed. Your shelves need to be visible.

1. Go to [goodreads.com](https://www.goodreads.com) and log in
2. Click your profile picture (top right) → **Settings**
3. Scroll down to **Privacy** (or go to Settings → Privacy)
4. Make sure these are set:
   - **Who can view my profile**: `anyone`
   - **Who can see my bookshelves**: `anyone`
5. Save changes

### Find Your Goodreads User ID

1. Go to your Goodreads profile page
2. Look at the URL — it will be something like:
   `https://www.goodreads.com/user/show/12345678-your-name`
3. The number (`12345678`) is your **User ID** — save this for later

### Verify It Works

Open this URL in your browser (replace the number with your User ID):

```
https://www.goodreads.com/review/list_rss/12345678?shelf=to-read
```

You should see XML with your book titles. If you see an empty page or error, your profile isn't public yet.

---

## Step 2: Find Your Library

The app searches your local library's catalog. It works with any library that uses **BiblioCommons** (most major US city libraries).

### Check if your library uses BiblioCommons

Try going to: `https://YOUR_LIBRARY.bibliocommons.com`

Common examples:
| Library | BiblioCommons URL |
|---------|-------------------|
| San Francisco (SFPL) | `sfpl.bibliocommons.com` |
| New York Public Library | `nypl.bibliocommons.com` |
| Brooklyn Public Library | `bpl.bibliocommons.com` |
| Chicago Public Library | `chipublib.bibliocommons.com` |
| Seattle Public Library | `seattle.bibliocommons.com` |
| Boston Public Library | `bpl.bibliocommons.com` |
| Toronto Public Library | `torontopubliclibrary.bibliocommons.com` |

If your library uses BiblioCommons, note the subdomain (the part before `.bibliocommons.com`).

### Pick Your Branch (Optional)

If you have a preferred branch, note its exact name as it appears on the library website (e.g., "Park" for SFPL Park Branch). The app will flag when books are available at your specific branch.

---

## Step 3: Choose Your Book Format Preference

The app can filter results to show only the formats you care about. Options:

- **Print books only** (default) — standard paperback/hardcover
- **Include large print** — if you prefer large print editions
- **Include eBooks** — show Libby/Hoopla availability too
- **All formats** — show everything

You'll set this in the configuration.

---

## Step 4: Deploy the App

### Option A: Deploy to Render (Recommended — Free)

1. **Fork the repository**
   - Go to the GitHub repo and click **Fork**

2. **Customize for your library**
   - Open `app.py` and find these lines near the top:
     ```python
     SFPL_SEARCH_URL = "https://sfpl.bibliocommons.com/v2/search"
     SFPL_ITEM_URL = "https://sfpl.bibliocommons.com"
     ```
   - Replace `sfpl` with your library's BiblioCommons subdomain
   - Update the branch name in the search function if you have a preferred branch (search for `"park"` and replace with your branch name)

3. **Update the page title**
   - In `templates/index.html`, change "SFPL Park Branch" to your library/branch name

4. **Deploy on Render**
   - Go to [render.com](https://render.com) → **New** → **Web Service**
   - Connect your forked GitHub repo
   - Render will auto-detect the settings from `render.yaml`
   - Add environment variables:
     - `ANTHROPIC_API_KEY` = your Anthropic API key
     - `GOODREADS_USER_ID` = your Goodreads user ID number

5. **Bookmark on your phone**
   - Open the Render URL on your phone's browser
   - Add to Home Screen for easy access

### Option B: Run Locally

```bash
# Clone the repo
git clone <repo-url> library-finder
cd library-finder

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API key and Goodreads user ID

# Run
flask run --host=0.0.0.0 --port=5001
```

Open `http://localhost:5001` in your browser.

---

## Step 5: Use the App

1. Open the app on your phone
2. It fetches your Goodreads to-read list and uses AI to recommend the top 10 based on books you've loved
3. Reorder the list by dragging books (or use the arrow buttons)
4. Tap **"Check Library"** to see what's available
5. Results show in two tabs:
   - **Available Now** — go grab these off the shelf
   - **Not Available** — tap "Place Hold" to reserve through your library's website

Your list is saved between visits, so you can tweak it anytime.

---

## Troubleshooting

**"Could not fetch your Goodreads to-read shelf"**
- Make sure your profile is public (Step 1)
- Verify your User ID is correct

**No AI recommendations (just shows first 10 books)**
- Check that your `ANTHROPIC_API_KEY` is set correctly
- Make sure you have books rated 4-5 stars on your "Read" shelf (the AI uses these to personalize recommendations)

**Library search returns no results**
- Verify your library uses BiblioCommons
- Check that you updated the URL in `app.py` correctly

**Books show as "Not Available" but you know they're at your branch**
- The app filters for standard print books in English by default
- The search relies on catalog data which may not be perfectly up-to-date

---

## Credits

Built with Flask, the Anthropic Claude API, and Goodreads RSS.

Made with ❤️ by [Geoff](https://geoff.lovable.app)
