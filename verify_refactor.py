from src.services.page_scraper import PageScraper
from src.infrastructure.csv_storage import CSVStorage
import pprint

def verify():
    url = "https://pep-pedia.org/peptides/bioglutide"
    print(f"[INFO] Verifying refactor with URL: {url}")
    
    scraper = PageScraper()
    results, error = scraper.scrape(url)
    
    if error:
        print(f"[ERROR] Scraping failed: {error}")
        return
    
    print(f"[INFO] Scraped {len(results)} peptide entries.")
    for p_data in results:
        print(f"\n--- Peptide: {p_data.name} ({p_data.method}) ---")
        print(f"Full Name: {p_data.full_name}")
        print(f"Hero Facts: {len(p_data.hero.facts)}")
        print(f"Quick Guide Keys: {list(p_data.quick_guide.keys())}")
        print(f"Sections: {len(p_data.sections)}")
        print(f"Graph Data: {len(p_data.graph_data)}")
        if p_data.graph_data:
            for time_range, data in p_data.graph_data.items():
                print(f"  {time_range}: Peak={data.peak}, Half-life={data.half_life}, Cleared={data.cleared}, Points={len(data.points)}")
    
    # Test storage
    print("\n[INFO] Testing storage...")
    storage = CSVStorage()
    storage.save(results)
    print("[INFO] Verification complete.")

if __name__ == "__main__":
    verify()
