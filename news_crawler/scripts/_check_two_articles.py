import sys, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from crawler.config import Config
from crawler.downloader import Downloader
from crawler.extractor import Extractor

URLS = [
    "https://www.thehindu.com/news/cities/Hyderabad/pest-infested-flour-decayed-vegetables-meat-waste-found-at-hyderabads-lulu-hypermarket-during-food-safety-inspection/article70996619.ece",
    "https://www.thehindu.com/news/cities/Hyderabad/food-safety-raids-at-hyderabad-bakery-brewery-uncover-expired-food-pest-infestation-hygiene-violations/article71003523.ece",
]
cfg = Config(ROOT / "config/config_edible_oils_round3.yaml")
cfg.raw.setdefault("crawl", {}).update({
    "respect_robots_txt": False, "use_playwright": True,
    "playwright_first": True, "timeout_seconds": 45,
})
d = Downloader(cfg); e = Extractor(cfg)
oil_re = re.compile(r"\boil\b|\boils\b", re.I)
for url in URLS:
    print("=" * 90)
    print(url)
    res = d.download(url)
    if res.get("status") != "success":
        print("  STATUS:", res.get("status")); continue
    ext = e.extract(url, res.get("raw_html", ""))
    text = ext.get("article_text", "") or ""
    print("  words:", ext.get("word_count"))
    print("  --- FULL TEXT ---")
    print(text)
    print("  --- SENTENCES MENTIONING 'oil' ---")
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if oil_re.search(sent):
            print("   >", sent.strip())
d.close()