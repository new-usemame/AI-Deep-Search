"""Individual agent that searches eBay for MacBooks."""
import asyncio
import random
from typing import Dict, Any, Optional, List
from app.browser import BrowserManager
from app.listing_analyzer import ListingAnalyzer
from app.filters import ListingFilter
from app.data_manager import DataManager
from app.llm_client import LLMClient
from app.config import settings


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
        self.is_running = True
        self.is_paused = False
        
        try:
            await self.browser.start()
            await self._search_ebay()
        except Exception as e:
            print(f"Agent {self.agent_id} error: {e}")
            self.stats["errors"] += 1
        finally:
            await self.browser.close()
            self.is_running = False
    
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
        print(f"Agent {self.agent_id}: Starting search for {query}")
        
        # Navigate to search page
        success = await self.browser.search_ebay(query)
        if not success:
            print(f"Agent {self.agent_id}: Failed to navigate to search page")
            return
        
        # Check for CAPTCHA
        if await self.browser.check_captcha():
            print(f"Agent {self.agent_id}: CAPTCHA detected, pausing")
            await self.pause()
            return
        
        pages_searched = 0
        max_pages = settings.max_pages_per_search
        
        while self.is_running and pages_searched < max_pages:
            if self.is_paused:
                await asyncio.sleep(1)
                continue
            
            # Get listings from current page
            listings = await self.browser.get_listings_from_page()
            
            if not listings:
                print(f"Agent {self.agent_id}: No listings found on page {pages_searched + 1}")
                break
            
            print(f"Agent {self.agent_id}: Found {len(listings)} listings on page {pages_searched + 1}")
            
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
            if not await self.browser.has_next_page():
                print(f"Agent {self.agent_id}: No more pages")
                break
            
            # Click next page
            if not await self.browser.click_next_page():
                print(f"Agent {self.agent_id}: Failed to navigate to next page")
                break
            
            # Check for CAPTCHA again
            if await self.browser.check_captcha():
                print(f"Agent {self.agent_id}: CAPTCHA detected, pausing")
                await self.pause()
                break
            
            # Delay before next page
            await asyncio.sleep(random.uniform(2, 4))
        
        print(f"Agent {self.agent_id}: Search complete. Pages: {pages_searched}, Added: {self.stats['listings_added']}")
    
    async def _process_listing(self, listing: Dict[str, Any]):
        """Process a single listing."""
        self.stats["listings_analyzed"] += 1
        
        try:
            # Get full listing details if needed
            if not listing.get("description"):
                details = await self.browser.get_listing_details(listing.get("link", ""))
                listing["description"] = details.get("description", "")
                listing["full_text"] = details.get("full_text", "")
            
            # Analyze with LLM
            analysis = await self.analyzer.analyze(
                listing_data=listing,
                target_model_number=self.model_number
            )
            
            # Check if it should be included
            should_include, reason = self.filter.should_include(listing, analysis)
            
            if should_include:
                # Merge analysis data with listing data
                result = {
                    **listing,
                    **analysis,
                }
                
                # Add to CSV
                added = await self.data_manager.add_listing(result)
                if added:
                    self.stats["listings_added"] += 1
                    print(f"Agent {self.agent_id}: Added listing - {listing.get('title', '')[:50]}")
                else:
                    print(f"Agent {self.agent_id}: Duplicate listing skipped")
            else:
                print(f"Agent {self.agent_id}: Listing excluded - {reason}")
        
        except Exception as e:
            print(f"Agent {self.agent_id}: Error processing listing: {e}")
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
