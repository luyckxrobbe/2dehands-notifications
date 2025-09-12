#!/usr/bin/env python3
"""
Raspberry Pi optimized WebNavigator class for minimal resource usage.
"""

import asyncio
import random
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class WebNavigatorPi:
    """
    Raspberry Pi optimized web navigation class with minimal resource usage.
    """
    
    def __init__(
        self, 
        headless: bool = True,
        proxies: Optional[List[str]] = None,
        request_delay: float = 2.0,  # Increased delay for Pi
        page_timeout: int = 15000,   # Reduced timeout
        max_pages_per_session: int = 5  # Limit pages per browser session
    ):
        """
        Initialize the Raspberry Pi optimized WebNavigator.
        
        Args:
            headless: Whether to run browser in headless mode (always True on Pi)
            proxies: List of proxy URLs
            request_delay: Base delay between requests in seconds (increased for Pi)
            page_timeout: Page navigation timeout in milliseconds (reduced for Pi)
            max_pages_per_session: Maximum pages to scrape before restarting browser (default: 5)
        """
        self.headless = True  # Always headless on Pi
        self.proxies = proxies or []
        self.request_delay = request_delay
        self.page_timeout = page_timeout
        self.max_pages_per_session = max_pages_per_session
        
        # Simplified user agent for Pi
        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        # Internal state
        self.playwright = None
        self.browser = None
        self.context = None
        self._current_proxy_index = 0
        self._pages_scraped = 0
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def start(self):
        """Start the browser and context with Pi-optimized settings."""
        self.playwright = await async_playwright().start()
        
        # Pi-optimized browser launch options
        launch_options = {
            'headless': True,
            'args': [
                '--no-sandbox',
                '--disable-dev-shm-usage',  # Critical for Pi
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=TranslateUI',
                '--disable-ipc-flooding-protection',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images',  # Don't load images to save memory
                '--disable-javascript',  # Disable JS for faster loading
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--memory-pressure-off',
                '--max_old_space_size=512',  # Limit memory usage
                '--single-process',  # Use single process to save memory
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--mute-audio'
            ]
        }
        
        self.browser = await self.playwright.chromium.launch(**launch_options)
        
        # Create context with minimal settings
        context_options = {
            'user_agent': self.user_agent,
            'viewport': {'width': 1024, 'height': 768},  # Smaller viewport
            'ignore_https_errors': True,
            'java_script_enabled': False,  # Disable JS for speed
            'bypass_csp': True
        }
        
        # Add proxy if configured
        if self.proxies:
            proxy = self._get_next_proxy()
            context_options['proxy'] = {'server': proxy}
        
        self.context = await self.browser.new_context(**context_options)
        self._pages_scraped = 0
    
    async def close(self):
        """Close browser and playwright."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    def _get_next_proxy(self) -> str:
        """Get next proxy in rotation."""
        if not self.proxies:
            return None
        proxy = self.proxies[self._current_proxy_index]
        self._current_proxy_index = (self._current_proxy_index + 1) % len(self.proxies)
        return proxy
    
    async def new_page(self) -> Page:
        """Create a new page with Pi optimizations."""
        # Restart browser if we've scraped too many pages
        if self._pages_scraped >= self.max_pages_per_session:
            logger.info("Restarting browser to free memory...")
            await self.close()
            await self.start()
        
        page = await self.context.new_page()
        
        # Set aggressive timeouts for Pi
        page.set_default_timeout(self.page_timeout)
        page.set_default_navigation_timeout(self.page_timeout)
        
        # Block unnecessary resources to save bandwidth and memory
        await page.route("**/*", self._block_unnecessary_resources)
        
        self._pages_scraped += 1
        return page
    
    async def _block_unnecessary_resources(self, route):
        """Block unnecessary resources to save bandwidth and memory."""
        resource_type = route.request.resource_type
        if resource_type in ['image', 'media', 'font', 'stylesheet']:
            await route.abort()
        else:
            await route.continue_()
    
    async def navigate_to(self, page: Page, url: str, wait_until: str = "domcontentloaded") -> bool:
        """Navigate to URL with Pi-optimized settings."""
        try:
            # Use domcontentloaded for faster loading
            await page.goto(url, wait_until="domcontentloaded", timeout=self.page_timeout)
            
            # Wait a bit for dynamic content but not too long
            await asyncio.sleep(1)
            
            return True
        except Exception as e:
            logger.warning(f"Navigation failed for {url}: {e}")
            return False
    
    async def wait_for_selector_with_timeout(self, page: Page, selector: str, timeout: int = 5000) -> bool:
        """Wait for selector with reduced timeout for Pi."""
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False
    
    async def handle_2dehands_consent_banner(self, page: Page):
        """Handle consent banner with Pi-optimized approach."""
        try:
            # Try to find and click consent button quickly
            consent_selectors = [
                'button[data-testid="consent-accept-all"]',
                'button:has-text("Accept all")',
                'button:has-text("Accepteren")',
                '.consent-accept-all',
                '[data-testid="consent-accept-all"]'
            ]
            
            for selector in consent_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.is_visible(timeout=2000):
                        await element.click(timeout=2000)
                        await asyncio.sleep(0.5)  # Short wait
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Consent banner handling failed: {e}")
    
    async def handle_cookie_banner(self, page: Page):
        """Handle cookie banner with Pi-optimized approach."""
        try:
            # Try to find and click cookie accept button quickly
            cookie_selectors = [
                'button:has-text("Accept")',
                'button:has-text("Accepteren")',
                '.cookie-accept',
                '[data-testid="cookie-accept"]'
            ]
            
            for selector in cookie_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.is_visible(timeout=2000):
                        await element.click(timeout=2000)
                        await asyncio.sleep(0.5)  # Short wait
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Cookie banner handling failed: {e}")
    
    async def wait_for_consent_banner_dismissed(self, page: Page):
        """Wait for consent banner to be dismissed with short timeout."""
        try:
            # Wait for banner to disappear or timeout quickly
            await page.wait_for_function(
                "() => !document.querySelector('[data-testid=\"consent-accept-all\"]') && !document.querySelector('button:has-text(\"Accept all\")')",
                timeout=3000
            )
        except Exception:
            # Continue even if banner doesn't disappear
            pass
