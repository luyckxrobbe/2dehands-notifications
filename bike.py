#!/usr/bin/env python3
"""
Bike class for representing individual bike listings from 2dehands/marktplaats.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import re


class Bike:
    """
    Represents a single bike listing with all its properties and methods.
    """
    
    def __init__(self, title: str, price: str, href: str, seller: str, 
                 location: str, date: str, attributes: List[str], 
                 description: str, image: str):
        """
        Initialize a Bike object with all listing data.
        
        Args:
            title: The bike listing title
            price: The price as string (e.g., "€ 1.200,00" or "Bieden")
            href: The URL to the listing
            seller: The seller name
            location: The location where the bike is located
            date: The date when the listing was posted
            attributes: List of bike attributes (condition, size, material, etc.)
            description: The listing description
            image: URL to the bike image
        """
        self.title = title
        self.price = price
        self.href = href
        self.seller = seller
        self.location = location
        self.date = date
        self.attributes = attributes
        self.description = description
        self.image = image
        self._scraped_at = datetime.now()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Bike':
        """
        Create a Bike instance from a dictionary (e.g., from JSON data).
        
        Args:
            data: Dictionary containing bike listing data
            
        Returns:
            Bike instance
        """
        bike = cls(
            title=data.get('title', ''),
            price=data.get('price', ''),
            href=data.get('href', ''),
            seller=data.get('seller', ''),
            location=data.get('location', ''),
            date=data.get('date', ''),
            attributes=data.get('attributes', []),
            description=data.get('description', ''),
            image=data.get('image', '')
        )
        
        # Restore the scraped_at timestamp if it exists in the data
        if 'scraped_at' in data:
            try:
                bike._scraped_at = datetime.fromisoformat(data['scraped_at'])
            except (ValueError, TypeError):
                # If parsing fails, keep the current timestamp (datetime.now())
                pass
        
        return bike
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Bike instance to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the bike
        """
        return {
            'title': self.title,
            'price': self.price,
            'href': self.href,
            'seller': self.seller,
            'location': self.location,
            'date': self.date,
            'attributes': self.attributes,
            'description': self.description,
            'image': self.image,
            'scraped_at': self._scraped_at.isoformat()
        }
    
    def get_numeric_price(self) -> Optional[float]:
        """
        Extract numeric price from price string.
        Handles European number format where dots are thousand separators.
        e.g., "€ 1.20" = 1200 euros, "€ 1.200,50" = 1200.50 euros
        
        Returns:
            Numeric price as float, or None if price is "Bieden" or invalid
        """
        if not self.price or self.price.lower() in ['bieden', 'price on request']:
            return None
        
        # Remove currency symbols and spaces
        price_clean = re.sub(r'[€$£¥]', '', self.price)
        price_clean = re.sub(r'\s+', '', price_clean)
        
        # Handle European number format
        # Pattern: digits with optional dots (thousand separators) and optional comma (decimal separator)
        # Examples: "1.20" -> 1200, "1.200,50" -> 1200.50, "1200" -> 1200
        match = re.search(r'(\d+(?:\.\d{3})*(?:,\d{2})?)', price_clean)
        if match:
            price_str = match.group(1)
            
            # Check if there's a comma (decimal separator)
            if ',' in price_str:
                # Format: "1.200,50" - dots are thousand separators, comma is decimal
                parts = price_str.split(',')
                integer_part = parts[0].replace('.', '')  # Remove thousand separators
                decimal_part = parts[1]
                return float(f"{integer_part}.{decimal_part}")
            else:
                # Format: "1.20" or "1200" - need to determine if dots are thousand separators
                # If there are dots and the last group after dots has 3 digits, treat as thousand separators
                if '.' in price_str:
                    parts = price_str.split('.')
                    # If last part has 3 digits, treat all dots as thousand separators
                    if len(parts[-1]) == 3:
                        return float(price_str.replace('.', ''))
                    else:
                        # Otherwise treat as decimal separator
                        return float(price_str)
                else:
                    # No dots, just a plain number
                    return float(price_str)
        
        return None
    
    def get_condition(self) -> Optional[str]:
        """
        Extract condition from attributes.
        
        Returns:
            Condition string (e.g., "Nieuw", "Zo goed als nieuw", "Gebruikt")
        """
        condition_keywords = ['nieuw', 'gebruikt', 'zo goed als nieuw']
        
        for attr in self.attributes:
            attr_lower = attr.lower()
            for keyword in condition_keywords:
                if keyword in attr_lower:
                    return attr
        
        return None
    
    def get_frame_material(self) -> Optional[str]:
        """
        Extract frame material from attributes.
        
        Returns:
            Frame material (e.g., "Carbon", "Aluminium", "Staal")
        """
        material_keywords = ['carbon', 'aluminium', 'staal', 'steel', 'titanium']
        
        for attr in self.attributes:
            attr_lower = attr.lower()
            for keyword in material_keywords:
                if keyword in attr_lower:
                    return attr
        
        return None
    
    def get_frame_size(self) -> Optional[str]:
        """
        Extract frame size from attributes or title.
        
        Returns:
            Frame size if found
        """
        # Look in attributes first
        size_patterns = [
            r'(\d+)\s*cm',
            r'(\d+)\s*inch',
            r'(xs|s|m|l|xl)',
            r'(\d+)\s*tot\s*(\d+)\s*cm'
        ]
        
        for attr in self.attributes:
            for pattern in size_patterns:
                match = re.search(pattern, attr.lower())
                if match:
                    return attr
        
        # Look in title
        for pattern in size_patterns:
            match = re.search(pattern, self.title.lower())
            if match:
                return match.group(0)
        
        return None
    
    def get_brand(self) -> Optional[str]:
        """
        Extract bike brand from title.
        
        Returns:
            Brand name if found
        """
        # Common bike brands
        brands = [
            'trek', 'specialized', 'canyon', 'giant', 'cannondale', 'bmc',
            'cervelo', 'pinarello', 'bianchi', 'colnago', 'wilier', 'ridley',
            'cube', 'scott', 'merida', 'focus', 'orbea', 'felt', 'koga',
            'isaac', 'eddy merckx', 'look', 'factor', 'prorace', 'thompson'
        ]
        
        title_lower = self.title.lower()
        for brand in brands:
            if brand in title_lower:
                return brand.title()
        
        return None
    
    def is_scraped_today(self) -> bool:
        """
        Check if this bike was scraped today.
        
        Returns:
            True if the bike was scraped today, False otherwise
        """
        from datetime import datetime
        today = datetime.now().date()
        return self._scraped_at.date() == today
    
    def is_new_listing(self, other_bikes: List['Bike']) -> bool:
        """
        Check if this bike is a new listing compared to a list of existing bikes.
        
        Args:
            other_bikes: List of existing Bike objects to compare against
            
        Returns:
            True if this bike is not found in the existing list
        """
        for bike in other_bikes:
            if self.href == bike.href:
                return False
        return True
    
    def is_duplicate_of(self, other: 'Bike') -> bool:
        """
        Check if this bike is a duplicate of another bike using only href comparison.
        This is the fastest and most reliable method for duplicate detection.
        
        Args:
            other: Another Bike object to compare against
            
        Returns:
            True if this bike is considered a duplicate of the other bike
        """
        if not isinstance(other, Bike):
            return False
        
        # Only check: exact href match (most reliable and fastest)
        return self.href == other.href
    
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """
        Calculate similarity between two titles using simple word overlap.
        
        Args:
            title1: First title
            title2: Second title
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Normalize titles: lowercase, remove extra spaces, remove common words
        def normalize_title(title):
            # Remove common words that don't add meaning
            common_words = {'de', 'het', 'een', 'van', 'op', 'in', 'met', 'voor', 'en', 'of', 'racefiets', 'fiets', 'bike'}
            words = re.findall(r'\b\w+\b', title.lower())
            return [word for word in words if word not in common_words and len(word) > 2]
        
        words1 = set(normalize_title(title1))
        words2 = set(normalize_title(title2))
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def __eq__(self, other) -> bool:
        """
        Check if two bikes are equal based on their href (unique identifier).
        
        Args:
            other: Another Bike object to compare
            
        Returns:
            True if bikes have the same href
        """
        if not isinstance(other, Bike):
            return False
        return self.href == other.href
    
    def __hash__(self) -> int:
        """
        Hash function for Bike objects based on href.
        
        Returns:
            Hash value
        """
        return hash(self.href)
    
    def __str__(self) -> str:
        """
        String representation of the bike.
        
        Returns:
            Formatted string with bike details
        """
        return f"Bike: {self.title} - {self.price} - {self.location}"
    
    def __repr__(self) -> str:
        """
        Detailed string representation for debugging.
        
        Returns:
            Detailed string representation
        """
        return (f"Bike(title='{self.title}', price='{self.price}', "
                f"seller='{self.seller}', location='{self.location}', "
                f"href='{self.href}')")
