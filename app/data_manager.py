"""Data management for CSV export and result tracking."""
import csv
import os
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Set, Optional
from pathlib import Path
from app.config import settings


class DataManager:
    """Manages CSV export and result deduplication."""
    
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = csv_path or os.path.join(settings.data_dir, settings.csv_filename)
        self.seen_urls: Set[str] = set()
        self.seen_hashes: Set[str] = set()
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        
        # Load existing URLs to avoid duplicates
        self._load_existing_urls()
    
    def _load_existing_urls(self):
        """Load existing URLs from CSV to prevent duplicates."""
        if os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = row.get("link", "")
                        if url:
                            self.seen_urls.add(url)
            except Exception as e:
                print(f"Error loading existing URLs: {e}")
    
    def _generate_hash(self, listing: Dict[str, Any]) -> str:
        """Generate hash for listing to detect duplicates."""
        # Use title + price + seller as unique identifier
        unique_str = f"{listing.get('title', '')}{listing.get('price', '')}{listing.get('seller', '')}"
        return hashlib.md5(unique_str.encode()).hexdigest()
    
    def is_duplicate(self, listing: Dict[str, Any]) -> bool:
        """Check if listing is a duplicate."""
        url = listing.get("link", "")
        listing_hash = self._generate_hash(listing)
        
        if url in self.seen_urls:
            return True
        if listing_hash in self.seen_hashes:
            return True
        
        return False
    
    async def add_listing(self, listing: Dict[str, Any]) -> bool:
        """
        Add a listing to CSV if it's not a duplicate.
        
        Returns:
            True if added, False if duplicate
        """
        if self.is_duplicate(listing):
            return False
        
        url = listing.get("link", "")
        listing_hash = self._generate_hash(listing)
        
        self.seen_urls.add(url)
        self.seen_hashes.add(listing_hash)
        
        # Prepare CSV row
        row = {
            "title": listing.get("title", ""),
            "price": listing.get("price", ""),
            "model_number": listing.get("model_number", ""),
            "link": url,
            "condition": listing.get("condition", ""),
            "activation_lock_mentioned": str(listing.get("activation_lock_mentioned", False)),
            "activation_lock_type": listing.get("activation_lock_type", "none"),
            "seller": listing.get("seller", ""),
            "date_found": datetime.now().isoformat(),
            "confidence": str(listing.get("confidence", 0.0)),
            "reasoning": listing.get("reasoning", ""),
        }
        
        # Write to CSV (using sync file operations for CSV compatibility)
        file_exists = os.path.exists(self.csv_path)
        
        with open(self.csv_path, 'a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        
        return True
    
    def get_all_listings(self) -> List[Dict[str, Any]]:
        """Read all listings from CSV."""
        listings = []
        
        if not os.path.exists(self.csv_path):
            return listings
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    listings.append(dict(row))
        except Exception as e:
            print(f"Error reading CSV: {e}")
        
        return listings
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about collected listings."""
        return {
            "total_listings": len(self.seen_urls),
            "csv_path": self.csv_path,
            "csv_exists": os.path.exists(self.csv_path),
        }
