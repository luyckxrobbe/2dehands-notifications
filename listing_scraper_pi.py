#!/usr/bin/env python3
"""
Pi-optimized scraper for individual 2dehands listing pages to extract detailed information.
Optimized for Raspberry Pi with reduced resource usage and longer timeouts.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page
from web_navigator_pi import WebNavigatorPi
from centralized_logging import setup_logging, get_logger

# Set up centralized logging
setup_logging()
logger = get_logger(__name__)


class ListingScraperPi:
    """Pi-optimized scraper for individual 2dehands listing pages."""
    
    def __init__(
        self, 
        headless: bool = True,
        proxies: Optional[List[str]] = None,
        request_delay: float = 2.0  # Pi-optimized: longer delay
    ):
        self.navigator = WebNavigatorPi(
            headless=headless,
            proxies=proxies,
            request_delay=request_delay
        )
    
    async def __aenter__(self):
        await self.navigator.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.navigator.close()
    
    async def scrape_listing(self, url: str) -> Dict[str, Any]:
        """
        Scrape detailed information from a 2dehands listing page.
        Pi-optimized with longer timeouts and reduced resource usage.
        
        Args:
            url: The URL of the listing page
            
        Returns:
            Dictionary containing detailed listing information
        """
        try:
            logger.debug(f"Scraping listing: {url}")
            
            # Create a new page and navigate to the listing page
            page = await self.navigator.new_page()
            if not page:
                logger.error(f"Failed to create new page for: {url}")
                return {}
            
            # Navigate to the listing page with Pi-optimized timeout
            success = await self.navigator.navigate_to(page, url, wait_until="domcontentloaded")
            if not success:
                logger.error(f"Failed to navigate to listing page: {url}")
                return {}
            
            # Wait for page to load with Pi-optimized delay
            await asyncio.sleep(1.5)  # Pi-optimized: longer wait
            
            # Extract all the detailed information
            result = {
                'url': url,
                'title': await self._extract_title(page),
                'price': await self._extract_price(page),
                'description': await self._extract_description(page),
                'seller': await self._extract_seller_info(page),
                'location': await self._extract_location(page),
                'date_posted': await self._extract_date_posted(page),
                'images': await self._extract_images(page),
                'attributes': await self._extract_attributes(page),
                'view_count': await self._extract_view_count(page),
                'listing_id': self._extract_listing_id(url),
                'scraped_at': datetime.now(timezone.utc).isoformat()
            }
            
            logger.debug(f"Successfully scraped listing: {result.get('title', 'Unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error scraping listing {url}: {e}")
            return {}
    
    async def _extract_title(self, page: Page) -> str:
        """Extract the listing title."""
        try:
            # Try multiple selectors for title
            title_selectors = [
                'h1[data-testid="ad-title"]',
                'h1',
                '.ad-title',
                '[data-testid="ad-title"]'
            ]
            
            for selector in title_selectors:
                title_element = await page.query_selector(selector)
                if title_element:
                    title = await title_element.text_content()
                    if title and title.strip():
                        return title.strip()
            
            return "Title not found"
        except Exception as e:
            logger.debug(f"Error extracting title: {e}")
            return "Title not found"
    
    async def _extract_price(self, page: Page) -> str:
        """Extract the listing price."""
        try:
            # Try multiple selectors for price
            price_selectors = [
                '[data-testid="price"]',
                '.price',
                '.ad-price',
                '[class*="price"]'
            ]
            
            for selector in price_selectors:
                price_element = await page.query_selector(selector)
                if price_element:
                    price = await price_element.text_content()
                    if price and price.strip():
                        return price.strip()
            
            return "Price not found"
        except Exception as e:
            logger.debug(f"Error extracting price: {e}")
            return "Price not found"
    
    async def _extract_description(self, page: Page) -> str:
        """Extract the listing description."""
        try:
            # Try multiple selectors for description
            desc_selectors = [
                '[data-testid="description"]',
                '.description',
                '.ad-description',
                '[class*="description"]'
            ]
            
            for selector in desc_selectors:
                desc_element = await page.query_selector(selector)
                if desc_element:
                    description = await desc_element.text_content()
                    if description and description.strip():
                        return description.strip()
            
            return "Description not found"
        except Exception as e:
            logger.debug(f"Error extracting description: {e}")
            return "Description not found"
    
    async def _extract_seller_info(self, page: Page) -> Dict[str, Any]:
        """Extract seller information."""
        try:
            seller_info = {}
            
            # Try to find seller name
            seller_name_selectors = [
                '[data-testid="seller-name"]',
                '.seller-name',
                '.ad-seller',
                '[class*="seller"]'
            ]
            
            for selector in seller_name_selectors:
                seller_element = await page.query_selector(selector)
                if seller_element:
                    name = await seller_element.text_content()
                    if name and name.strip():
                        seller_info['name'] = name.strip()
                        break
            
            # Try to find seller type (business/private)
            seller_type_selectors = [
                '[data-testid="seller-type"]',
                '.seller-type',
                '[class*="seller-type"]'
            ]
            
            for selector in seller_type_selectors:
                type_element = await page.query_selector(selector)
                if type_element:
                    seller_type = await type_element.text_content()
                    if seller_type and seller_type.strip():
                        seller_info['type'] = seller_type.strip()
                        break
            
            return seller_info if seller_info else {'name': 'Unknown', 'type': 'Unknown'}
            
        except Exception as e:
            logger.debug(f"Error extracting seller info: {e}")
            return {'name': 'Unknown', 'type': 'Unknown'}
    
    async def _extract_location(self, page: Page) -> str:
        """Extract the listing location."""
        try:
            # Try multiple selectors for location
            location_selectors = [
                '[data-testid="location"]',
                '.location',
                '.ad-location',
                '[class*="location"]'
            ]
            
            for selector in location_selectors:
                location_element = await page.query_selector(selector)
                if location_element:
                    location = await location_element.text_content()
                    if location and location.strip():
                        return location.strip()
            
            return "Location not found"
        except Exception as e:
            logger.debug(f"Error extracting location: {e}")
            return "Location not found"
    
    async def _extract_date_posted(self, page: Page) -> Optional[str]:
        """Extract the date when the listing was posted."""
        try:
            # Look for date information in Report-stats section
            stats_element = await page.query_selector('.Report-stats')
            if stats_element:
                # Look for Report-stat elements with title attributes containing dates
                date_elements = await stats_element.query_selector_all('.Report-stat[title*="sep"], .Report-stat[title*="jan"], .Report-stat[title*="feb"], .Report-stat[title*="mrt"], .Report-stat[title*="apr"], .Report-stat[title*="mei"], .Report-stat[title*="jun"], .Report-stat[title*="jul"], .Report-stat[title*="aug"], .Report-stat[title*="okt"], .Report-stat[title*="nov"], .Report-stat[title*="dec"]')
                
                for date_element in date_elements:
                    date_text = await date_element.get_attribute('title')
                    if date_text:
                        parsed_date = self._parse_date(date_text)
                        if parsed_date:
                            return parsed_date
                
                # Also try to find elements with "Sinds" text
                since_elements = await stats_element.query_selector_all('.Report-stat')
                for since_element in since_elements:
                    text_content = await since_element.text_content()
                    if text_content and 'sinds' in text_content.lower():
                        # Try to extract date from the text content
                        parsed_date = self._parse_date(text_content)
                        if parsed_date:
                            return parsed_date
                        
                        # Also try the title attribute
                        title_text = await since_element.get_attribute('title')
                        if title_text:
                            parsed_date = self._parse_date(title_text)
                            if parsed_date:
                                return parsed_date
            
            # Fallback: Try to find any element with date-like title attributes
            all_elements = await page.query_selector_all('[title*="sep"], [title*="jan"], [title*="feb"], [title*="mrt"], [title*="apr"], [title*="mei"], [title*="jun"], [title*="jul"], [title*="aug"], [title*="okt"], [title*="nov"], [title*="dec"]')
            for element in all_elements:
                title_text = await element.get_attribute('title')
                if title_text:
                    parsed_date = self._parse_date(title_text)
                    if parsed_date:
                        return parsed_date
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting date posted: {e}")
            return None
    
    def _parse_date(self, date_text: str) -> Optional[str]:
        """Parse Dutch date text to ISO format."""
        try:
            # Common Dutch date patterns
            date_patterns = [
                r'(\d{1,2})\s+(jan|feb|mrt|apr|mei|jun|jul|aug|sep|okt|nov|dec)\.?\s*\'?(\d{2,4})(?:,\s*(\d{1,2}):(\d{2}))?',  # Pattern for "25 aug '25, 14:29"
                r'(\d{1,2})\s+(jan|feb|mrt|apr|mei|jun|jul|aug|sep|okt|nov|dec)\s+(\d{4})',
                r'(\d{1,2})\s+(januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+(\d{4})',

            ]
            
            date_text_lower = date_text.lower().strip()
            
            # Handle "vandaag" (today)
            if 'vandaag' in date_text_lower:
                return datetime.now(timezone.utc).isoformat()
            
            # Handle "gisteren" (yesterday)
            if 'gisteren' in date_text_lower:
                yesterday = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                yesterday = yesterday.replace(day=yesterday.day - 1)
                return yesterday.isoformat()
            
            # Handle "X dagen geleden" (X days ago)
            days_ago_match = re.search(r'(\d{1,2})\s+dagen\s+geleden', date_text_lower)
            if days_ago_match:
                days_ago = int(days_ago_match.group(1))
                past_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                past_date = past_date.replace(day=past_date.day - days_ago)
                return past_date.isoformat()
            
            # Handle "X weken geleden" (X weeks ago)
            weeks_ago_match = re.search(r'(\d{1,2})\s+weken\s+geleden', date_text_lower)
            if weeks_ago_match:
                weeks_ago = int(weeks_ago_match.group(1))
                past_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                past_date = past_date.replace(day=past_date.day - (weeks_ago * 7))
                return past_date.isoformat()
            
            # Handle specific dates
            for pattern in date_patterns:
                match = re.search(pattern, date_text_lower)
                if match:
                    groups = match.groups()
                    
                    # Handle the new pattern with time: "25 aug '25, 14:29"
                    if len(groups) == 5 and groups[3] is not None and groups[4] is not None:
                        day, month, year, hour, minute = groups
                        hour = int(hour)
                        minute = int(minute)
                    elif len(groups) == 3:
                        day, month, year = groups
                        hour = 0
                        minute = 0
                    else:
                        continue
                    
                    # Convert Dutch month names to numbers
                    month_map = {
                        'jan': 1, 'januari': 1,
                        'feb': 2, 'februari': 2,
                        'mrt': 3, 'maart': 3,
                        'apr': 4, 'april': 4,
                        'mei': 5,
                        'jun': 6, 'juni': 6,
                        'jul': 7, 'juli': 7,
                        'aug': 8, 'augustus': 8,
                        'sep': 9, 'september': 9,
                        'okt': 10, 'oktober': 10,
                        'nov': 11, 'november': 11,
                        'dec': 12, 'december': 12
                    }
                    
                    month_num = month_map.get(month.lower())
                    if month_num:
                        try:
                            # Handle 2-digit years (e.g., '25 -> 2025)
                            if len(year) == 2:
                                year = 2000 + int(year)
                            else:
                                year = int(year)
                            
                            parsed_date = datetime(year, month_num, int(day), hour, minute, tzinfo=timezone.utc)
                            return parsed_date.isoformat()
                        except ValueError:
                            continue
            
            return None
            
        except Exception as e:
            logger.debug(f"Error parsing date '{date_text}': {e}")
            return None
    
    async def _extract_images(self, page: Page) -> List[str]:
        """Extract image URLs from the listing."""
        try:
            images = []
            
            # Try multiple selectors for images
            image_selectors = [
                '[data-testid="image"] img',
                '.ad-image img',
                '.gallery img',
                '[class*="image"] img'
            ]
            
            for selector in image_selectors:
                image_elements = await page.query_selector_all(selector)
                for img_element in image_elements:
                    src = await img_element.get_attribute('src')
                    if src:
                        # Convert relative URLs to absolute
                        absolute_url = urljoin(page.url, src)
                        images.append(absolute_url)
            
            return images[:10]  # Limit to first 10 images for Pi optimization
            
        except Exception as e:
            logger.debug(f"Error extracting images: {e}")
            return []
    
    async def _extract_attributes(self, page: Page) -> List[str]:
        """Extract listing attributes (condition, size, etc.)."""
        try:
            attributes = []
            
            # Try multiple selectors for attributes
            attr_selectors = [
                '[data-testid="attribute"]',
                '.ad-attribute',
                '.attribute',
                '[class*="attribute"]'
            ]
            
            for selector in attr_selectors:
                attr_elements = await page.query_selector_all(selector)
                for attr_element in attr_elements:
                    attr_text = await attr_element.text_content()
                    if attr_text and attr_text.strip():
                        attributes.append(attr_text.strip())
            
            return attributes[:20]  # Limit to first 20 attributes for Pi optimization
            
        except Exception as e:
            logger.debug(f"Error extracting attributes: {e}")
            return []
    
    async def _extract_view_count(self, page: Page) -> Optional[int]:
        """Extract the number of views for the listing."""
        try:
            # Try multiple selectors for view count
            view_selectors = [
                '[data-testid="view-count"]',
                '.view-count',
                '.ad-views',
                '[class*="view"]'
            ]
            
            for selector in view_selectors:
                view_element = await page.query_selector(selector)
                if view_element:
                    view_text = await view_element.text_content()
                    if view_text:
                        # Extract numbers from the text
                        numbers = re.findall(r'\d+', view_text)
                        if numbers:
                            return int(numbers[0])
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting view count: {e}")
            return None
    
    def _extract_listing_id(self, url: str) -> str:
        """Extract listing ID from URL."""
        try:
            # Extract ID from URL patterns like /m1234567890-title
            match = re.search(r'/m(\d+)', url)
            if match:
                return match.group(1)
            return ""
        except Exception:
            return ""
    
    def is_today(self, date_str: Optional[str]) -> bool:
        """Check if the listing was posted today."""
        if not date_str:
            return False
        
        try:
            listing_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            today = datetime.now(timezone.utc).date()
            return listing_date.date() == today
        except Exception:
            return False


async def scrape_listing_pi(url: str, headless: bool = True) -> Dict[str, Any]:
    """
    Pi-optimized function to scrape a single listing.
    
    Args:
        url: The URL of the listing to scrape
        headless: Whether to run in headless mode
        
    Returns:
        Dictionary containing the scraped listing data
    """
    async with ListingScraperPi(headless=headless) as scraper:
        return await scraper.scrape_listing(url)


async def main():
    """Test the Pi-optimized scraper with a sample URL."""
    # Test with a sample URL
    test_url = "https://www.2dehands.be/v/fietsen-en-brommers/fietsen-racefietsen/m2308511301-specialized-tarmac-sl6-s-works-54cm"
    
    logger.info(f"Testing Pi-optimized scraper with: {test_url}")
    
    result = await scrape_listing_pi(test_url, headless=False)
    
    logger.info("\nScraped data:")
    logger.info(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Check if it's from today
    scraper = ListingScraperPi()
    is_today = scraper.is_today(result.get('date_posted'))
    logger.info(f"\nIs from today: {is_today}")


if __name__ == "__main__":
    asyncio.run(main())
