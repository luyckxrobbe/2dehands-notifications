#!/usr/bin/env python3
"""
Minimal Bike class for backup storage - only essential fields for duplicate detection.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import re
import json


class BikeMinimal:
    """
    Minimal bike representation for backup storage.
    Only stores essential fields needed for duplicate detection.
    All other details are scraped from individual pages when needed.
    """
    
    def __init__(self, title: str, price: str, href: str, scraped_at: datetime = None):
        """
        Initialize a minimal Bike object with only essential fields.
        
        Args:
            title: The bike listing title
            price: The price as string (e.g., "€ 1.200,00" or "Bieden")
            href: The URL to the listing
            scraped_at: When this bike was first scraped (for duplicate detection)
        """
        self.title = title
        self.price = price
        self.href = href
        self._scraped_at = scraped_at or datetime.now()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BikeMinimal':
        """
        Create a BikeMinimal instance from a dictionary.
        
        Args:
            data: Dictionary containing minimal bike data
            
        Returns:
            BikeMinimal instance
        """
        bike = cls(
            title=data.get('title', ''),
            price=data.get('price', ''),
            href=data.get('href', '')
        )
        
        # Restore the scraped_at timestamp if it exists
        if 'scraped_at' in data:
            try:
                bike._scraped_at = datetime.fromisoformat(data['scraped_at'])
            except (ValueError, TypeError):
                bike._scraped_at = datetime.now()
        
        return bike
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert BikeMinimal instance to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation with only essential fields
        """
        return {
            'title': self.title,
            'price': self.price,
            'href': self.href,
            'scraped_at': self._scraped_at.isoformat()
        }
    
    def get_numeric_price(self) -> Optional[float]:
        """
        Extract numeric price from price string.
        Handles European number format where dots are thousand separators.
        
        Returns:
            Numeric price as float, or None if price cannot be parsed
        """
        if not self.price:
            return None
        
        # Remove currency symbols and clean up
        price_clean = re.sub(r'[€$£¥]', '', self.price.strip())
        
        # Handle "Bieden" (bidding) or similar non-numeric prices
        if not re.search(r'\d', price_clean):
            return None
        
        try:
            # Replace dots with empty string (thousand separators) and comma with dot (decimal)
            price_clean = price_clean.replace('.', '').replace(',', '.')
            return float(price_clean)
        except ValueError:
            return None
    
    def is_scraped_today(self) -> bool:
        """
        Check if this bike was scraped today.
        
        Returns:
            True if scraped today, False otherwise
        """
        today = datetime.now().date()
        return self._scraped_at.date() == today
    
    def __eq__(self, other) -> bool:
        """
        Check if two bikes are the same based on href (unique identifier).
        
        Args:
            other: Another BikeMinimal object
            
        Returns:
            True if bikes are the same, False otherwise
        """
        if not isinstance(other, BikeMinimal):
            return False
        return self.href == other.href
    
    def __hash__(self) -> int:
        """
        Hash based on href for use in sets and dictionaries.
        
        Returns:
            Hash value based on href
        """
        return hash(self.href)
    
    def __str__(self) -> str:
        """String representation of the bike."""
        return f"BikeMinimal(title='{self.title[:50]}...', price='{self.price}', href='{self.href}')"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"BikeMinimal(title='{self.title}', price='{self.price}', href='{self.href}', scraped_at='{self._scraped_at}')"


class BikeMinimalListings:
    """
    Minimal listings collection for backup storage with only essential fields.
    """
    
    def __init__(self, bikes: Optional[List[BikeMinimal]] = None, max_bikes: int = 300):
        """
        Initialize with optional list of minimal bikes.
        
        Args:
            bikes: Optional list of BikeMinimal objects
            max_bikes: Maximum number of bikes to keep in rolling window
        """
        self.bikes: List[BikeMinimal] = bikes or []
        self.max_bikes = max_bikes
        self._last_updated = datetime.now()
        self._enforce_max_bikes()
    
    @classmethod
    def from_json_file(cls, file_path, max_bikes: int = 300) -> 'BikeMinimalListings':
        """
        Load from JSON file with only essential fields.
        
        Args:
            file_path: Path to JSON file
            max_bikes: Maximum number of bikes to keep
            
        Returns:
            BikeMinimalListings instance
        """
        if not file_path.exists():
            return cls(max_bikes=max_bikes)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            bikes = []
            for item in data:
                if isinstance(item, dict):
                    bikes.append(BikeMinimal.from_dict(item))
            
            return cls(bikes, max_bikes=max_bikes)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error loading from {file_path}: {e}")
            return cls(max_bikes=max_bikes)
    
    @classmethod
    def from_full_bikes(cls, full_bikes: List, max_bikes: int = 300) -> 'BikeMinimalListings':
        """
        Create minimal listings from full Bike objects.
        
        Args:
            full_bikes: List of full Bike objects
            max_bikes: Maximum number of bikes to keep
            
        Returns:
            BikeMinimalListings instance
        """
        minimal_bikes = []
        for bike in full_bikes:
            minimal_bike = BikeMinimal(
                title=bike.title,
                price=bike.price,
                href=bike.href,
                scraped_at=bike._scraped_at
            )
            minimal_bikes.append(minimal_bike)
        
        return cls(minimal_bikes, max_bikes=max_bikes)
    
    def _enforce_max_bikes(self) -> None:
        """Ensure we don't exceed max_bikes by removing oldest bikes."""
        if len(self.bikes) > self.max_bikes:
            self.bikes.sort(key=lambda b: b._scraped_at, reverse=True)
            self.bikes = self.bikes[:self.max_bikes]
    
    def add_bike(self, bike: BikeMinimal) -> None:
        """Add a single minimal bike to the collection."""
        if bike not in self.bikes:
            self.bikes.append(bike)
            self._enforce_max_bikes()
            self._last_updated = datetime.now()
    
    def add_bikes(self, bikes: List[BikeMinimal]) -> None:
        """Add multiple minimal bikes to the collection."""
        for bike in bikes:
            self.add_bike(bike)
    
    def contains(self, bike: BikeMinimal) -> bool:
        """Check if a bike is already in the collection."""
        return bike in self.bikes
    
    def get_new_bikes(self, other_bikes: List[BikeMinimal]) -> List[BikeMinimal]:
        """Get bikes that are not in this collection."""
        return [bike for bike in other_bikes if bike not in self.bikes]
    
    def to_json_file(self, file_path) -> None:
        """Save to JSON file with only essential fields."""
        import json
        from pathlib import Path
        
        # Create directory if it doesn't exist
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        data = [bike.to_dict() for bike in self.bikes]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def __len__(self) -> int:
        """Return number of bikes in collection."""
        return len(self.bikes)
    
    def __iter__(self):
        """Iterate over bikes in collection."""
        return iter(self.bikes)
    
    def __contains__(self, bike: BikeMinimal) -> bool:
        """Check if bike is in collection."""
        return bike in self.bikes
