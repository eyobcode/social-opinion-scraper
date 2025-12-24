from platforms.universal_scraper import UniversalScraper
from core.utils import ScraperUtils
import json

def main():
    # x_scraper = UniversalScraper(platform='x', headless=False)
    # # results = x_scraper.run(max_posts=2, mode='blind')
    # # results = x_scraper.run(mode="single", single_href="https://x.com/elonmusk/status/2003579749176868875")
    # results = x_scraper.run(max_posts=2, mode='search', search_text="PM Abiy ahemed")
    #
    # ScraperUtils.save_json("x_results.json", results)
    # print(f"Scraped {len(results)} X posts. Saved to x_results.json")
    # # print(json.dumps(results, indent=4))
    insta = UniversalScraper(platform='instagram', headless=False)
    results = insta.run(max_posts=2, mode='blind')
    ScraperUtils.save_json("instagram_results.json", results)
    print(f"Scraped {len(results)} Instagram posts. Saved to instagram_results.json")
    # print(json.dumps(results, indent=4))

if __name__ == "__main__":
    main()
