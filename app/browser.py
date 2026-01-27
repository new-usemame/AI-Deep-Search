"""Playwright browser wrapper for web automation."""
import asyncio
import random
import logging
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from app.config import settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser instances with stealth configuration."""
    
    def __init__(self, headless: bool = None):
        self.headless = headless if headless is not None else settings.headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    async def start(self):
        """Initialize browser and context."""
        try:
            logger.info("Starting Playwright...")
            self.playwright = await async_playwright().start()
            logger.info("Playwright started successfully")
            
            # Launch browser with stealth settings
            logger.info(f"Launching Chromium browser (headless={self.headless})...")
            try:
                self.browser = await self.playwright.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                    ]
                )
                logger.info("Browser launched successfully")
            except Exception as launch_error:
                logger.error(f"Failed to launch browser: {launch_error}", exc_info=True)
                raise
            
            # Create context with realistic settings
            logger.info("Creating browser context...")
            try:
                self.context = await self.browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=self._get_random_user_agent(),
                    locale="en-US",
                    timezone_id="America/New_York",
                )
                logger.info("Browser context created")
            except Exception as context_error:
                logger.error(f"Failed to create browser context: {context_error}", exc_info=True)
                raise
            
            # Add stealth scripts
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                window.chrome = {
                    runtime: {}
                };
            """)
            
            logger.info("Creating browser page...")
            self.page = await self.context.new_page()
            await self.page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
            })
            logger.info("Browser page created and configured successfully")
        except Exception as e:
            logger.error(f"Error in browser.start(): {e}", exc_info=True)
            raise
    
    async def close(self):
        """Close browser and cleanup."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> bool:
        """Navigate to a URL."""
        try:
            logger.debug(f"Navigating to: {url}")
            await self.page.goto(
                url,
                wait_until=wait_until,
                timeout=settings.page_load_timeout
            )
            logger.debug(f"Successfully navigated to: {url}")
            await self._random_delay(0.5, 1.5)
            return True
        except Exception as e:
            logger.error(f"Navigation error to {url}: {e}", exc_info=True)
            return False
    
    async def search_ebay(self, query: str) -> bool:
        """Navigate to eBay search page."""
        # Construct eBay search URL
        search_url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}"
        logger.info(f"Searching eBay for: {query} (URL: {search_url})")
        result = await self.navigate(search_url)
        if result:
            logger.info(f"Successfully navigated to eBay search page")
        else:
            logger.error(f"Failed to navigate to eBay search page")
        return result
    
    async def get_listings_from_page(self) -> List[Dict[str, Any]]:
        """Extract listing data from current eBay search results page."""
        listings = []
        
        try:
            logger.debug("Waiting for listings to load...")
            # Wait for listings to load
            await self.page.wait_for_selector("ul.srp-results > li", timeout=10000)
            logger.debug("Listings container found")
            
            # Get all listing items
            listing_elements = await self.page.query_selector_all("ul.srp-results > li.s-item")
            logger.info(f"Found {len(listing_elements)} listing elements on page")
            
            for i, element in enumerate(listing_elements):
                try:
                    listing = await self._extract_listing_data(element)
                    if listing:
                        listings.append(listing)
                        logger.debug(f"Extracted listing {i+1}/{len(listing_elements)}: {listing.get('title', '')[:50]}")
                    else:
                        logger.debug(f"Failed to extract data from listing element {i+1}")
                except Exception as e:
                    logger.warning(f"Error extracting listing {i+1}: {e}")
                    continue
            
            logger.info(f"Successfully extracted {len(listings)} listings from page")
            
        except Exception as e:
            logger.error(f"Error getting listings from page: {e}", exc_info=True)
            # Try to get page URL for debugging
            try:
                current_url = self.page.url
                logger.error(f"Current page URL: {current_url}")
            except:
                pass
        
        return listings
    
    async def _extract_listing_data(self, element) -> Optional[Dict[str, Any]]:
        """Extract data from a single listing element."""
        try:
            # Title and link
            title_elem = await element.query_selector("h3.s-item__title")
            if not title_elem:
                logger.debug("No title element found in listing")
                return None
            
            title = await title_elem.inner_text()
            title = title.strip()
            
            if not title:
                logger.debug("Title is empty")
                return None
            
            link_elem = await element.query_selector("a.s-item__link")
            link = await link_elem.get_attribute("href") if link_elem else None
            
            # Price
            price_elem = await element.query_selector("span.s-item__price")
            price = await price_elem.inner_text() if price_elem else "N/A"
            
            # Condition
            condition_elem = await element.query_selector("span.s-item__condition")
            condition = await condition_elem.inner_text() if condition_elem else "N/A"
            
            # Shipping
            shipping_elem = await element.query_selector("span.s-item__shipping")
            shipping = await shipping_elem.inner_text() if shipping_elem else ""
            
            # Seller
            seller_elem = await element.query_selector("span.s-item__seller-info-text")
            seller = await seller_elem.inner_text() if seller_elem else "N/A"
            
            return {
                "title": title,
                "link": link,
                "price": price,
                "condition": condition,
                "shipping": shipping,
                "seller": seller,
                "description": "",  # Will be filled when viewing details
            }
        except Exception as e:
            print(f"Error extracting listing data: {e}")
            return None
    
    async def get_listing_details(self, url: str) -> Dict[str, Any]:
        """Navigate to listing detail page and extract full description."""
        details = {"description": "", "full_text": ""}
        
        try:
            await self.navigate(url)
            await self._random_delay(1, 2)
            
            # Try to get description
            desc_selectors = [
                "#viTabs_0_is > div > div",
                ".vi-item-condition",
                "#viTabs_0_is",
                ".notranslate",
            ]
            
            for selector in desc_selectors:
                try:
                    desc_elem = await self.page.query_selector(selector)
                    if desc_elem:
                        details["description"] = await desc_elem.inner_text()
                        break
                except:
                    continue
            
            # Get full page text as fallback
            body = await self.page.query_selector("body")
            if body:
                details["full_text"] = await body.inner_text()
            
        except Exception as e:
            print(f"Error getting listing details: {e}")
        
        return details
    
    async def has_next_page(self) -> bool:
        """Check if there's a next page of results."""
        try:
            next_button = await self.page.query_selector("a.pagination__next")
            if next_button:
                is_disabled = await next_button.get_attribute("aria-disabled")
                return is_disabled != "true"
            return False
        except:
            return False
    
    async def click_next_page(self) -> bool:
        """Click next page button."""
        try:
            next_button = await self.page.query_selector("a.pagination__next")
            if next_button:
                is_disabled = await next_button.get_attribute("aria-disabled")
                if is_disabled == "true":
                    return False
                
                await next_button.click()
                await self.page.wait_for_load_state("domcontentloaded")
                await self._random_delay(1, 2)
                return True
            return False
        except Exception as e:
            print(f"Error clicking next page: {e}")
            return False
    
    async def check_captcha(self) -> bool:
        """Check if page shows a CAPTCHA."""
        try:
            logger.debug("Checking for CAPTCHA...")
            captcha_indicators = [
                "iframe[src*='captcha']",
                ".g-recaptcha",
                "#captcha",
                "text=Please verify you're a human",
            ]
            
            for indicator in captcha_indicators:
                elem = await self.page.query_selector(indicator)
                if elem:
                    logger.warning(f"CAPTCHA detected via indicator: {indicator}")
                    return True
            
            # Check page text
            body_text = await self.page.query_selector("body")
            if body_text:
                text = await body_text.inner_text()
                if "captcha" in text.lower() or "verify" in text.lower():
                    logger.warning("CAPTCHA detected in page text")
                    return True
            
            logger.debug("No CAPTCHA detected")
            return False
        except Exception as e:
            logger.warning(f"Error checking for CAPTCHA: {e}")
            return False
    
    async def _random_delay(self, min_seconds: float, max_seconds: float):
        """Add random delay to mimic human behavior."""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
    
    def _get_random_user_agent(self) -> str:
        """Get a random realistic user agent."""
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        ]
        return random.choice(user_agents)
