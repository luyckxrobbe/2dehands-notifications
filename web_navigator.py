#!/usr/bin/env python3
"""
WebNavigator class for centralized web navigation with proxy support.
"""

import asyncio
import random
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class WebNavigator:
    """
    Centralized web navigation class that handles browser management,
    page navigation, and proxy configuration.
    """
    
    def __init__(
        self, 
        headless: bool = True,
        proxies: Optional[List[str]] = None,
        proxy_rotation: str = "round_robin",
        user_agents: Optional[List[str]] = None,
        request_delay: float = 1.0,
        page_timeout: int = 30000
    ):
        """
        Initialize the WebNavigator.
        
        Args:
            headless: Whether to run browser in headless mode
            proxies: List of proxy URLs (e.g., ["http://proxy1:port", "http://proxy2:port"])
            proxy_rotation: How to rotate proxies ("round_robin", "random", "none")
            user_agents: List of user agent strings to rotate
            request_delay: Base delay between requests in seconds
            page_timeout: Page navigation timeout in milliseconds
        """
        self.headless = headless
        self.proxies = proxies or []
        self.proxy_rotation = proxy_rotation
        self.user_agents = user_agents or [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0'
        ]
        self.request_delay = request_delay
        self.page_timeout = page_timeout
        
        # Internal state
        self.playwright = None
        self.browser = None
        self.context = None
        self._current_proxy_index = 0
        self._current_ua_index = 0
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def start(self):
        """Start the browser and context."""
        self.playwright = await async_playwright().start()
        
        # Configure browser launch options
        launch_options = {
            'headless': self.headless,
            'args': [
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-extensions',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        }
        
        self.browser = await self.playwright.chromium.launch(**launch_options)
        
        # Create context with proxy if configured
        context_options = await self._get_context_options()
        self.context = await self.browser.new_context(**context_options)
    
    async def close(self):
        """Close browser and playwright."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def _get_context_options(self) -> Dict[str, Any]:
        """Get context options including proxy configuration."""
        options = {
            'user_agent': self._get_next_user_agent(),
            'viewport': {'width': 1920, 'height': 1080},
            'extra_http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        }
        
        # Add proxy if configured
        if self.proxies:
            proxy_url = self._get_next_proxy()
            if proxy_url:
                options['proxy'] = {'server': proxy_url}
        
        return options
    
    def _get_next_proxy(self) -> Optional[str]:
        """Get the next proxy in rotation."""
        if not self.proxies:
            return None
        
        if self.proxy_rotation == "random":
            return random.choice(self.proxies)
        elif self.proxy_rotation == "round_robin":
            proxy = self.proxies[self._current_proxy_index]
            self._current_proxy_index = (self._current_proxy_index + 1) % len(self.proxies)
            return proxy
        else:  # "none" or invalid
            return self.proxies[0] if self.proxies else None
    
    def _get_next_user_agent(self) -> str:
        """Get the next user agent in rotation."""
        ua = self.user_agents[self._current_ua_index]
        self._current_ua_index = (self._current_ua_index + 1) % len(self.user_agents)
        return ua
    
    async def new_page(self) -> Page:
        """Create a new page with current configuration."""
        if not self.context:
            raise RuntimeError("WebNavigator not started. Use async context manager or call start() first.")
        
        page = await self.context.new_page()
        
        # Set additional page options
        await page.set_extra_http_headers({
            'User-Agent': self._get_next_user_agent()
        })
        
        return page
    
    async def navigate_to(self, page: Page, url: str, wait_until: str = "networkidle") -> bool:
        """
        Navigate to a URL with proper error handling and delays.
        
        Args:
            page: The page to navigate
            url: URL to navigate to
            wait_until: When to consider navigation complete
            
        Returns:
            True if navigation successful, False otherwise
        """
        try:
            # Add random delay to avoid detection
            delay = self.request_delay + random.uniform(0, 1)
            await asyncio.sleep(delay)
            
            # Use shorter timeout for pagination pages and individual listings
            if "/p/" in url:
                timeout = 15000  # Pagination pages
            elif "/v/" in url:
                timeout = 10000  # Individual listing pages
            else:
                timeout = self.page_timeout
            
            response = await page.goto(url, wait_until=wait_until, timeout=timeout)
            
            # Check if the response indicates the page doesn't exist
            if response and response.status >= 400:
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Navigation failed for {url}: {e}")
            return False
    
    async def handle_cookie_banner(self, page: Page) -> None:
        """Handle cookie consent banners."""
        cookie_selectors = [
            # 2dehands.be specific selectors based on actual HTML structure
            'button.sp_choice_type_11[title="Accepteren"]',
            'button[aria-label="Accepteren"]',
            'button:has-text("Accepteren")',
            'button:has-text("Alles accepteren")',
            'button:has-text("Accept all")',
            'button:has-text("Accept")',
            'button:has-text("Akkoord")',
            'button:has-text("Alles toestaan")',
            # Generic selectors
            '[data-testid="accept-all"]',
            '[data-testid="accept-cookies"]',
            '.cookie-accept',
            '#cookie-accept',
            'button[class*="accept"]',
            'button[class*="cookie"]',
            # 2dehands consent banner specific
            '#sp_message_container_1269016 button',
            'iframe[title="SP Consent Message"] + div button',
            'div[role="dialog"] button:has-text("Accept")',
            'div[role="dialog"] button:has-text("Accepteren")',
            'div[role="dialog"] button:has-text("Alles accepteren")',
            # Target the specific message container
            '#notice button[title="Accepteren"]',
            '.message-container button[title="Accepteren"]'
        ]
        
        # First, try to handle the specific 2dehands consent banner
        try:
            # Check if the consent banner iframe exists
            consent_iframe = await page.query_selector('iframe[title="SP Consent Message"]')
            if consent_iframe:
                # Try to find and click accept button in the iframe
                try:
                    iframe_content = await consent_iframe.content_frame()
                    if iframe_content:
                        accept_buttons = [
                            'button:has-text("Accept")',
                            'button:has-text("Accepteren")',
                            'button:has-text("Alles accepteren")',
                            'button[class*="accept"]',
                            'button[class*="consent"]'
                        ]
                        for button_selector in accept_buttons:
                            try:
                                button = await iframe_content.query_selector(button_selector)
                                if button:
                                    await button.click()
                                    await asyncio.sleep(1)  # Wait for banner to disappear
                                    return
                            except Exception:
                                continue
                except Exception:
                    pass
                
                # If iframe approach fails, try to dismiss with JavaScript
                try:
                    await page.evaluate("""
                        // Try to find and click the specific 2dehands consent button
                        const acceptButton = document.querySelector('button.sp_choice_type_11[title="Accepteren"]') ||
                                           document.querySelector('button[aria-label="Accepteren"]') ||
                                           document.querySelector('#notice button[title="Accepteren"]') ||
                                           document.querySelector('.message-container button[title="Accepteren"]');
                        
                        if (acceptButton) {
                            acceptButton.click();
                            console.log('Clicked 2dehands consent button via JavaScript');
                        } else {
                            // Fallback: try to find any consent buttons
                            const buttons = document.querySelectorAll('button');
                            for (let button of buttons) {
                                const text = button.textContent?.toLowerCase() || '';
                                const title = button.getAttribute('title')?.toLowerCase() || '';
                                const ariaLabel = button.getAttribute('aria-label')?.toLowerCase() || '';
                                
                                if (text.includes('accept') || text.includes('accepteren') || text.includes('akkoord') ||
                                    title.includes('accept') || title.includes('accepteren') ||
                                    ariaLabel.includes('accept') || ariaLabel.includes('accepteren')) {
                                    button.click();
                                    console.log('Clicked consent button via JavaScript fallback');
                                    break;
                                }
                            }
                        }
                        
                        // Try to remove consent banner elements
                        const consentElements = document.querySelectorAll('[id*="sp_message"], [class*="consent"], [class*="cookie"], #notice, .message-container');
                        consentElements.forEach(el => {
                            if (el.style) el.style.display = 'none';
                            if (el.remove) el.remove();
                        });
                    """)
                    await asyncio.sleep(0.5)
                except Exception:
                    pass
                
                # If iframe approach fails, try to click outside the iframe to dismiss
                try:
                    await page.click('body', position={'x': 10, 'y': 10})
                    await asyncio.sleep(0.5)
                except Exception:
                    pass
        except Exception:
            pass
        
        # Fallback to regular cookie banner handling
        for selector in cookie_selectors:
            try:
                button = await page.query_selector(selector)
                if button:
                    await button.click()
                    await asyncio.sleep(0.5)  # Wait for banner to disappear
                    break
            except Exception:
                continue
    
    async def handle_2dehands_consent_banner(self, page: Page) -> None:
        """Handle 2dehands specific consent banners."""
        consent_selectors = [
            'button:has-text("Akkoord")',
            'button:has-text("Ik ga akkoord")',
            'button:has-text("Alles accepteren")',
            '[data-testid="consent-accept"]',
            '.consent-accept',
            '#consent-accept'
        ]
        
        for selector in consent_selectors:
            try:
                button = await page.query_selector(selector)
                if button:
                    await button.click()
                    await asyncio.sleep(0.5)
                    break
            except Exception:
                continue
    
    async def wait_for_consent_banner_dismissed(self, page: Page) -> None:
        """Wait for consent banners to be dismissed."""
        try:
            # Wait a bit for any animations to complete
            await asyncio.sleep(1)
        except Exception:
            pass
    
    async def wait_for_selector_with_timeout(self, page: Page, selector: str, timeout: int = 10000) -> bool:
        """Wait for selector with timeout and error handling."""
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False
    
    async def safe_click(self, page: Page, selector: str, timeout: int = 5000) -> bool:
        """Safely click an element with error handling."""
        try:
            # First ensure consent banner is handled
            await self.handle_cookie_banner(page)
            
            element = await page.query_selector(selector)
            if element:
                await element.click(timeout=timeout)
                return True
        except Exception as e:
            logger.error(f"Click failed for selector {selector}: {e}")
        return False
    
    async def wait_for_consent_banner_dismissed(self, page: Page, timeout: int = 5000) -> bool:
        """Wait for consent banner to be dismissed."""
        try:
            # Wait for consent banner to disappear
            await page.wait_for_selector('iframe[title="SP Consent Message"]', state='hidden', timeout=timeout)
            return True
        except Exception:
            # If banner doesn't exist or is already dismissed, that's fine
            return True
    
    async def handle_2dehands_consent_banner(self, page: Page) -> bool:
        """Specifically handle 2dehands consent banner."""
        try:
            # Check if the specific 2dehands banner exists
            banner = await page.query_selector('#notice, .message-container')
            if not banner:
                return True  # No banner to handle
            
            # Try to click the accept button
            accept_button = await page.query_selector('button.sp_choice_type_11[title="Accepteren"]')
            if accept_button:
                await accept_button.click()
                await asyncio.sleep(1)
                return True
            
            # Fallback: try other selectors
            fallback_selectors = [
                'button[aria-label="Accepteren"]',
                '#notice button[title="Accepteren"]',
                '.message-container button[title="Accepteren"]',
                'button:has-text("Accepteren")'
            ]
            
            for selector in fallback_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        await button.click()
                        await asyncio.sleep(1)
                        return True
                except Exception:
                    continue
            
            # If all else fails, try JavaScript
            await page.evaluate("""
                const button = document.querySelector('button.sp_choice_type_11[title="Accepteren"]') ||
                              document.querySelector('button[aria-label="Accepteren"]') ||
                              document.querySelector('#notice button[title="Accepteren"]');
                if (button) {
                    button.click();
                    console.log('Clicked 2dehands consent button via JavaScript');
                }
            """)
            
            return True
            
        except Exception:
            return False
    
    async def safe_text_content(self, page: Page, selector: str) -> Optional[str]:
        """Safely get text content from an element."""
        try:
            element = await page.query_selector(selector)
            if element:
                return await element.text_content()
        except Exception:
            pass
        return None
    
    async def safe_get_attribute(self, page: Page, selector: str, attribute: str) -> Optional[str]:
        """Safely get attribute value from an element."""
        try:
            element = await page.query_selector(selector)
            if element:
                return await element.get_attribute(attribute)
        except Exception:
            pass
        return None
    
    def get_current_proxy(self) -> Optional[str]:
        """Get the currently active proxy."""
        if not self.proxies:
            return None
        return self.proxies[self._current_proxy_index % len(self.proxies)]
    
    def get_current_user_agent(self) -> str:
        """Get the currently active user agent."""
        return self.user_agents[self._current_ua_index % len(self.user_agents)]
    
    def add_proxy(self, proxy_url: str):
        """Add a new proxy to the rotation."""
        if proxy_url not in self.proxies:
            self.proxies.append(proxy_url)
    
    def remove_proxy(self, proxy_url: str):
        """Remove a proxy from the rotation."""
        if proxy_url in self.proxies:
            self.proxies.remove(proxy_url)
    
    def set_proxy_rotation(self, rotation: str):
        """Set the proxy rotation strategy."""
        if rotation in ["round_robin", "random", "none"]:
            self.proxy_rotation = rotation
        else:
            raise ValueError("Invalid proxy rotation. Use 'round_robin', 'random', or 'none'")
    
    def set_request_delay(self, delay: float):
        """Set the base request delay."""
        self.request_delay = max(0.1, delay)  # Minimum 100ms delay
    
    def get_stats(self) -> Dict[str, Any]:
        """Get navigation statistics."""
        return {
            'proxies_configured': len(self.proxies),
            'current_proxy': self.get_current_proxy(),
            'user_agents_configured': len(self.user_agents),
            'current_user_agent': self.get_current_user_agent(),
            'proxy_rotation': self.proxy_rotation,
            'request_delay': self.request_delay,
            'headless': self.headless
        }
