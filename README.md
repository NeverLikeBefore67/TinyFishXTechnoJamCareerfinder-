# TinyFish Jobs

A small Flask app for searching job boards with TinyFish. Choose a role, location, seniority, keywords, and sources; review ranked results and open the original posting to apply.

## Features

- Searches LinkedIn, Indeed, Glassdoor, Wellfound, Naukri, and Internshala.
- Filters results by source and job type.
- Combines TinyFish Search, Fetch, and Agent results, then deduplicates and scores listings.
- Caches results locally for six hours to avoid repeating the same search.
- Links back to the original job posting.

## Run locally

Requires Python 3.9 or newer and a TinyFish API key.

1. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

2. Create `.env` from the example and add your key:

   ```powershell
   Copy-Item .env.example .env
   ```

   Set `TINYFISH_API_KEY` in `.env`. Keep this file private; it is excluded by `.gitignore`.

3. Start the app:

   ```powershell
   python app.py
   ```

4. Open [http://localhost:5000](http://localhost:5000).

Search requests use TinyFish and may count against your account's usage limits. The first run may take longer while results are collected; repeat searches can use the local cache.

## Search API

`POST /api/search` accepts JSON with a required `role` and optional `location`, `seniority`, `keywords`, `portals`, `company_urls`, and `force_refresh` fields. The response includes ranked `jobs`, the total, endpoints used, and any errors.

Other endpoints:

- `GET /api/health` — check that the app is running.
- `POST /api/cache/clear` — clear cached search results.

## Configuration and files

- `.env` — local TinyFish API key; never commit it.
- `.env.example` — safe environment-variable template.
- `config.py` — default portals, sample career pages, and cache duration.
- `static/index.html` — responsive interface and browser-side search controls.
- `jobs_cache.json` — local search cache; excluded from Git.

## Project layout

```text
app.py
cache_manager.py
config.py
job_processor.py
tinyfish_client.py
requirements.txt
static/index.html
```
