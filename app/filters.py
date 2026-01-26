"""Filtering logic for inclusion/exclusion of listings."""
from typing import List, Dict, Any
from app.config import settings


class ListingFilter:
    """Handles filtering of listings based on inclusion/exclusion criteria."""
    
    def __init__(
        self,
        model_numbers: List[str],
        exclusions: List[str],
        require_activation_lock: bool = True
    ):
        self.model_numbers = [m.upper() for m in model_numbers]
        self.exclusions = [e.lower() for e in exclusions]
        self.require_activation_lock = require_activation_lock
    
    def should_include(
        self,
        listing_data: Dict[str, Any],
        llm_analysis: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Determine if a listing should be included in results.
        
        Returns:
            (should_include: bool, reason: str)
        """
        # Check exclusions first
        if llm_analysis.get("has_exclusions", False):
            exclusion_reasons = llm_analysis.get("exclusion_reasons", [])
            reason = f"Contains exclusions: {', '.join(exclusion_reasons)}"
            return False, reason
        
        # Check if activation lock is mentioned (if required)
        if self.require_activation_lock:
            if not llm_analysis.get("activation_lock_mentioned", False):
                return False, "No activation lock mentioned"
        
        # Check model number match (if specified)
        if self.model_numbers:
            listing_model = llm_analysis.get("model_number", "")
            if listing_model:
                listing_model = listing_model.upper()
                # Check if any target model number appears in listing model
                model_match = any(
                    target_model in listing_model or listing_model in target_model
                    for target_model in self.model_numbers
                )
                if not model_match:
                    # Also check if model number is in title/description
                    title_desc = (
                        listing_data.get("title", "") + " " + 
                        listing_data.get("description", "")
                    ).upper()
                    model_match = any(
                        target_model in title_desc
                        for target_model in self.model_numbers
                    )
                
                if not model_match and self.model_numbers:
                    return False, f"Model number mismatch (looking for: {', '.join(self.model_numbers)})"
        
        # Final check: LLM says it matches
        if not llm_analysis.get("matches", False):
            return False, llm_analysis.get("reasoning", "LLM analysis indicates no match")
        
        return True, "Matches all criteria"
    
    def check_exclusions_in_text(self, text: str) -> List[str]:
        """Check if text contains any exclusion terms."""
        text_lower = text.lower()
        found = [ex for ex in self.exclusions if ex in text_lower]
        return found
