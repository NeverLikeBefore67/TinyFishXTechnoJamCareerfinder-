import requests
import time

print("Testing TinyFish Job Scraper...")
start = time.time()

r = requests.post('http://localhost:5000/api/search', json={
    'role': 'Frontend Developer',
    'location': 'Remote',
    'seniority': 'Entry',
    'portals': ['linkedin.com/jobs', 'indeed.com'],
    'force_refresh': True,
})

elapsed = time.time() - start
data = r.json()

print(f"\nDone in {elapsed:.1f}s")
print(f"Status: {r.status_code}")
print(f"Jobs found: {data.get('total', 0)}")
print(f"Endpoints used: {data.get('endpoints_used', [])}")
print(f"Errors: {data.get('errors', 'None')}")

for j in data.get('jobs', [])[:5]:
    title = j.get('title', 'N/A')[:65]
    source = j.get('source', '')
    score = j.get('relevance_score', 0)
    print(f"  [{score}%] {title}  ({source})")
