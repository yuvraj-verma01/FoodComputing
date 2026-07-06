import os, requests, time

token = os.environ.get("MC_API_TOKEN", "").strip(" \"'")
url = "https://search.mediacloud.org/api/search/story-list"
headers = {"Authorization": f"Token {token}", "Accept": "application/json"}

# Test with a simple query first to see if the API responds at all
payload = {
    "q": "milk adulteration",
    "platform": "onlinenews-mediacloud",
    "start": "2024-01-01",
    "end": "2026-06-29",
    "page_size": 10,
    "cs": "34412118,38379954",
}
print("Sending request...")
start = time.time()
r = requests.get(url, params=payload, headers=headers, timeout=60)
elapsed = time.time() - start
print(f"STATUS: {r.status_code} (took {elapsed:.1f}s)")
print("RESPONSE:", r.text[:1000])
