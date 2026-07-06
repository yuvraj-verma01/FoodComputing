"""Repair corrupted filtered_results.json and remove off-topic articles."""
import json

PATH = r"c:\Users\Writika\milk_pipeline\data\round_1_filtered\filtered_results.json"

with open(PATH, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

# The corruption: replacement tool mangled the IIT Madras title line and injected
# a stray JSON block mid-string. Find and fix the specific garbled region.
BAD = (
    'tle": "IIT M  {\n'
    '    "url": "https://timesofindia.indiatimes.com/city/jaipur/cid-cb-investigation-spurious-milk-case-kaithun-chaksu-jaipur/articleshow/105430331.cms",\n'
    '    "title": "CID-CB Investigation: Spurious Milk Case at Kaithun near Chaksu, Jaipur",\n'
    '    "text": "",\n'
    '    "publish_date": "2023-11-23"\n'
    '  }\n'
    ']ish_date": "2023-07-30"'
)
GOOD = (
    'tle": "IIT Madras develops pocket-friendly device to detect milk adulteration",\n'
    '    "text": "",\n'
    '    "publish_date": "2023-03-28"'
)

if BAD in content:
    content = content.replace(BAD, GOOD)
    print("Corruption found and repaired.")
else:
    print("WARNING: Expected corruption pattern not found. Inspect manually.")

with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

# Validate
try:
    articles = json.load(open(PATH, encoding="utf-8"))
    print(f"JSON valid. Articles: {len(articles)}")
except json.JSONDecodeError as e:
    print(f"Still invalid: {e}")
    import sys; sys.exit(1)

# Now remove the 5 off-topic articles by URL
REMOVE_URLS = {
    # Milk production (not adulteration) - title was just "Karur"
    "https://www.thehindu.com/news/cities/Tiruchirapalli/steps-being-taken-to-increase-milk-production-says-minister-mano-thangaraj/article67139129.ece",
    # Breast milk bank donation
    "https://timesofindia.indiatimes.com/city/kochi/two-donate-milk-to-gh-breast-milk-bank/articleshow/103725786.cms",
    # Govt adopting pregnant women (completely unrelated)
    "https://www.hindustantimes.com/india-news/govt-officials-in-uttara-kannada-adopt-pregnant-women-101698174704031.html",
    # Buttermilk & infant mortality (nutrition, not adulteration)
    "https://www.hindustantimes.com/cities/pune-news/taste-of-life-pune-doctor-s-struggle-to-justify-buttermilk-feed-to-reduce-risk-of-infant-mortality-101700684207547.html",
    # Toddy in milk packets (alcohol fraud, not milk adulteration)
    "https://www.siasat.com/toddy-sold-in-milk-packets-270-litres-seized-from-medchal-hotel-3247412/",
}

before = len(articles)
articles = [a for a in articles if a.get("url") not in REMOVE_URLS]
after = len(articles)
print(f"Removed {before - after} off-topic articles. Remaining: {after}")

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(articles, f, indent=2, ensure_ascii=False)

print("Done.")
