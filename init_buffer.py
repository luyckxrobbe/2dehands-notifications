#!/usr/bin/env python3
"""
Initialize the bike monitor buffer by scraping the first few pages.
"""

import asyncio
import argparse
import json
from pathlib import Path
from typing import Dict, Any

from scrape_2dehands_live import scrape_bikes
from current_listings import CurrentListings


async def init_buffer(config_file: str, max_pages: int = None, max_bikes: int = None):
    """
    Initialize the buffer by scraping multiple pages.
    
    Args:
        config_file: Path to the JSON configuration file
        max_pages: Number of pages to scrape for initialization (overrides config if provided)
        max_bikes: Maximum number of bikes to keep in buffer (overrides config if provided)
    """
    # Load configuration
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    url = config['url']
    backup_file = config['backup_file']
    
    # Use config values unless explicitly overridden by command line arguments
    pages_to_scrape = max_pages if max_pages is not None else config['initial_pages']
    target_bikes = max_bikes if max_bikes is not None else config['max_bikes']
    
    # Get proxy configuration
    proxies = config.get('proxies', [])
    request_delay = config.get('request_delay', 1.0)
    
    print(f"🚴‍♂️ Initializing buffer for: {url}")
    print(f"📄 Scraping first {pages_to_scrape} pages...")
    print(f"🔢 Target buffer size: {target_bikes} bikes")
    if proxies:
        print(f"🌐 Using {len(proxies)} proxies")
    print()
    
    # Scrape multiple pages
    listings = await scrape_bikes(
        url, 
        headless=True, 
        max_pages=pages_to_scrape,
        proxies=proxies if proxies else None,
        request_delay=request_delay
    )
    
    print(f"✅ Scraped {len(listings)} total listings")
    
    # Limit to target_bikes if we got more
    if len(listings) > target_bikes:
        print(f"📝 Limiting to {target_bikes} most recent bikes")
        # Sort by scraped_at and take the most recent ones
        listings.bikes.sort(key=lambda b: b._scraped_at, reverse=True)
        listings.bikes = listings.bikes[:target_bikes]
    
    print(f"🎯 Buffer initialized with {len(listings)} bikes")
    
    # Save to backup file if specified
    if backup_file and backup_file.strip():
        backup_path = Path(backup_file)
        # Create directory if it doesn't exist
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        listings.to_json_file(backup_path)
        print(f"💾 Saved buffer to: {backup_path}")
    else:
        print("⚠️  No backup file specified - buffer will not be saved")
    
    # Show some stats
    stats = listings.get_stats()
    print()
    print("📊 Buffer Statistics:")
    print(f"   Total bikes: {stats['total_bikes']}")
    print(f"   Bikes with price: {stats['bikes_with_price']}")
    print(f"   Average price: €{stats['average_price']}")
    print(f"   Price range: €{stats['min_price']} - €{stats['max_price']}")
    
    if stats['brands']:
        print("   Top brands:")
        for brand, count in sorted(stats['brands'].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"     {brand}: {count}")
    
    print()
    print("✅ Buffer initialization complete!")
    print("You can now start monitoring with:")
    print(f"python bike_monitor.py {config_file}")


def main():
    """
    Main function to initialize buffer.
    """
    parser = argparse.ArgumentParser(description="Initialize bike monitor buffer")
    parser.add_argument("config", type=str, help="Path to JSON configuration file")
    parser.add_argument("--pages", type=int, help="Number of pages to scrape (overrides config)")
    parser.add_argument("--max-bikes", type=int, help="Maximum bikes in buffer (overrides config)")
    args = parser.parse_args()
    
    if not Path(args.config).exists():
        print(f"Error: Config file not found: {args.config}")
        return
    
    asyncio.run(init_buffer(args.config, args.pages, args.max_bikes))


if __name__ == "__main__":
    main()
