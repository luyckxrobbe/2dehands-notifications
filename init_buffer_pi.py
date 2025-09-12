#!/usr/bin/env python3
"""
Raspberry Pi optimized buffer initialization.
"""

import asyncio
import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Any

from scrape_2dehands_pi import scrape_bikes_pi
from current_listings import CurrentListings
from centralized_logging import setup_logging, get_logger

# Configure logging
setup_logging()
logger = get_logger(__name__)


async def init_buffer_pi(config_file: str, max_pages: int = None, max_bikes: int = None):
    """
    Pi-optimized buffer initialization by scraping fewer pages.
    
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
    request_delay = config.get('request_delay', 2.0)  # Default 2s for Pi
    
    logger.info(f"🚴‍♂️ Pi-optimized buffer initialization for: {url}")
    logger.info(f"📄 Scraping first {pages_to_scrape} pages (Pi optimized)...")
    logger.info(f"🔢 Target buffer size: {target_bikes} bikes")
    if proxies:
        logger.info(f"🌐 Using {len(proxies)} proxies")
    logger.info("")
    
    # Scrape multiple pages with Pi optimization
    listings = await scrape_bikes_pi(
        url, 
        max_pages=pages_to_scrape,
        proxies=proxies if proxies else None,
        request_delay=request_delay
    )
    
    logger.info(f"✅ Scraped {len(listings)} total listings")
    
    # Limit to target_bikes if we got more
    if len(listings) > target_bikes:
        logger.info(f"📝 Limiting to {target_bikes} most recent bikes")
        # Sort by scraped_at and take the most recent ones
        listings.bikes.sort(key=lambda b: b._scraped_at, reverse=True)
        listings.bikes = listings.bikes[:target_bikes]
    
    logger.info(f"🎯 Buffer initialized with {len(listings)} bikes")
    
    # Save to backup file if specified
    if backup_file and backup_file.strip():
        backup_path = Path(backup_file)
        # Create directory if it doesn't exist
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        listings.to_json_file(backup_path)
        logger.info(f"💾 Saved buffer to: {backup_path}")
    else:
        logger.warning("⚠️  No backup file specified - buffer will not be saved")
    
    # Show some stats
    stats = listings.get_stats()
    logger.info("")
    logger.info("📊 Buffer Statistics:")
    logger.info(f"   Total bikes: {stats['total_bikes']}")
    logger.info(f"   Bikes with price: {stats['bikes_with_price']}")
    logger.info(f"   Average price: €{stats['average_price']}")
    logger.info(f"   Price range: €{stats['min_price']} - €{stats['max_price']}")
    
    if stats['brands']:
        logger.info("   Top brands:")
        for brand, count in sorted(stats['brands'].items(), key=lambda x: x[1], reverse=True)[:5]:
            logger.info(f"     {brand}: {count}")
    
    logger.info("")
    logger.info("✅ Pi-optimized buffer initialization complete!")
    logger.info("You can now start monitoring with:")
    logger.info(f"python run_monitors.py {config_file}")


def main():
    """Main function for Pi-optimized buffer initialization."""
    parser = argparse.ArgumentParser(description="Pi-optimized buffer initialization")
    parser.add_argument("config", type=str, help="Path to JSON configuration file")
    parser.add_argument("--pages", type=int, help="Number of pages to scrape (overrides config)")
    parser.add_argument("--max-bikes", type=int, help="Maximum bikes in buffer (overrides config)")
    args = parser.parse_args()
    
    if not Path(args.config).exists():
        logger.error(f"Error: Config file not found: {args.config}")
        return
    
    asyncio.run(init_buffer_pi(args.config, args.pages, args.max_bikes))


if __name__ == "__main__":
    main()
