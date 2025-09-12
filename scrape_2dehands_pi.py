#!/usr/bin/env python3
"""
Raspberry Pi optimized scraping functions for 2dehands/marktplaats.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from bike import Bike
from current_listings import CurrentListings
from web_navigator_pi import WebNavigatorPi
from centralized_logging import setup_logging, get_logger

# Configure logging
setup_logging()
logger = get_logger(__name__)

# Optimized selector for Pi
LISTING_SELECTOR = "li.hz-Listing.hz-Listing--list-item"


async def extract_listing_from_li_pi(page, li) -> Dict[str, Any]:
    """
    Pi-optimized listing extraction with minimal operations.
    """
    try:
        # Skip promotional listings quickly
        a = li.locator("a.hz-Listing-coverLink").first
        data_tracking = await a.get_attribute("data-tracking")
        if data_tracking and len(data_tracking) > 200:
            return None

        # Extract only essential fields for Pi
        title = await li.locator("h3.hz-Listing-title").text_content()
        title = title.strip() if title else None

        price_el = li.locator("span.hz-Listing-price--desktop, p.hz-Listing-price--mobile").first
        price = await price_el.text_content()
        price = price.strip() if price else None

        href = await a.get_attribute("href")
        if href and href.startswith("/"):
            # Detect domain from current page URL
            current_url = page.url
            if current_url and "marktplaats.nl" in current_url:
                base_url = "https://www.marktplaats.nl"
            else:
                base_url = "https://www.2dehands.be"
            href = f"{base_url}{href}"

        seller_el = li.locator(".hz-Listing--sellerInfo .hz-Listing-seller-name").first
        seller = await seller_el.text_content()
        seller = seller.strip() if seller else None

        location_el = li.locator(".hz-Listing--sellerInfo .hz-Listing-location .hz-Listing-distance-label").first
        location = await location_el.text_content()
        location = location.strip() if location else None

        date_el = li.locator(".hz-Listing-group--price-date-feature .hz-Listing-date, .hz-Listing-group--price-date-feature--tablet .hz-Listing-date").first
        date_label = await date_el.text_content()
        date_label = date_label.strip() if date_label else None

        # Skip attributes extraction for Pi (saves time)
        # Skip description extraction for Pi (saves time)
        # Skip image extraction for Pi (saves time)

        return {
            "title": title,
            "price": price,
            "href": href,
            "seller": seller,
            "location": location,
            "date": date_label,
            "attributes": [],  # Empty for Pi
            "description": None,  # Empty for Pi
            "image": None,  # Empty for Pi
        }

    except Exception as e:
        logger.debug(f"Error extracting listing: {e}")
        return None


async def scrape_page_pi(navigator: WebNavigatorPi, url: str) -> List[Dict[str, Any]]:
    """
    Pi-optimized page scraping with minimal resource usage.
    """
    logger.debug(f"Scraping page: {url}")
    
    page = await navigator.new_page()
    
    try:
        # Navigate with minimal wait
        success = await navigator.navigate_to(page, url, wait_until="domcontentloaded")
        if not success:
            return []

        # Handle banners quickly
        await navigator.handle_2dehands_consent_banner(page)
        await navigator.handle_cookie_banner(page)
        await navigator.wait_for_consent_banner_dismissed(page)
        
        # Wait for listings with short timeout
        selector_found = await navigator.wait_for_selector_with_timeout(page, LISTING_SELECTOR, timeout=5000)
        if not selector_found:
            logger.debug("No listings found on page")
            return []

        li_nodes = page.locator(LISTING_SELECTOR)
        total = await li_nodes.count()
        logger.debug(f"Found {total} listing elements on page")
        
        results = []
        
        # Process listings in smaller batches for Pi
        batch_size = 10
        for i in range(0, total, batch_size):
            batch_end = min(i + batch_size, total)
            
            for j in range(i, batch_end):
                li = li_nodes.nth(j)
                try:
                    item = await extract_listing_from_li_pi(page, li)
                    if item and (item.get("title") or item.get("price") or item.get("href")):
                        results.append(item)
                except Exception:
                    continue
            
            # Small delay between batches for Pi
            if batch_end < total:
                await asyncio.sleep(0.1)

        logger.debug(f"Extracted {len(results)} listings from page")
        return results
        
    except Exception as e:
        logger.error(f"Error scraping page {url}: {e}")
        return []
    finally:
        await page.close()


def get_page_url(base_url: str, page_num: int) -> str:
    """Get page URL (same as original)."""
    if page_num == 1:
        return base_url
    
    if '/p/' in base_url:
        import re
        return re.sub(r'/p/\d+', f'/p/{page_num}', base_url)
    else:
        if '#' in base_url:
            base_part, fragment = base_url.split('#', 1)
            base_part = base_part.rstrip('/')
            return f"{base_part}/p/{page_num}/#{fragment}"
        else:
            base_url = base_url.rstrip('/')
            return f"{base_url}/p/{page_num}/"


async def scrape_bikes_pi(
    url: str, 
    max_pages: int = 2,  # Reduced default for Pi
    proxies: Optional[List[str]] = None,
    request_delay: float = 2.0  # Increased delay for Pi
) -> CurrentListings:
    """
    Pi-optimized bike scraping with minimal resource usage.
    
    Args:
        url: URL to scrape
        max_pages: Maximum number of pages to scrape (reduced for Pi)
        proxies: Optional list of proxy URLs
        request_delay: Delay between requests in seconds
        
    Returns:
        CurrentListings object with scraped bikes
    """
    logger.info(f"Starting Pi-optimized scrape: {max_pages} pages")
    
    all_listings = []
    
    # Create Pi-optimized navigator
    navigator = WebNavigatorPi(
        headless=True,
        proxies=proxies,
        request_delay=request_delay,
        max_pages_per_session=5  # Restart browser every 5 pages
    )
    
    async with navigator:
        for page_num in range(1, max_pages + 1):
            try:
                page_url = get_page_url(url, page_num)
                logger.info(f"Scraping page {page_num}: {page_url}")
                
                listings_data = await scrape_page_pi(navigator, page_url)
                
                # Stop if no listings found (page doesn't exist)
                if len(listings_data) == 0 and page_num > 1:
                    logger.info(f"No listings on page {page_num}, stopping")
                    break
                
                all_listings.extend(listings_data)
                logger.info(f"Found {len(listings_data)} listings on page {page_num}")
                
                # Delay between pages (longer for Pi)
                if page_num < max_pages:
                    await asyncio.sleep(request_delay)
                    
            except Exception as e:
                logger.error(f"Error scraping page {page_num}: {e}")
                break

    # Convert to Bike objects and return CurrentListings
    result = CurrentListings.from_list(all_listings)
    logger.info(f"Pi-optimized scrape completed: {len(all_listings)} total listings")
    
    return result


async def main():
    """Test function for Pi-optimized scraping."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pi-optimized bike scraping")
    parser.add_argument("url", type=str, help="Target listings page URL")
    parser.add_argument("-p", "--pages", type=int, default=2, help="Number of pages to scrape")
    parser.add_argument("-o", "--output", type=str, default="listings_pi.json", help="Output JSON file")
    args = parser.parse_args()

    listings = await scrape_bikes_pi(args.url, max_pages=args.pages)
    
    # Save results
    output_path = Path(args.output)
    listings.to_json_file(output_path)
    logger.info(f"Saved {len(listings)} listings to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
