"""
TinyFish Job Scraper — Main Flask Application

A TinyFish-powered job and internship scraper that:
1. Uses TinyFish SEARCH to discover job listings across portals
2. Uses TinyFish FETCH to extract clean content from job pages
3. Uses TinyFish AGENT to navigate dynamic career pages
4. Filters, ranks, and deduplicates results
5. Caches results for freshness without redundant scraping
"""

import json
import hashlib
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from tinyfish_client import TinyFishClient
from job_processor import JobProcessor
from cache_manager import CacheManager
from config import COMPANY_CAREERS

app = Flask(__name__, static_folder="static")
CORS(app)

# Initialize components
cache = CacheManager()


@app.route("/")
def index():
    """Serve the frontend."""
    return send_from_directory("static", "index.html")


@app.route("/api/search", methods=["POST"])
def search_jobs():
    """
    Main search endpoint — orchestrates all 3 TinyFish APIs.

    Request body:
    {
        "role": "Software Engineer",
        "location": "Bangalore",
        "seniority": "Intern",       // Intern | Entry | Mid | Senior
        "keywords": "python react",  // optional extra keywords
        "portals": ["linkedin.com/jobs", "indeed.com"],  // optional
        "company_urls": ["https://careers.google.com/"],  // optional
        "force_refresh": false       // bypass cache
    }
    """
    data = request.get_json() or {}
    role = data.get("role", "").strip()
    location = data.get("location", "").strip()
    seniority = data.get("seniority", "").strip()
    keywords = data.get("keywords", "").strip()
    portals = data.get("portals", None)
    company_urls = data.get("company_urls", [])
    force_refresh = data.get("force_refresh", False)

    if not role:
        return jsonify({"error": "Role is required"}), 400

    # Check cache first
    cache_key = CacheManager.make_cache_key(role, location, seniority, keywords)
    if not force_refresh:
        cached_jobs, is_fresh = cache.get_cached_results(cache_key)
        if is_fresh and cached_jobs:
            return jsonify({
                "jobs": cached_jobs,
                "total": len(cached_jobs),
                "cached": True,
                "endpoints_used": ["cache"],
                "message": f"Showing {len(cached_jobs)} cached results. Click 'Refresh' for live data."
            })

    # Initialize per-request
    try:
        client = TinyFishClient()
    except ValueError as e:
        return jsonify({"error": str(e)}), 500

    processor = JobProcessor()
    all_jobs = []
    endpoints_used = []
    errors = []
    user_prefs = {
        "role": role,
        "location": location,
        "seniority": seniority,
        "keywords": keywords,
    }

    # ── STEP 1: TinyFish SEARCH API ──────────────────
    # Discover job listings across portals
    try:
        search_results = client.search_jobs(
            role=role,
            location=location,
            seniority=seniority,
            portals=portals,
            extra_keywords=keywords
        )
        search_jobs_processed = processor.process_search_results(search_results, user_prefs)
        all_jobs.extend(search_jobs_processed)
        endpoints_used.append("search")
    except Exception as e:
        errors.append(f"Search: {str(e)}")

    # ── STEP 2: TinyFish FETCH API ───────────────────
    # Fetch and extract details from top search result URLs
    try:
        # Get top URLs from search results that look like actual job listings
        urls_to_fetch = []
        for job in all_jobs[:15]:  # Top 15 results
            url = job.get("apply_url", "")
            if url and url.startswith("http"):
                urls_to_fetch.append(url)

        if urls_to_fetch:
            fetched = client.fetch_job_pages(
                urls=urls_to_fetch[:10],  # API limit
                purpose=f"Extract detailed job listing info for {role} positions"
            )
            fetch_jobs = processor.process_fetched_content(fetched, user_prefs)
            # Enrich existing jobs or add new ones
            all_jobs = _merge_jobs(all_jobs, fetch_jobs)
            endpoints_used.append("fetch")
    except Exception as e:
        errors.append(f"Fetch: {str(e)}")

    # ── STEP 3: TinyFish AGENT API ───────────────────
    # Scrape dynamic company career pages
    try:
        careers_to_scrape = company_urls if company_urls else [
            c["url"] for c in COMPANY_CAREERS[:1]  # Limit to 1 to keep response fast
        ]
        for career_url in careers_to_scrape:
            agent_result = client.agent_scrape_careers(
                url=career_url,
                role=role,
                location=location,
                seniority=seniority
            )
            if agent_result:
                agent_jobs = processor.process_agent_results(
                    agent_result, career_url, user_prefs
                )
                all_jobs.extend(agent_jobs)
        if careers_to_scrape:
            endpoints_used.append("agent")
    except Exception as e:
        errors.append(f"Agent: {str(e)}")

    # ── FINAL: Sort by relevance & deduplicate ───────
    all_jobs = _deduplicate(all_jobs)
    all_jobs.sort(key=lambda j: j.get("relevance_score", 0), reverse=True)

    # Cache the results
    cache.save_results(cache_key, all_jobs, user_prefs)

    return jsonify({
        "jobs": all_jobs,
        "total": len(all_jobs),
        "cached": False,
        "endpoints_used": endpoints_used,
        "errors": errors if errors else None,
        "message": f"Found {len(all_jobs)} listings using {', '.join(endpoints_used)} endpoints."
    })


@app.route("/api/cache/clear", methods=["POST"])
def clear_cache():
    """Clear the job results cache."""
    cache.clear_cache()
    return jsonify({"message": "Cache cleared successfully."})


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "TinyFish Job Scraper",
        "endpoints": ["search", "fetch", "agent"],
    })


def _deduplicate(jobs):
    """Remove duplicate jobs based on ID."""
    seen = set()
    unique = []
    for job in jobs:
        jid = job.get("id", "")
        if jid and jid not in seen:
            seen.add(jid)
            unique.append(job)
    return unique


def _merge_jobs(existing, new_jobs):
    """Merge new job data into existing list, enriching where possible."""
    existing_by_url = {j.get("apply_url", ""): j for j in existing}
    for nj in new_jobs:
        url = nj.get("apply_url", "")
        if url in existing_by_url:
            # Enrich existing entry with fetched data
            ej = existing_by_url[url]
            if not ej.get("company") and nj.get("company"):
                ej["company"] = nj["company"]
            if not ej.get("location") and nj.get("location"):
                ej["location"] = nj["location"]
            if len(nj.get("snippet", "")) > len(ej.get("snippet", "")):
                ej["snippet"] = nj["snippet"]
            ej["relevance_score"] = max(
                ej.get("relevance_score", 0),
                nj.get("relevance_score", 0)
            )
        else:
            existing.append(nj)
    return existing


if __name__ == "__main__":
    print("\n[TinyFish] Job Scraper starting...")
    print("   Open http://localhost:5000 in your browser\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
