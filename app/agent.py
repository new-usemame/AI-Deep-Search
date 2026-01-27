"""Individual agent that searches eBay for MacBooks."""
import asyncio
import random
import logging
from typing import Dict, Any, Optional, List
from app.browser import BrowserManager
from app.listing_analyzer import ListingAnalyzer
from app.filters import ListingFilter
from app.data_manager import DataManager
from app.llm_client import LLMClient
from app.config import settings

logger = logging.getLogger(__name__)


class SearchAgent:
    """An individual agent that searches eBay for MacBooks."""
    
    def __init__(
        self,
        agent_id: int,
        model_number: str,
        filter_config: ListingFilter,
        data_manager: DataManager,
        llm_client: LLMClient
    ):
        self.agent_id = agent_id
        self.model_number = model_number
        self.filter = filter_config
        self.data_manager = data_manager
        self.llm_client = llm_client
        
        self.browser = BrowserManager()
        self.analyzer = ListingAnalyzer(llm_client)
        
        self.is_running = False
        self.is_paused = False
        self.stats = {
            "pages_searched": 0,
            "listings_analyzed": 0,
            "listings_added": 0,
            "errors": 0,
        }
    
    async def start(self):
        """Start the agent's search process."""
        logger.info(f"Agent {self.agent_id}: Starting agent process...")
        self.is_running = True
        self.is_paused = False
        
        try:
            logger.info(f"Agent {self.agent_id}: Initializing browser...")
            try:
                await self.browser.start()
                logger.info(f"Agent {self.agent_id}: Browser started successfully")
            except Exception as browser_error:
                logger.error(f"Agent {self.agent_id}: Browser initialization failed: {browser_error}", exc_info=True)
                self.stats["errors"] += 1
                return
            
            logger.info(f"Agent {self.agent_id}: Starting search process...")
            await self._search_ebay()
            logger.info(f"Agent {self.agent_id}: Search process completed")
        except Exception as e:
            logger.error(f"Agent {self.agent_id} error in start(): {e}", exc_info=True)
            self.stats["errors"] += 1
        finally:
            logger.info(f"Agent {self.agent_id}: Closing browser...")
            try:
                await self.browser.close()
            except Exception as close_error:
                logger.warning(f"Agent {self.agent_id}: Error closing browser: {close_error}")
            self.is_running = False
            logger.info(f"Agent {self.agent_id}: Stopped. Final stats: {self.stats}")
    
    async def stop(self):
        """Stop the agent."""
        self.is_running = False
        self.is_paused = False
        if self.browser:
            await self.browser.close()
    
    async def pause(self):
        """Pause the agent."""
        self.is_paused = True
    
    async def resume(self):
        """Resume the agent."""
        self.is_paused = False
    
    async def _search_ebay(self):
        """Main search loop for eBay."""
        # Construct search query
        query = f"MacBook {self.model_number}"
        logger.info(f"Agent {self.agent_id}: Starting search for {query}")
        
        # Navigate to search page
        logger.info(f"Agent {self.agent_id}: Navigating to eBay search page...")
        success = await self.browser.search_ebay(query)
        if not success:
            logger.error(f"Agent {self.agent_id}: Failed to navigate to search page")
            return
        
        logger.info(f"Agent {self.agent_id}: Successfully navigated to search page")
        
        # Check for CAPTCHA
        logger.info(f"Agent {self.agent_id}: Checking for CAPTCHA...")
        has_captcha = await self.browser.check_captcha()
        if has_captcha:
            logger.warning(f"Agent {self.agent_id}: CAPTCHA detected, pausing")
            await self.pause()
            return
        logger.info(f"Agent {self.agent_id}: No CAPTCHA detected")
        
        pages_searched = 0
        max_pages = settings.max_pages_per_search
        
        while self.is_running and pages_searched < max_pages:
            if self.is_paused:
                await asyncio.sleep(1)
                continue
            
            # Get listings from current page
            logger.info(f"Agent {self.agent_id}: Extracting listings from page {pages_searched + 1}...")
            listings = await self.browser.get_listings_from_page()
            
            if not listings:
                logger.warning(f"Agent {self.agent_id}: No listings found on page {pages_searched + 1}")
                break
            
            logger.info(f"Agent {self.agent_id}: Found {len(listings)} listings on page {pages_searched + 1}")
            
            # Process each listing
            for listing in listings:
                if not self.is_running:
                    break
                
                await self._process_listing(listing)
                
                # Small delay between listings
                await asyncio.sleep(random.uniform(
                    settings.request_delay_min,
                    settings.request_delay_max
                ))
            
            self.stats["pages_searched"] += 1
            pages_searched += 1
            
            # Check for next page
            logger.info(f"Agent {self.agent_id}: Checking for next page...")
            has_next = await self.browser.has_next_page()
            if not has_next:
                logger.info(f"Agent {self.agent_id}: No more pages available")
                break
            
            # Click next page
            logger.info(f"Agent {self.agent_id}: Navigating to next page...")
            next_success = await self.browser.click_next_page()
            if not next_success:
                logger.warning(f"Agent {self.agent_id}: Failed to navigate to next page")
                break
            logger.info(f"Agent {self.agent_id}: Successfully navigated to next page")
            
            # Check for CAPTCHA again
            has_captcha = await self.browser.check_captcha()
            if has_captcha:
                logger.warning(f"Agent {self.agent_id}: CAPTCHA detected after page navigation, pausing")
                await self.pause()
                break
            
            # Delay before next page
            await asyncio.sleep(random.uniform(2, 4))
        
        logger.info(f"Agent {self.agent_id}: Search complete. Pages: {pages_searched}, Analyzed: {self.stats['listings_analyzed']}, Added: {self.stats['listings_added']}, Errors: {self.stats['errors']}")
    
    async def _process_listing(self, listing: Dict[str, Any]):
        """Process a single listing."""
        self.stats["listings_analyzed"] += 1
        listing_title = listing.get("title", "Unknown")[:50]
        logger.debug(f"Agent {self.agent_id}: Processing listing #{self.stats['listings_analyzed']}: {listing_title}")
        
        try:
            # Get full listing details if needed
            if not listing.get("description"):
                logger.debug(f"Agent {self.agent_id}: Fetching full details for listing...")
                details = await self.browser.get_listing_details(listing.get("link", ""))
                listing["description"] = details.get("description", "")
                listing["full_text"] = details.get("full_text", "")
                logger.debug(f"Agent {self.agent_id}: Retrieved {len(listing.get('description', ''))} chars of description")
            
            # Analyze with LLM
            logger.debug(f"Agent {self.agent_id}: Analyzing listing with LLM...")
            analysis = await self.analyzer.analyze(
                listing_data=listing,
                target_model_number=self.model_number
            )
            logger.debug(f"Agent {self.agent_id}: LLM analysis complete. Activation lock: {analysis.get('activation_lock_mentioned', False)}")
            
            # Check if it should be included
            should_include, reason = self.filter.should_include(listing, analysis)
            
            if should_include:
                # Merge analysis data with listing data
                result = {
                    **listing,
                    **analysis,
                }
                
                # Add to CSV
                logger.debug(f"Agent {self.agent_id}: Adding listing to CSV...")
                added = await self.data_manager.add_listing(result)
                if added:
                    self.stats["listings_added"] += 1
                    logger.info(f"Agent {self.agent_id}: ✓ Added listing - {listing_title}")
                else:
                    logger.debug(f"Agent {self.agent_id}: Duplicate listing skipped - {listing_title}")
            else:
                logger.debug(f"Agent {self.agent_id}: ✗ Listing excluded - {reason} - {listing_title}")
        
        except Exception as e:
            logger.error(f"Agent {self.agent_id}: Error processing listing '{listing_title}': {e}", exc_info=True)
            self.stats["errors"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "agent_id": self.agent_id,
            "model_number": self.model_number,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            **self.stats,
        }
