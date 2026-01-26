"""OpenRouter API client for LLM interactions."""
import json
import time
from typing import Dict, Any, Optional
import httpx
from app.config import settings


class LLMClient:
    """Client for interacting with OpenRouter API."""
    
    def __init__(self, model: Optional[str] = None):
        self.api_key = settings.openrouter_api_key
        self.base_url = settings.openrouter_base_url
        self.model = model or settings.openrouter_model
        self.client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/your-repo",
                "X-Title": "MacBook Search Agent",
            }
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def analyze_listing(
        self,
        title: str,
        description: str,
        url: str,
        model_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze an eBay listing using LLM to determine if it matches criteria.
        
        Returns:
            Dict with keys: matches, activation_lock_mentioned, model_number,
            has_exclusions, confidence, reasoning
        """
        prompt = self._build_analysis_prompt(title, description, model_number)
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert at analyzing eBay listings for MacBooks. Analyze listings carefully and respond in valid JSON format only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 500,
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Parse JSON response
                analysis = json.loads(content)
                return analysis
                
            except json.JSONDecodeError as e:
                # Try to extract JSON from markdown code blocks
                try:
                    if "```json" in content:
                        json_start = content.find("```json") + 7
                        json_end = content.find("```", json_start)
                        content = content[json_start:json_end].strip()
                    elif "```" in content:
                        json_start = content.find("```") + 3
                        json_end = content.find("```", json_start)
                        content = content[json_start:json_end].strip()
                    analysis = json.loads(content)
                    return analysis
                except:
                    if attempt == max_retries - 1:
                        # Return default analysis on final failure
                        return self._default_analysis(title, description)
                    time.sleep(2 ** attempt)
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    return self._default_analysis(title, description)
                time.sleep(2 ** attempt)
        
        return self._default_analysis(title, description)
    
    def _build_analysis_prompt(
        self,
        title: str,
        description: str,
        model_number: Optional[str] = None
    ) -> str:
        """Build the prompt for listing analysis."""
        model_context = ""
        if model_number:
            model_context = f"\n\nTarget model number: {model_number}"
        
        prompt = f"""Analyze this eBay listing for a MacBook:

Title: {title}
Description: {description[:2000]}{model_context}

Determine the following and respond in valid JSON format:
{{
  "matches": true/false,  // Should this listing be included in results?
  "activation_lock_mentioned": true/false,  // Does it mention activation lock, iCloud lock, or similar? (explicit or implicit)
  "activation_lock_type": "explicit" | "implicit" | "none",  // How is it mentioned?
  "model_number": "string or null",  // Extracted model number (e.g., A1706, A1707)
  "has_exclusions": true/false,  // Does it mention broken screen, bad battery, cracked, not working, etc.?
  "exclusion_reasons": ["reason1", "reason2"],  // List of exclusion terms found
  "price": "string or null",  // Extracted price if mentioned
  "condition": "string or null",  // Condition mentioned (for parts, as-is, etc.)
  "confidence": 0.0-1.0,  // Confidence in analysis
  "reasoning": "brief explanation"  // Why it matches or doesn't match
}}

Important:
- Activation lock can be mentioned explicitly ("activation lock", "iCloud locked") or implicitly ("can't unlock", "previous owner", "for parts", "as-is", "locked to owner")
- Exclude if it mentions: broken screen, bad battery, cracked, not working, damaged screen, dead battery
- Include if it mentions activation lock (explicit or implicit) AND doesn't have exclusions
- Be conservative: if unsure, set matches to false"""
        
        return prompt
    
    def _default_analysis(self, title: str, description: str) -> Dict[str, Any]:
        """Return default analysis when LLM call fails."""
        text_lower = (title + " " + description).lower()
        
        # Simple keyword matching as fallback
        activation_keywords = [
            "activation lock", "icloud lock", "locked", "can't unlock",
            "previous owner", "for parts", "as-is"
        ]
        exclusion_keywords = [
            "broken screen", "bad battery", "cracked", "not working",
            "damaged screen", "dead battery"
        ]
        
        has_activation = any(kw in text_lower for kw in activation_keywords)
        has_exclusions = any(kw in text_lower for kw in exclusion_keywords)
        
        return {
            "matches": has_activation and not has_exclusions,
            "activation_lock_mentioned": has_activation,
            "activation_lock_type": "implicit" if has_activation else "none",
            "model_number": None,
            "has_exclusions": has_exclusions,
            "exclusion_reasons": [kw for kw in exclusion_keywords if kw in text_lower],
            "price": None,
            "condition": None,
            "confidence": 0.5,
            "reasoning": "Fallback analysis due to LLM error"
        }
