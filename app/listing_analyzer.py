"""LLM-based listing analyzer for detecting activation locks and extracting data."""
from typing import Dict, Any, Optional
from app.llm_client import LLMClient


class ListingAnalyzer:
    """Analyzes listings using LLM to detect activation locks and extract information."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
    
    async def analyze(
        self,
        listing_data: Dict[str, Any],
        target_model_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a listing to determine if it matches search criteria.
        
        Args:
            listing_data: Dictionary with title, description, link, etc.
            target_model_number: Optional model number to match against
        
        Returns:
            Analysis result with matches, activation_lock_mentioned, etc.
        """
        title = listing_data.get("title", "")
        description = listing_data.get("description", "")
        url = listing_data.get("link", "")
        
        # If description is empty, try to get it from full_text
        if not description and listing_data.get("full_text"):
            description = listing_data.get("full_text", "")
        
        # Call LLM for analysis
        analysis = await self.llm_client.analyze_listing(
            title=title,
            description=description,
            url=url,
            model_number=target_model_number
        )
        
        # Enhance analysis with additional data
        analysis["url"] = url
        analysis["title"] = title
        analysis["price"] = analysis.get("price") or listing_data.get("price", "N/A")
        analysis["condition"] = analysis.get("condition") or listing_data.get("condition", "N/A")
        analysis["seller"] = listing_data.get("seller", "N/A")
        
        return analysis
