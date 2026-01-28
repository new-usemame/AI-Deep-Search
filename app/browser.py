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
            logger.info(f"Navigating to: {url}")
            await self.page.goto(
                url,
                wait_until=wait_until,
                timeout=settings.page_load_timeout
            )
            logger.info(f"Page loaded (wait_until={wait_until})")
            
            # Try to wait for network idle, but don't block if it takes too long
            try:
                await asyncio.wait_for(
                    self.page.wait_for_load_state("networkidle"),
                    timeout=5.0
                )
                logger.info("Network idle - page fully loaded")
            except asyncio.TimeoutError:
                logger.info("Network idle timeout (5s), continuing - page may still be loading")
            except Exception as e:
                logger.debug(f"Network idle wait error: {e}, continuing")
            
            logger.info(f"Successfully navigated to: {url}")
            await self._random_delay(1, 2)
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
            logger.info("Waiting for listings to load...")
            
            # Wait a bit for dynamic content to render (navigation already waited for network idle)
            await asyncio.sleep(2)
            
            # Try waiting for common eBay search result containers with timeout
            container_found = False
            container_selectors = ["ul.srp-results", ".srp-results", "[data-viewport]", "ul[class*='srp']"]
            for selector in container_selectors:
                try:
                    await asyncio.wait_for(
                        self.page.wait_for_selector(selector, timeout=3000),
                        timeout=3.0
                    )
                    logger.info(f"Search results container found: {selector}")
                    container_found = True
                    break
                except:
                    continue
            
            if not container_found:
                logger.warning("Search results container not found with any selector, trying to extract anyway")
            
            # Try multiple selectors for eBay listings (eBay has changed their structure over time)
            selectors_to_try = [
                "ul.srp-results > li.s-item",
                "ul.srp-results li.s-item",
                "li.s-item",
                "[data-view] li[data-viewport]",
                ".srp-results .s-item",
            ]
            
            listing_elements = []
            for selector in selectors_to_try:
                try:
                    logger.info(f"Trying selector: {selector}")
                    # Wait for selector with shorter timeout
                    try:
                        await self.page.wait_for_selector(selector, timeout=5000)
                    except:
                        logger.debug(f"Selector {selector} not found, trying next...")
                        continue
                    
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        logger.info(f"Found {len(elements)} elements with selector: {selector}")
                        listing_elements = elements
                        break
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
            
            # If no elements found, try to get page content for debugging
            if not listing_elements:
                logger.warning("No listing elements found with any selector. Checking page content...")
                
                # First, try JavaScript-based approach (most reliable)
                try:
                    page_info = await asyncio.wait_for(
                        self.page.evaluate("""() => {
                            return {
                                title: document.title,
                                url: window.location.href,
                                bodyText: document.body ? document.body.innerText.substring(0, 1000) : 'No body',
                                hasResults: document.querySelector('ul.srp-results') !== null,
                                hasAnyListItems: document.querySelectorAll('li').length,
                                htmlSnippet: document.documentElement.outerHTML.substring(0, 2000)
                            };
                        }"""),
                        timeout=5.0
                    )
                    logger.warning(f"Page info (JS): title='{page_info.get('title', 'N/A')}', url='{page_info.get('url', 'N/A')}'")
                    logger.warning(f"Has results container: {page_info.get('hasResults', False)}")
                    logger.warning(f"Total <li> elements: {page_info.get('hasAnyListItems', 0)}")
                    logger.warning(f"Body text (first 1000 chars): {page_info.get('bodyText', 'N/A')[:1000]}")
                    logger.warning(f"HTML snippet (first 2000 chars): {page_info.get('htmlSnippet', 'N/A')[:2000]}")
                except asyncio.TimeoutError:
                    logger.error("Timeout getting page info via JavaScript")
                except Exception as js_error:
                    logger.error(f"Error getting page info via JavaScript: {js_error}", exc_info=True)
                
                # Fallback: Try Playwright methods
                try:
                    # Get page URL first (this should always work)
                    page_url = self.page.url
                    logger.warning(f"Page URL (Playwright): {page_url}")
                    
                    # Get page title
                    try:
                        page_title = await asyncio.wait_for(self.page.title(), timeout=5.0)
                        logger.warning(f"Page title: {page_title}")
                    except Exception as title_error:
                        logger.error(f"Could not get page title: {title_error}")
                        page_title = "Unknown"
                    
                    # Check if page has any content
                    try:
                        body_text = await asyncio.wait_for(
                            self.page.query_selector("body"),
                            timeout=5.0
                        )
                        if body_text:
                            text_content = await asyncio.wait_for(
                                body_text.inner_text(),
                                timeout=5.0
                            )
                            logger.warning(f"Page contains text (first 1000 chars): {text_content[:1000]}")
                            
                            # Check for common eBay error/block messages
                            text_lower = text_content.lower()
                            if "captcha" in text_lower or "verify" in text_lower:
                                logger.error("CAPTCHA or verification detected on page!")
                            if "access denied" in text_lower or "blocked" in text_lower:
                                logger.error("Access denied or blocked message detected!")
                            if "sorry, we couldn't find" in text_lower or "no results" in text_lower:
                                logger.warning("No search results found on page")
                    except asyncio.TimeoutError:
                        logger.error("Timeout getting page body text")
                    except Exception as e:
                        logger.error(f"Error getting page body: {e}")
                    
                    # Try to find any list items at all
                    try:
                        all_li = await asyncio.wait_for(
                            self.page.query_selector_all("li"),
                            timeout=5.0
                        )
                        logger.warning(f"Found {len(all_li)} total <li> elements on page")
                    except asyncio.TimeoutError:
                        logger.error("Timeout getting list elements")
                    except Exception as e:
                        logger.error(f"Error getting list elements: {e}")
                    
                    # Try to get page HTML structure (fallback)
                    try:
                        html_content = await asyncio.wait_for(
                            self.page.content(),
                            timeout=5.0
                        )
                        # Log a snippet of HTML to see structure
                        logger.warning(f"Page HTML snippet (first 2000 chars): {html_content[:2000]}")
                    except asyncio.TimeoutError:
                        logger.error("Timeout getting page HTML")
                    except Exception as e:
                        logger.error(f"Error getting page HTML: {e}")
                        
                except Exception as debug_error:
                    logger.error(f"Error during debugging: {debug_error}", exc_info=True)
                    # Try to at least get the URL even if other debugging fails
                    try:
                        logger.error(f"Current page URL (from exception handler): {self.page.url}")
                    except:
                        logger.error("Could not even get page URL")
            
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
            # Try multiple selectors for title (eBay has changed structure)
            title_selectors = [
                "h3.s-item__title",
                ".s-item__title",
                "h3[class*='title']",
                "a[class*='title']",
                "h3",
            ]
            
            title_elem = None
            title = ""
            for selector in title_selectors:
                try:
                    title_elem = await element.query_selector(selector)
                    if title_elem:
                        title = await title_elem.inner_text()
                        title = title.strip()
                        if title:
                            break
                except:
                    continue
            
            if not title:
                logger.debug("No title found in listing element")
                return None
            
            # Try multiple selectors for link
            link_selectors = [
                "a.s-item__link",
                "a[class*='link']",
                "a[href*='ebay.com/itm']",
                "a",
            ]
            
            link = None
            for selector in link_selectors:
                try:
                    link_elem = await element.query_selector(selector)
                    if link_elem:
                        link = await link_elem.get_attribute("href")
                        if link and "ebay.com" in link:
                            break
                except:
                    continue
            
            # Try multiple selectors for price
            price_selectors = [
                "span.s-item__price",
                ".s-item__price",
                "[class*='price']",
            ]
            
            price = "N/A"
            for selector in price_selectors:
                try:
                    price_elem = await element.query_selector(selector)
                    if price_elem:
                        price_text = await price_elem.inner_text()
                        if price_text.strip():
                            price = price_text.strip()
                            break
                except:
                    continue
            
            # Try multiple selectors for condition
            condition_selectors = [
                "span.s-item__condition",
                ".s-item__condition",
                "[class*='condition']",
            ]
            
            condition = "N/A"
            for selector in condition_selectors:
                try:
                    condition_elem = await element.query_selector(selector)
                    if condition_elem:
                        condition_text = await condition_elem.inner_text()
                        if condition_text.strip():
                            condition = condition_text.strip()
                            break
                except:
                    continue
            
            # Try multiple selectors for seller
            seller_selectors = [
                "span.s-item__seller-info-text",
                ".s-item__seller-info-text",
                "[class*='seller']",
            ]
            
            seller = "N/A"
            for selector in seller_selectors:
                try:
                    seller_elem = await element.query_selector(selector)
                    if seller_elem:
                        seller_text = await seller_elem.inner_text()
                        if seller_text.strip():
                            seller = seller_text.strip()
                            break
                except:
                    continue
            
            return {
                "title": title,
                "link": link,
                "price": price,
                "condition": condition,
                "shipping": "",
                "seller": seller,
                "description": "",  # Will be filled when viewing details
            }
        except Exception as e:
            logger.warning(f"Error extracting listing data: {e}", exc_info=True)
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
            logger.info("Checking for CAPTCHA indicators...")
            captcha_indicators = [
                "iframe[src*='captcha']",
                ".g-recaptcha",
                "#captcha",
                "text=Please verify you're a human",
            ]
            
            for indicator in captcha_indicators:
                try:
                    # Add timeout to prevent hanging
                    elem = await asyncio.wait_for(
                        self.page.query_selector(indicator),
                        timeout=2.0
                    )
                    if elem:
                        logger.warning(f"CAPTCHA detected via indicator: {indicator}")
                        return True
                except asyncio.TimeoutError:
                    logger.debug(f"Timeout checking CAPTCHA indicator: {indicator}")
                    continue
                except Exception as e:
                    logger.debug(f"Error checking indicator {indicator}: {e}")
                    continue
            
            # Check page text with timeout
            try:
                body_text = await asyncio.wait_for(
                    self.page.query_selector("body"),
                    timeout=2.0
                )
                if body_text:
                    text = await asyncio.wait_for(
                        body_text.inner_text(),
                        timeout=2.0
                    )
                    if "captcha" in text.lower() or "verify" in text.lower():
                        logger.warning("CAPTCHA detected in page text")
                        return True
            except asyncio.TimeoutError:
                logger.debug("Timeout checking page text for CAPTCHA")
            except Exception as e:
                logger.debug(f"Error checking page text: {e}")
            
            logger.info("No CAPTCHA detected")
            return False
        except Exception as e:
            logger.error(f"Error checking for CAPTCHA: {e}", exc_info=True)
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
