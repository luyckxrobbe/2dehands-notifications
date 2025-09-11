#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from bike import Bike
from current_listings import CurrentListings
from web_navigator import WebNavigator
from centralized_logging import setup_logging, get_logger

# Configure logging
setup_logging()
logger = get_logger(__name__)


LISTING_SELECTOR = "li.hz-Listing.hz-Listing--list-item"


async def extract_listing_from_li(page, li, navigator) -> Dict[str, Any]:
    import time
    start_time = time.time()
    
    # Skip promotional listings with long data-tracking attributes
    a = li.locator("a.hz-Listing-coverLink").first
    data_tracking = await a.get_attribute("data-tracking")
    if data_tracking and len(data_tracking) > 200:  # Promotional listings have very long tracking strings
        logger.debug(f"Skipped promotional listing (data-tracking length: {len(data_tracking)})")
        return None

    title = await li.locator("h3.hz-Listing-title").text_content()
    title = title.strip() if title else None

    price_el = li.locator("span.hz-Listing-price--desktop, p.hz-Listing-price--mobile").first
    price = await price_el.text_content()
    price = price.strip() if price else None

    href = await a.get_attribute("href")

    # As a last resort, click to navigate, capture URL, then go back
    navigated_url = None
    if not href:
        try:
            # First, ensure consent banner is handled and dismissed
            await navigator.handle_2dehands_consent_banner(page)
            await navigator.handle_cookie_banner(page)
            await navigator.wait_for_consent_banner_dismissed(page)
            
            prev_url = page.url
            
            # Try to click with force to bypass any remaining consent banner
            try:
                await a.click(force=True, timeout=5000)
            except Exception:
                # Try regular click as fallback
                try:
                    await a.click(timeout=5000)
                except Exception:
                    # Skip this listing if we can't click
                    return None
            
            # Wait for SPA route change with shorter timeout
            await asyncio.wait_for(
                page.wait_for_function("url => window.location.href !== url", arg=prev_url, timeout=3000),
                timeout=5.0
            )
            navigated_url = page.url
            # Immediately go back to the listing page - no need to wait for page load
            await page.go_back()
            # Just wait for the URL to change back, no need to wait for full page load
            await asyncio.wait_for(
                page.wait_for_function("url => window.location.href === arguments[0]", arg=prev_url, timeout=5000),
                timeout=7.0
            )
        except Exception:
            pass

    seller_el = li.locator(".hz-Listing--sellerInfo .hz-Listing-seller-name").first
    seller = await seller_el.text_content()
    seller = seller.strip() if seller else None

    location_el = li.locator(".hz-Listing--sellerInfo .hz-Listing-location .hz-Listing-distance-label").first
    location = await location_el.text_content()
    location = location.strip() if location else None

    date_el = li.locator(".hz-Listing-group--price-date-feature .hz-Listing-date, .hz-Listing-group--price-date-feature--tablet .hz-Listing-date").first
    date_label = await date_el.text_content()
    date_label = date_label.strip() if date_label else None

    attr_els = li.locator(".hz-Listing-attributes .hz-Attribute, .hz-Listing-extended-attributes .hz-Attribute")
    attributes = []
    try:
        count = await attr_els.count()
    except Exception:
        count = 0
    for idx in range(count):
        t = await attr_els.nth(idx).text_content()
        if t:
            attributes.append(t.strip())

    # Try extended description first, then fall back to short description
    desc_el = li.locator("p.hz-Listing-description--extended").first
    description = await desc_el.text_content()
    if not description:
        desc_el = li.locator("p.hz-Listing-description.hz-text-paragraph").first
        description = await desc_el.text_content()
    description = description.strip() if description else None

    img_el = li.locator(".hz-Listing-image-item--main img").first
    image = await img_el.get_attribute("src")
    if not image:
        image = await img_el.get_attribute("data-src")

    final_href = href or navigated_url
    if final_href and final_href.startswith("/"):
        # Detect domain from current page URL
        current_url = page.url
        if current_url and "marktplaats.nl" in current_url:
            base_url = "https://www.marktplaats.nl"
        else:
            base_url = "https://www.2dehands.be"
        final_href = f"{base_url}{final_href}"
    
    total_time = time.time() - start_time
    logger.debug(f"Listing extraction took {total_time:.3f}s for: {title[:50] if title else 'No title'}...")
    
    return {
        "title": title,
        "price": price,
        "href": final_href,
        "seller": seller,
        "location": location,
        "date": date_label,
        "attributes": attributes,
        "description": description,
        "image": image,
    }


async def scrape_page(navigator: WebNavigator, url: str) -> List[Dict[str, Any]]:
    import time
    start_time = time.time()
    logger.debug(f"Starting to scrape page: {url}")
    
    page = await navigator.new_page()
    page_start = time.time()
    logger.debug(f"Created new page in {page_start - start_time:.2f}s")
    
    try:
        # Navigate to the page with faster loading strategy for pagination
        # For pagination pages, use domcontentloaded instead of networkidle for faster loading
        wait_until = "domcontentloaded" if "/p/" in url else "networkidle"
        nav_start = time.time()
        success = await navigator.navigate_to(page, url, wait_until=wait_until)
        nav_end = time.time()
        logger.debug(f"Navigation took {nav_end - nav_start:.2f}s")
        
        if not success:
            logger.debug("Navigation failed, returning empty results")
            return []
        
        # Handle consent banner first
        consent_start = time.time()
        await navigator.handle_2dehands_consent_banner(page)
        consent_end = time.time()
        logger.debug(f"Consent banner handling took {consent_end - consent_start:.2f}s")
        
        # Handle cookie banner
        cookie_start = time.time()
        await navigator.handle_cookie_banner(page)
        cookie_end = time.time()
        logger.debug(f"Cookie banner handling took {cookie_end - cookie_start:.2f}s")
        
        # Wait for listings to load
        selector_start = time.time()
        selector_found = await navigator.wait_for_selector_with_timeout(page, LISTING_SELECTOR, timeout=20000)
        await asyncio.sleep(1)  # Additional wait for dynamic content
        selector_end = time.time()
        logger.debug(f"Selector wait took {selector_end - selector_start:.2f}s")

        li_nodes = page.locator(LISTING_SELECTOR)
        total = await li_nodes.count()
        logger.debug(f"Found {total} listing elements on page")
        results: List[Dict[str, Any]] = []

        extraction_start = time.time()
        for i in range(total):
            li = li_nodes.nth(i)
            try:
                item = await extract_listing_from_li(page, li, navigator)
                # Skip if None (promotional listing) or if no core content exists
                if item and (item.get("title") or item.get("price") or item.get("href")):
                    results.append(item)
            except Exception:
                # Continue with next listing if something goes wrong for this one
                continue
        
        extraction_end = time.time()
        logger.debug(f"Extracted {len(results)} listings in {extraction_end - extraction_start:.2f}s")
        
        total_time = time.time() - start_time
        logger.debug(f"Total page scrape time: {total_time:.2f}s for {len(results)} listings")

        return results
        
    finally:
        await page.close()
        logger.debug("Page closed")


def get_page_url(base_url: str, page_num: int) -> str:
    """
    Convert a base URL to a specific page URL.
    
    Args:
        base_url: Base URL (e.g., https://www.2dehands.be/l/fietsen-en-brommers/fietsen-racefietsen/)
        page_num: Page number (1-based)
        
    Returns:
        URL for the specific page
    """
    if page_num == 1:
        return base_url
    
    # Handle 2dehands/marktplaats pagination pattern: /p/2, /p/3, etc.
    if '/p/' in base_url:
        # URL already has page parameter, replace it
        import re
        return re.sub(r'/p/\d+', f'/p/{page_num}', base_url)
    else:
        # Add page parameter in the path before the fragment (#)
        if '#' in base_url:
            # Split at the fragment
            base_part, fragment = base_url.split('#', 1)
            # Remove trailing slash if present to avoid double slashes
            base_part = base_part.rstrip('/')
            return f"{base_part}/p/{page_num}/#{fragment}"
        else:
            # No fragment, just add /p/2/
            base_url = base_url.rstrip('/')
            return f"{base_url}/p/{page_num}/"


async def scrape_bikes(
    url: str, 
    headless: bool = True, 
    max_pages: int = 1,
    proxies: Optional[List[str]] = None,
    request_delay: float = 1.0
) -> CurrentListings:
    """
    Scrape bike listings and return as CurrentListings object.
    
    Args:
        url: URL to scrape
        headless: Whether to run browser in headless mode
        max_pages: Maximum number of pages to scrape (default: 1)
        proxies: Optional list of proxy URLs to use
        request_delay: Delay between requests in seconds
        
    Returns:
        CurrentListings object with scraped bikes
    """
    import time
    total_start = time.time()
    logger.debug(f"Starting scrape_bikes: {max_pages} pages, headless={headless}")
    
    all_listings = []
    
    # Create WebNavigator with proxy support
    navigator_start = time.time()
    navigator = WebNavigator(
        headless=headless,
        proxies=proxies,
        request_delay=request_delay
    )
    navigator_end = time.time()
    logger.debug(f"Created WebNavigator in {navigator_end - navigator_start:.2f}s")
    
    async with navigator:
        for page_num in range(1, max_pages + 1):
            try:
                page_start = time.time()
                page_url = get_page_url(url, page_num)
                logger.debug(f"Scraping page {page_num}: {page_url}")
                
                listings_data = await scrape_page(navigator, page_url)
                
                # If we got no listings and this is not the first page, the page probably doesn't exist
                if len(listings_data) == 0 and page_num > 1:
                    logger.debug(f"No listings on page {page_num}, stopping")
                    break
                
                all_listings.extend(listings_data)
                page_end = time.time()
                logger.info(f"Found {len(listings_data)} listings on page {page_num} (took {page_end - page_start:.2f}s)")
                
                # Delay between pages (handled by WebNavigator)
                if page_num < max_pages:
                    delay_start = time.time()
                    await asyncio.sleep(2)  # Additional delay between pages
                    delay_end = time.time()
                    logger.debug(f"Page delay took {delay_end - delay_start:.2f}s")
                    
            except Exception as e:
                logger.error(f"Error scraping page {page_num}: {e}")
                break

    # Convert to Bike objects and return CurrentListings
    conversion_start = time.time()
    result = CurrentListings.from_list(all_listings)
    conversion_end = time.time()
    logger.debug(f"Converted to CurrentListings in {conversion_end - conversion_start:.2f}s")
    
    total_time = time.time() - total_start
    logger.debug(f"Total scrape_bikes time: {total_time:.2f}s for {len(all_listings)} listings across {max_pages} pages")
    
    return result


async def run(url: str, output: Path, headless: bool = True, compare_file: Path = None):
    """
    Legacy function for backward compatibility.
    Scrapes bikes and optionally saves to JSON file.
    """
    current_listings = await scrape_bikes(url, headless)
    
    # Save current listings if output file specified
    if output:
        current_listings.to_json_file(output)
        logger.info(f"Wrote {len(current_listings)} listings to {output}")
    
    # Compare with previous listings if provided
    if compare_file and compare_file.exists():
        previous_listings = CurrentListings.from_json_file(compare_file)
        comparison = current_listings.compare_with(previous_listings)
        
        logger.info(f"\n=== COMPARISON RESULTS ===")
        logger.info(f"New listings: {len(comparison['new'])}")
        logger.info(f"Removed listings: {len(comparison['removed'])}")
        logger.info(f"Updated listings: {len(comparison['updated'])}")
        
        if comparison['new']:
            logger.info(f"\n=== NEW LISTINGS ===")
            for bike in comparison['new']:
                logger.info(f"🆕 {bike.title} - {bike.price} - {bike.location}")
                logger.info(f"   {bike.href}")
        
        if comparison['removed']:
            logger.info(f"\n=== REMOVED LISTINGS ===")
            for bike in comparison['removed']:
                logger.info(f"❌ {bike.title} - {bike.price} - {bike.location}")
        
        if comparison['updated']:
            logger.info(f"\n=== UPDATED LISTINGS ===")
            for bike in comparison['updated']:
                logger.info(f"🔄 {bike.title} - {bike.price} - {bike.location}")
    
    return current_listings


def main():
    parser = argparse.ArgumentParser(description="Live scrape 2dehands/marktplaats listing page and output JSON")
    parser.add_argument("url", type=str, help="Target listings page URL (2dehands.be or marktplaats.nl)")
    parser.add_argument("-o", "--output", type=str, default="listings_live.json", help="Output JSON file path")
    parser.add_argument("-c", "--compare", type=str, help="Previous listings file to compare against")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode")
    args = parser.parse_args()

    compare_file = Path(args.compare) if args.compare else None
    asyncio.run(run(args.url, Path(args.output), headless=not args.headed, compare_file=compare_file))


if __name__ == "__main__":
    main()
