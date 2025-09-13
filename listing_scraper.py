"""
Scraper for individual 2dehands listing pages to extract detailed information.
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
from web_navigator import WebNavigator
from centralized_logging import setup_logging, get_logger

# Set up centralized logging
setup_logging()
logger = get_logger(__name__)


class ListingScraper:
    """Scraper for individual 2dehands listing pages."""
    
    def __init__(
        self, 
        headless: bool = True,
        proxies: Optional[List[str]] = None,
        request_delay: float = None  # Will use config value
    ):
        self.navigator = WebNavigator(
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
        
        Args:
            url: The URL of the listing page
            
        Returns:
            Dictionary containing detailed listing information
        """
        page = await self.navigator.new_page()
        
        try:
            # Navigate to the page with faster loading strategy for individual listings
            success = await self.navigator.navigate_to(page, url, wait_until="domcontentloaded")
            if not success:
                return {}
            
            # Handle cookie banner
            await self.navigator.handle_cookie_banner(page)
            
            # Wait for the main content to load with shorter timeout
            await self.navigator.wait_for_selector_with_timeout(page, '.Listing-root, .hz-Page-content', timeout=5000)
            
            # Extract all the information
            listing_data = await self._extract_listing_data(page, url)
            
            return listing_data
            
        except Exception as e:
            logger.error(f"Error scraping listing {url}: {e}")
            return {}
        finally:
            await page.close()
    
    async def _extract_listing_data(self, page: Page, url: str) -> Dict[str, Any]:
        """Extract detailed data from the listing page."""
        
        # Basic information
        title = await self._extract_title(page)
        price = await self._extract_price(page)
        description = await self._extract_description(page)
        date_posted = await self._extract_date_posted(page)
        
        # Seller information
        seller_info = await self._extract_seller_info(page)
        
        # Specifications/attributes
        specifications = await self._extract_specifications(page)
        
        # Images
        images = await self._extract_images(page)
        
        # Location
        location = await self._extract_location(page)
        
        # Stats (views, favorites)
        stats = await self._extract_stats(page)
        
        # Category information
        category = await self._extract_category(page)
        
        # Listing ID from URL
        listing_id = self._extract_listing_id(url)
        
        return {
            'listing_id': listing_id,
            'url': url,
            'title': title,
            'price': price,
            'description': description,
            'date_posted': date_posted,
            'seller': seller_info,
            'specifications': specifications,
            'images': images,
            'location': location,
            'stats': stats,
            'category': category,
            'scraped_at': datetime.now(timezone.utc).isoformat()
        }
    
    async def _extract_title(self, page: Page) -> str:
        """Extract the listing title."""
        try:
            # Try multiple selectors for the title
            selectors = [
                '.ListingHeader-title',
                'h1.ListingHeader-title',
                'h1',
                '.hz-Listing-title'
            ]
            
            for selector in selectors:
                element = await page.query_selector(selector)
                if element:
                    title = await element.text_content()
                    if title and title.strip():
                        return title.strip()
            
            return ""
        except Exception:
            return ""
    
    async def _extract_price(self, page: Page) -> Dict[str, Any]:
        """Extract price information."""
        try:
            # Try to find price element
            price_element = await page.query_selector('.ListingHeader-price')
            if not price_element:
                price_element = await page.query_selector('.hz-Listing-price')
            
            if price_element:
                price_text = await price_element.text_content()
                if price_text:
                    # Extract numeric price
                    price_match = re.search(r'€\s*([\d.,]+)', price_text)
                    if price_match:
                        price_str = price_match.group(1).replace(',', '').replace('.', '')
                        try:
                            price_cents = int(price_str)
                            return {
                                'display': price_text.strip(),
                                'cents': price_cents,
                                'euros': price_cents / 100
                            }
                        except ValueError:
                            pass
            
            return {'display': '', 'cents': 0, 'euros': 0}
        except Exception:
            return {'display': '', 'cents': 0, 'euros': 0}
    
    async def _extract_description(self, page: Page) -> str:
        """Extract the full description."""
        try:
            # Look for description in multiple places
            selectors = [
                '.Description-description',
                '.Description-description div[data-collapsable="description"]',
                '.hz-Listing-description',
                '.description'
            ]
            
            for selector in selectors:
                element = await page.query_selector(selector)
                if element:
                    description = await element.text_content()
                    if description and description.strip():
                        return description.strip()
            
            return ""
        except Exception:
            return ""
    
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
            date_elements = await page.query_selector_all('[title*="sep"], [title*="jan"], [title*="feb"], [title*="mrt"], [title*="apr"], [title*="mei"], [title*="jun"], [title*="jul"], [title*="aug"], [title*="okt"], [title*="nov"], [title*="dec"]')
            for date_element in date_elements:
                date_text = await date_element.get_attribute('title')
                if date_text:
                    parsed_date = self._parse_date(date_text)
                    if parsed_date:
                        return parsed_date
            
            # Last resort: Try to find "Sinds" text anywhere on the page
            since_element = await page.query_selector('text="Sinds"')
            if since_element:
                parent = await since_element.query_selector('xpath=..')
                if parent:
                    date_text = await parent.text_content()
                    if date_text:
                        return self._parse_date(date_text)
            
            # If we still haven't found a date, log some debug information
            logger.debug(f"Could not extract date from page. URL: {page.url}")
            
            # Try to get some debug info about what's on the page
            try:
                stats_element = await page.query_selector('.Report-stats')
                if stats_element:
                    stats_html = await stats_element.inner_html()
                    logger.debug(f"Report-stats HTML: {stats_html[:500]}...")
                else:
                    logger.debug("No .Report-stats element found on page")
            except Exception:
                pass
            
            return None
        except Exception as e:
            logger.debug(f"Error extracting date: {e}")
            return None
    
    def _parse_date(self, date_text: str) -> Optional[str]:
        """Parse Dutch date text to ISO format."""
        try:
            # Remove extra text and clean up
            date_text = date_text.lower().strip()
            
            # Look for patterns like "4 sep. '25, 15:55" or "Sinds 4 sep. '25" or "7 sep. '25, 17:15"
            # Updated regex to capture time as well
            date_match = re.search(r'(\d{1,2})\s+(jan|feb|mrt|apr|mei|jun|jul|aug|sep|okt|nov|dec)\.?\s*\'?(\d{2,4})(?:,\s*(\d{1,2}):(\d{2}))?', date_text)
            if date_match:
                day = int(date_match.group(1))
                month_str = date_match.group(2)
                year_str = date_match.group(3)
                hour_str = date_match.group(4)
                minute_str = date_match.group(5)
                
                # Convert Dutch month names
                month_map = {
                    'jan': 1, 'feb': 2, 'mrt': 3, 'apr': 4, 'mei': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'dec': 12
                }
                month = month_map.get(month_str, 1)
                
                # Handle year
                if len(year_str) == 2:
                    year = 2000 + int(year_str)
                else:
                    year = int(year_str)
                
                # Handle time (default to 0:0 if not provided)
                hour = int(hour_str) if hour_str else 0
                minute = int(minute_str) if minute_str else 0
                
                # Create datetime object with time
                dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
                return dt.isoformat()
            
            # Also try to match patterns without the apostrophe in year
            date_match = re.search(r'(\d{1,2})\s+(jan|feb|mrt|apr|mei|jun|jul|aug|sep|okt|nov|dec)\.?\s+(\d{2,4})(?:,\s*(\d{1,2}):(\d{2}))?', date_text)
            if date_match:
                day = int(date_match.group(1))
                month_str = date_match.group(2)
                year_str = date_match.group(3)
                hour_str = date_match.group(4)
                minute_str = date_match.group(5)
                
                # Convert Dutch month names
                month_map = {
                    'jan': 1, 'feb': 2, 'mrt': 3, 'apr': 4, 'mei': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'dec': 12
                }
                month = month_map.get(month_str, 1)
                
                # Handle year
                if len(year_str) == 2:
                    year = 2000 + int(year_str)
                else:
                    year = int(year_str)
                
                # Handle time (default to 0:0 if not provided)
                hour = int(hour_str) if hour_str else 0
                minute = int(minute_str) if minute_str else 0
                
                # Create datetime object with time
                dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
                return dt.isoformat()
            
            return None
        except Exception as e:
            logger.debug(f"Error parsing date '{date_text}': {e}")
            return None
    
    def test_date_parsing(self):
        """Test method to verify date parsing works with various formats."""
        test_cases = [
            "4 sep. '25, 15:55",
            "Sinds 4 sep. '25",
            "7 sep. '25, 17:15",
            "Sinds 7 sep. '25",
            "15 jan. '25",
            "Sinds 15 jan. '25",
            "3 mrt. '25, 09:30",
            "Sinds 3 mrt. '25"
        ]
        
        for test_case in test_cases:
            result = self._parse_date(test_case)
            logger.info(f"Date parsing test: '{test_case}' -> '{result}'")
    
    async def _extract_seller_info(self, page: Page) -> Dict[str, Any]:
        """Extract seller information."""
        try:
            seller_info = {}
            
            # Seller name
            name_element = await page.query_selector('.SellerInfo-name a')
            if name_element:
                seller_info['name'] = await name_element.text_content()
                seller_info['url'] = await name_element.get_attribute('href')
            
            # Seller type (private/dealer)
            type_element = await page.query_selector('.SellerInfo-icon[title]')
            if type_element:
                seller_info['type'] = await type_element.get_attribute('title')
            
            # Years on platform
            years_element = await page.query_selector('.SellerInfo-row')
            if years_element:
                years_text = await years_element.text_content()
                if 'jaar' in years_text:
                    seller_info['years_on_platform'] = years_text.strip()
            
            return seller_info
        except Exception:
            return {}
    
    async def _extract_specifications(self, page: Page) -> Dict[str, str]:
        """Extract bike specifications/attributes."""
        try:
            specs = {}
            
            # Look for attributes list
            attributes = await page.query_selector_all('.Attributes-item')
            
            for attr in attributes:
                try:
                    label_element = await attr.query_selector('.Attributes-label')
                    value_element = await attr.query_selector('.Attributes-value')
                    
                    if label_element and value_element:
                        label = await label_element.text_content()
                        value = await value_element.text_content()
                        
                        if label and value:
                            # Clean up the label to use as key
                            key = label.strip().lower().replace(' ', '_').replace(':', '')
                            specs[key] = value.strip()
                except Exception:
                    continue
            
            return specs
        except Exception:
            return {}
    
    async def _extract_images(self, page: Page) -> List[str]:
        """Extract image URLs."""
        try:
            images = []
            
            # Look for main image
            main_img = await page.query_selector('.HeroImage-image')
            if main_img:
                src = await main_img.get_attribute('src')
                if src:
                    images.append(src)
            
            # Look for thumbnail images
            thumbnails = await page.query_selector_all('.Thumbnails-item')
            for thumb in thumbnails:
                style = await thumb.get_attribute('style')
                if style:
                    # Extract URL from background-image style
                    url_match = re.search(r'url\(["\']?([^"\']+)["\']?\)', style)
                    if url_match:
                        images.append(url_match.group(1))
            
            return list(set(images))  # Remove duplicates
        except Exception:
            return []
    
    async def _extract_location(self, page: Page) -> Dict[str, str]:
        """Extract location information."""
        try:
            location = {}
            
            # City name
            city_element = await page.query_selector('.SellerLocationSection-locationName')
            if city_element:
                location['city'] = await city_element.text_content()
            
            # Also check seller info section
            if not location.get('city'):
                location_element = await page.query_selector('.SellerInfo-rowWithIcon')
                if location_element:
                    location_text = await location_element.text_content()
                    if location_text:
                        location['city'] = location_text.strip()
            
            return location
        except Exception:
            return {}
    
    async def _extract_stats(self, page: Page) -> Dict[str, Any]:
        """Extract listing statistics."""
        try:
            stats = {}
            
            # Look for stats in Report section
            stats_elements = await page.query_selector_all('.Report-stat')
            
            for stat in stats_elements:
                try:
                    text = await stat.text_content()
                    if text:
                        if 'bekeken' in text.lower():
                            views_match = re.search(r'(\d+)x', text)
                            if views_match:
                                stats['views'] = int(views_match.group(1))
                        elif 'bewaard' in text.lower():
                            favorites_match = re.search(r'(\d+)x', text)
                            if favorites_match:
                                stats['favorites'] = int(favorites_match.group(1))
                except Exception:
                    continue
            
            return stats
        except Exception:
            return {}
    
    async def _extract_category(self, page: Page) -> Dict[str, str]:
        """Extract category information."""
        try:
            category = {}
            
            # Look for breadcrumbs
            breadcrumbs = await page.query_selector_all('.Breadcrumbs-root a')
            if len(breadcrumbs) >= 3:
                category['parent'] = await breadcrumbs[1].text_content()
                category['subcategory'] = await breadcrumbs[2].text_content()
            
            return category
        except Exception:
            return {}
    
    def _extract_listing_id(self, url: str) -> str:
        """Extract listing ID from URL."""
        try:
            # Look for pattern like m2308511301
            match = re.search(r'm(\d+)', url)
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


async def scrape_listing(url: str, headless: bool = True) -> Dict[str, Any]:
    """
    Convenience function to scrape a single listing.
    
    Args:
        url: The URL of the listing to scrape
        headless: Whether to run browser in headless mode
        
    Returns:
        Dictionary containing listing information
    """
    async with ListingScraper(headless=headless) as scraper:
        return await scraper.scrape_listing(url)


async def main():
    """Test the scraper with a sample URL."""
    # Test with the provided HTML file URL
    test_url = "https://www.2dehands.be/v/fietsen-en-brommers/fietsen-racefietsen/m2308511301-specialized-tarmac-sl6-s-works-54cm"
    
    logger.info(f"Scraping listing: {test_url}")
    
    result = await scrape_listing(test_url, headless=False)
    
    logger.info("\nScraped data:")
    logger.info(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Check if it's from today
    scraper = ListingScraper()
    is_today = scraper.is_today(result.get('date_posted'))
    logger.info(f"\nIs from today: {is_today}")


if __name__ == "__main__":
    asyncio.run(main())
