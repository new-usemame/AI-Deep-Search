"""Configuration management for the multi-agent search system."""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenRouter API
    openrouter_api_key: str = Field(..., env="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="meta-llama/llama-3.2-3b-instruct",
        env="OPENROUTER_MODEL"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        env="OPENROUTER_BASE_URL"
    )
    
    # Agent Configuration
    agent_count: int = Field(default=12, env="AGENT_COUNT")
    max_pages_per_search: int = Field(default=50, env="MAX_PAGES_PER_SEARCH")
    max_listings_per_page: int = Field(default=50, env="MAX_LISTINGS_PER_PAGE")
    
    # Search Configuration
    default_model_numbers: str = Field(
        default="A1706,A1707,A1932",
        env="DEFAULT_MODEL_NUMBERS"
    )
    default_sites: str = Field(
        default="ebay.com",
        env="DEFAULT_SITES"
    )
    default_exclusions: str = Field(
        default="broken screen,bad battery,cracked,not working,damaged screen",
        env="DEFAULT_EXCLUSIONS"
    )
    
    # Browser Configuration
    headless: bool = Field(default=True, env="HEADLESS")
    browser_timeout: int = Field(default=30000, env="BROWSER_TIMEOUT")
    page_load_timeout: int = Field(default=30000, env="PAGE_LOAD_TIMEOUT")
    
    # Rate Limiting
    request_delay_min: float = Field(default=1.0, env="REQUEST_DELAY_MIN")
    request_delay_max: float = Field(default=3.0, env="REQUEST_DELAY_MAX")
    
    # Data Storage
    data_dir: str = Field(default="./data", env="DATA_DIR")
    csv_filename: str = Field(default="macbook_results.csv", env="CSV_FILENAME")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def get_model_numbers(self) -> List[str]:
        """Parse model numbers from comma-separated string."""
        return [m.strip() for m in self.default_model_numbers.split(",") if m.strip()]
    
    def get_sites(self) -> List[str]:
        """Parse sites from comma-separated string."""
        return [s.strip() for s in self.default_sites.split(",") if s.strip()]
    
    def get_exclusions(self) -> List[str]:
        """Parse exclusions from comma-separated string."""
        return [e.strip().lower() for e in self.default_exclusions.split(",") if e.strip()]


# Global settings instance
settings = Settings()
