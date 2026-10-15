"""
TinyFish Client — Uses the official TinyFish Python SDK.

Endpoint Usage:
1. client.search.query()  — Discovers job listing URLs across portals and career pages.
2. client.fetch.get_contents() — Extracts clean, structured content from discovered job page URLs.
3. client.agent.run()     — Handles dynamic career pages that need interaction (filters, pagination).
"""

import json
import re
import hashlib
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from tinyfish import TinyFish


class TinyFishClient:
    """Unified client using the official TinyFish Python SDK."""

    def __init__(self, api_key=None):
        """
        Initialize the TinyFish SDK client.
        Reads TINYFISH_API_KEY from environment if api_key is not provided.
        """
        if api_key:
            self.client = TinyFish(api_key=api_key)
        else:
            # SDK auto-reads TINYFISH_API_KEY from environment
            self.client = TinyFish()

    # ──────────────────────────────────────────────────
    # ENDPOINT 1: SEARCH API  (client.search.query)
    # Discovers job listings across the web.
    # ──────────────────────────────────────────────────
    def search_jobs(self, role, location="", seniority="", portals=None, extra_keywords=""):
        """
        Use TinyFish Search API to discover job listing URLs.

        Args:
            role: Job role/title to search for (e.g., "Software Engineer")
            location: Preferred location (e.g., "Bangalore", "Remote")
            seniority: Level filter (e.g., "Intern", "Entry", "Mid", "Senior")
            portals: List of domain strings to search within
            extra_keywords: Additional search terms

        Returns:
            List of search result dicts with title, url, snippet
        """
        all_results = []

        # Build search queries targeting different portals
        site_filters = portals or [
            "linkedin.com/jobs", "indeed.com", "glassdoor.com",
            "wellfound.com", "naukri.com", "internshala.com"
        ]

        # Build the base query string
        query_parts = [role]
        if seniority:
            query_parts.append(seniority)
        if location:
            query_parts.append(location)
        if extra_keywords:
            query_parts.append(extra_keywords)
        base_query = " ".join(query_parts)

        # Search across each portal using site: filter
        for portal in site_filters:
            query = f"{base_query} site:{portal}"
            try:
                response = self.client.search.query(
                    query=query,
                )
                for item in response.results:
                    all_results.append({
                        "title": item.title,
                        "url": item.url,
                        "snippet": item.snippet,
                        "source_portal": portal,
                    })
            except Exception as e:
                print(f"[SEARCH] Error searching {portal}: {e}")
                continue

        # Also do a general search without site: filter for broader coverage
        try:
            general_query = f"{base_query} jobs hiring apply"
            response = self.client.search.query(
                query=general_query,
            )
            for item in response.results:
                all_results.append({
                    "title": item.title,
                    "url": item.url,
                    "snippet": item.snippet,
                    "source_portal": "web",
                })
        except Exception as e:
            print(f"[SEARCH] Error in general search: {e}")

        return all_results

    # ──────────────────────────────────────────────────
    # ENDPOINT 2: FETCH API  (client.fetch.get_contents)
    # Extracts clean content from job page URLs.
    # ──────────────────────────────────────────────────
    def fetch_job_pages(self, urls, purpose=""):
        """
        Use TinyFish Fetch API to extract clean content from job listing URLs.

        Args:
            urls: List of URLs to fetch (max 10 per request)
            purpose: Context for content extraction

        Returns:
            List of fetched page content dicts
        """
        all_fetched = []

        # Process in batches of 10 (API limit)
        for i in range(0, len(urls), 10):
            batch = urls[i:i+10]
            try:
                result = self.client.fetch.get_contents(
                    urls=batch,
                )
                for page in result.results:
                    all_fetched.append({
                        "url": page.url,
                        "title": page.title,
                        "content": page.text,
                        "links": getattr(page, "links", []),
                    })
                # Log any errors
                for error in result.errors:
                    print(f"[FETCH] Failed to fetch {error.url}: {error.error}")
            except Exception as e:
                print(f"[FETCH] Error fetching batch {i//10 + 1}: {e}")
                continue

        return all_fetched

    # ──────────────────────────────────────────────────
    # ENDPOINT 3: AGENT API  (client.agent.run)
    # Handles dynamic/interactive career pages.
    # ──────────────────────────────────────────────────
    def agent_scrape_careers(self, url, role, location="", seniority=""):
        """
        Use TinyFish Agent API for dynamic career pages that need
        interaction (filtering, searching, clicking).

        Args:
            url: Career page URL to automate
            role: Job role to search for
            location: Location preference
            seniority: Seniority level

        Returns:
            Structured JSON result from agent
        """
        goal = (
            f"On this careers page, search for '{role}' positions"
            f"{' in ' + location if location else ''}"
            f"{' at ' + seniority + ' level' if seniority else ''}. "
            f"Extract all matching job listings as a JSON array where each object has: "
            f"'title' (job title), 'company' (company name), 'location' (job location), "
            f"'type' (full-time/part-time/intern/contract), 'posted_date' (when posted), "
            f"'apply_url' (direct link to apply), and 'description' (brief job description). "
            f"If there's a search bar, type the role. If there are filters, apply relevant ones. "
            f"Return up to 15 listings."
        )

        output_schema = {
            "type": "object",
            "properties": {
                "jobs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "company": {"type": "string"},
                            "location": {"type": "string"},
                            "type": {"type": "string"},
                            "posted_date": {"type": "string"},
                            "apply_url": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["title"],
                    },
                }
            },
            "required": ["jobs"],
        }

        try:
            response = self.client.agent.run(
                url=url,
                goal=goal,
                output_schema=output_schema,
            )
            # Extract the jobs array from the result
            result = response.result
            if isinstance(result, dict) and "jobs" in result:
                return result["jobs"]
            return result
        except Exception as e:
            print(f"[AGENT] Error scraping {url}: {e}")
            return None

    # ──────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────
    @staticmethod
    def _map_country_code(location):
        """Map location string to country code for TinyFish Search."""
        location_lower = (location or "").lower()
        mapping = {
            "india": "IN", "bangalore": "IN", "bengaluru": "IN",
            "mumbai": "IN", "delhi": "IN", "hyderabad": "IN",
            "pune": "IN", "chennai": "IN", "noida": "IN",
            "gurgaon": "IN", "gurugram": "IN", "kolkata": "IN",
            "us": "US", "usa": "US", "united states": "US",
            "new york": "US", "san francisco": "US", "seattle": "US",
            "uk": "GB", "london": "GB", "remote": "US",
            "canada": "CA", "toronto": "CA",
            "germany": "DE", "berlin": "DE",
            "singapore": "SG",
        }
        for key, code in mapping.items():
            if key in location_lower:
                return code
        return "IN"  # Default to India for this bounty

    @staticmethod
    def generate_job_id(title, company, url):
        """Generate a unique ID for deduplication."""
        raw = f"{title}|{company}|{url}".lower().strip()
        return hashlib.md5(raw.encode()).hexdigest()[:12]
