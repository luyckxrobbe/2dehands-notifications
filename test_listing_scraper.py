#!/usr/bin/env python3
"""
Test script for the listing scraper.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the current directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent))

from listing_scraper import ListingScraper


async def test_listing_scraper():
    """Test the listing scraper with a sample URL."""
    
    # Test URL from the provided HTML file
    test_url = "https://www.2dehands.be/v/fietsen-en-brommers/fietsen-racefietsen/m2308511301-specialized-tarmac-sl6-s-works-54cm"
    
    print(f"Testing listing scraper with URL: {test_url}")
    print("=" * 80)
    
    try:
        async with ListingScraper(headless=False) as scraper:
            print("Scraping listing...")
            result = await scraper.scrape_listing(test_url)
            
            print("\nScraped data:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # Test the is_today function
            print("\n" + "=" * 80)
            print("Testing date parsing:")
            date_posted = result.get('date_posted')
            if date_posted:
                is_today = scraper.is_today(date_posted)
                print(f"Date posted: {date_posted}")
                print(f"Is from today: {is_today}")
            else:
                print("No date found in the listing")
            
            # Show key information
            print("\n" + "=" * 80)
            print("Key Information:")
            print(f"Title: {result.get('title', 'N/A')}")
            print(f"Price: {result.get('price', {}).get('display', 'N/A')}")
            print(f"Location: {result.get('location', {}).get('city', 'N/A')}")
            print(f"Seller: {result.get('seller', {}).get('name', 'N/A')}")
            print(f"Specifications: {len(result.get('specifications', {}))} items")
            print(f"Images: {len(result.get('images', []))} images")
            
    except Exception as e:
        print(f"Error testing listing scraper: {e}")
        import traceback
        traceback.print_exc()


async def test_multiple_listings():
    """Test with multiple listing URLs."""
    
    # You can add more test URLs here
    test_urls = [
        "https://www.2dehands.be/v/fietsen-en-brommers/fietsen-racefietsen/m2308511301-specialized-tarmac-sl6-s-works-54cm",
        # Add more URLs here for testing
    ]
    
    print(f"Testing {len(test_urls)} listings...")
    print("=" * 80)
    
    async with ListingScraper(headless=True) as scraper:
        for i, url in enumerate(test_urls, 1):
            print(f"\nTesting listing {i}/{len(test_urls)}: {url}")
            try:
                result = await scraper.scrape_listing(url)
                
                # Show summary
                print(f"✓ Title: {result.get('title', 'N/A')}")
                print(f"✓ Price: {result.get('price', {}).get('display', 'N/A')}")
                print(f"✓ Date: {result.get('date_posted', 'N/A')}")
                print(f"✓ Is today: {scraper.is_today(result.get('date_posted'))}")
                
            except Exception as e:
                print(f"✗ Error: {e}")


if __name__ == "__main__":
    print("Listing Scraper Test")
    print("=" * 80)
    
    # Test single listing
    asyncio.run(test_listing_scraper())
    
    print("\n" + "=" * 80)
    print("Testing multiple listings...")
    
    # Test multiple listings
    asyncio.run(test_multiple_listings())
