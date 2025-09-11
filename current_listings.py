#!/usr/bin/env python3
"""
CurrentListings class for managing collections of bike listings.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Set, Optional
from datetime import datetime
from bike import Bike


class CurrentListings:
    """
    Manages a collection of bike listings with methods for comparison and persistence.
    """
    
    def __init__(self, bikes: Optional[List[Bike]] = None, max_bikes: int = 300):
        """
        Initialize CurrentListings with an optional list of bikes.
        
        Args:
            bikes: Optional list of Bike objects to initialize with
            max_bikes: Maximum number of bikes to keep in rolling window
        """
        self.bikes: List[Bike] = bikes or []
        self.max_bikes = max_bikes
        self._last_updated = datetime.now()
        
        # Ensure we don't exceed max_bikes
        self._enforce_max_bikes()
    
    @classmethod
    def from_json_file(cls, file_path: Path, max_bikes: int = 300) -> 'CurrentListings':
        """
        Load CurrentListings from a JSON file.
        
        Args:
            file_path: Path to the JSON file containing bike data
            max_bikes: Maximum number of bikes to keep in rolling window
            
        Returns:
            CurrentListings instance loaded from file
        """
        if not file_path.exists():
            return cls(max_bikes=max_bikes)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            bikes = []
            for item in data:
                if isinstance(item, dict):
                    bikes.append(Bike.from_dict(item))
            
            return cls(bikes, max_bikes=max_bikes)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error loading from {file_path}: {e}")
            return cls(max_bikes=max_bikes)
    
    @classmethod
    def from_list(cls, bike_data: List[Dict[str, Any]], max_bikes: int = 300) -> 'CurrentListings':
        """
        Create CurrentListings from a list of bike dictionaries.
        
        Args:
            bike_data: List of dictionaries containing bike data
            max_bikes: Maximum number of bikes to keep in rolling window
            
        Returns:
            CurrentListings instance
        """
        bikes = [Bike.from_dict(item) for item in bike_data]
        return cls(bikes, max_bikes=max_bikes)
    
    def _enforce_max_bikes(self) -> None:
        """
        Ensure we don't exceed max_bikes by removing oldest bikes.
        """
        if len(self.bikes) > self.max_bikes:
            # Sort by scraped_at timestamp and keep the most recent ones
            self.bikes.sort(key=lambda b: b._scraped_at, reverse=True)
            self.bikes = self.bikes[:self.max_bikes]
    
    def add_bike(self, bike: Bike) -> None:
        """
        Add a single bike to the collection.
        
        Args:
            bike: Bike object to add
        """
        if bike not in self.bikes:
            self.bikes.append(bike)
            self._enforce_max_bikes()
            self._last_updated = datetime.now()
    
    def add_bikes(self, bikes: List[Bike]) -> None:
        """
        Add multiple bikes to the collection.
        
        Args:
            bikes: List of Bike objects to add
        """
        for bike in bikes:
            self.add_bike(bike)
    
    def update_with_new_listings(self, new_listings: 'CurrentListings') -> List[Bike]:
        """
        Update this collection with new listings and return truly new bikes.
        This method implements the rolling window logic to prevent false positives.
        Now includes comprehensive duplicate detection within the newly found bikes.
        
        Args:
            new_listings: CurrentListings object with newly scraped bikes
            
        Returns:
            List of truly new bikes (not in our rolling window and not duplicates)
        """
        # First, filter out bikes that are already in our rolling window
        bikes_not_in_window = []
        for bike in new_listings.bikes:
            if bike not in self.bikes:
                bikes_not_in_window.append(bike)
        
        # Second, remove duplicates within the newly found bikes
        truly_new_bikes = []
        duplicates_found = 0
        
        for i, bike in enumerate(bikes_not_in_window):
            is_duplicate = False
            
            # Check against bikes already in our window
            for existing_bike in self.bikes:
                if bike.is_duplicate_of(existing_bike):
                    is_duplicate = True
                    duplicates_found += 1
                    break
            
            # Check against other newly found bikes (to avoid duplicates within the new batch)
            if not is_duplicate:
                for j, other_new_bike in enumerate(bikes_not_in_window):
                    if i != j and bike.is_duplicate_of(other_new_bike):
                        is_duplicate = True
                        duplicates_found += 1
                        break
            
            if not is_duplicate:
                truly_new_bikes.append(bike)
        
        # Log duplicate detection results
        if duplicates_found > 0:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Duplicate detection: Found {duplicates_found} duplicates out of {len(bikes_not_in_window)} new bikes")
        
        # Don't add bikes to cache yet - let the caller decide when to add them
        # This prevents bikes from being added to cache before notifications are sent
        
        return truly_new_bikes
    
    def remove_bike(self, bike: Bike) -> bool:
        """
        Remove a bike from the collection.
        
        Args:
            bike: Bike object to remove
            
        Returns:
            True if bike was removed, False if not found
        """
        if bike in self.bikes:
            self.bikes.remove(bike)
            self._last_updated = datetime.now()
            return True
        return False
    
    def get_bike_by_href(self, href: str) -> Optional[Bike]:
        """
        Get a bike by its href (unique identifier).
        
        Args:
            href: The href of the bike to find
            
        Returns:
            Bike object if found, None otherwise
        """
        for bike in self.bikes:
            if bike.href == href:
                return bike
        return None
    
    def get_new_listings(self, other_listings: 'CurrentListings') -> List[Bike]:
        """
        Get bikes that are new compared to another CurrentListings instance.
        
        Args:
            other_listings: CurrentListings to compare against
            
        Returns:
            List of new Bike objects
        """
        other_hrefs = {bike.href for bike in other_listings.bikes}
        new_bikes = []
        
        for bike in self.bikes:
            if bike.href not in other_hrefs:
                new_bikes.append(bike)
        
        return new_bikes
    
    def get_removed_listings(self, other_listings: 'CurrentListings') -> List[Bike]:
        """
        Get bikes that were removed compared to another CurrentListings instance.
        
        Args:
            other_listings: CurrentListings to compare against
            
        Returns:
            List of removed Bike objects
        """
        current_hrefs = {bike.href for bike in self.bikes}
        removed_bikes = []
        
        for bike in other_listings.bikes:
            if bike.href not in current_hrefs:
                removed_bikes.append(bike)
        
        return removed_bikes
    
    def get_updated_listings(self, other_listings: 'CurrentListings') -> List[Bike]:
        """
        Get bikes that have been updated (price, description, etc.) compared to another instance.
        
        Args:
            other_listings: CurrentListings to compare against
            
        Returns:
            List of updated Bike objects
        """
        updated_bikes = []
        other_bikes_dict = {bike.href: bike for bike in other_listings.bikes}
        
        for bike in self.bikes:
            if bike.href in other_bikes_dict:
                other_bike = other_bikes_dict[bike.href]
                # Check if any important fields have changed
                if (bike.price != other_bike.price or 
                    bike.description != other_bike.description or
                    bike.attributes != other_bike.attributes):
                    updated_bikes.append(bike)
        
        return updated_bikes
    
    def compare_with(self, other_listings: 'CurrentListings') -> Dict[str, List[Bike]]:
        """
        Compare this CurrentListings with another and return all differences.
        
        Args:
            other_listings: CurrentListings to compare against
            
        Returns:
            Dictionary with 'new', 'removed', and 'updated' lists
        """
        return {
            'new': self.get_new_listings(other_listings),
            'removed': self.get_removed_listings(other_listings),
            'updated': self.get_updated_listings(other_listings)
        }
    
    def filter_by_price_range(self, min_price: Optional[float] = None, 
                             max_price: Optional[float] = None) -> 'CurrentListings':
        """
        Filter bikes by price range.
        
        Args:
            min_price: Minimum price (inclusive)
            max_price: Maximum price (inclusive)
            
        Returns:
            New CurrentListings instance with filtered bikes
        """
        filtered_bikes = []
        
        for bike in self.bikes:
            price = bike.get_numeric_price()
            if price is None:  # Skip bikes with no price or "Bieden"
                continue
            
            if min_price is not None and price < min_price:
                continue
            if max_price is not None and price > max_price:
                continue
            
            filtered_bikes.append(bike)
        
        return CurrentListings(filtered_bikes)
    
    def filter_by_condition(self, conditions: List[str]) -> 'CurrentListings':
        """
        Filter bikes by condition.
        
        Args:
            conditions: List of condition strings to filter by
            
        Returns:
            New CurrentListings instance with filtered bikes
        """
        filtered_bikes = []
        conditions_lower = [c.lower() for c in conditions]
        
        for bike in self.bikes:
            bike_condition = bike.get_condition()
            if bike_condition and bike_condition.lower() in conditions_lower:
                filtered_bikes.append(bike)
        
        return CurrentListings(filtered_bikes)
    
    def filter_by_brand(self, brands: List[str]) -> 'CurrentListings':
        """
        Filter bikes by brand.
        
        Args:
            brands: List of brand names to filter by
            
        Returns:
            New CurrentListings instance with filtered bikes
        """
        filtered_bikes = []
        brands_lower = [b.lower() for b in brands]
        
        for bike in self.bikes:
            bike_brand = bike.get_brand()
            if bike_brand and bike_brand.lower() in brands_lower:
                filtered_bikes.append(bike)
        
        return CurrentListings(filtered_bikes)
    
    def filter_by_location(self, locations: List[str]) -> 'CurrentListings':
        """
        Filter bikes by location.
        
        Args:
            locations: List of location strings to filter by
            
        Returns:
            New CurrentListings instance with filtered bikes
        """
        filtered_bikes = []
        locations_lower = [l.lower() for l in locations]
        
        for bike in self.bikes:
            if bike.location and bike.location.lower() in locations_lower:
                filtered_bikes.append(bike)
        
        return CurrentListings(filtered_bikes)
    
    def sort_by_price(self, ascending: bool = True) -> 'CurrentListings':
        """
        Sort bikes by price.
        
        Args:
            ascending: If True, sort from lowest to highest price
            
        Returns:
            New CurrentListings instance with sorted bikes
        """
        def get_sort_key(bike: Bike) -> float:
            price = bike.get_numeric_price()
            return price if price is not None else float('inf')
        
        sorted_bikes = sorted(self.bikes, key=get_sort_key, reverse=not ascending)
        return CurrentListings(sorted_bikes)
    
    def to_json_file(self, file_path: Path) -> None:
        """
        Save CurrentListings to a JSON file.
        
        Args:
            file_path: Path where to save the JSON file
        """
        data = [bike.to_dict() for bike in self.bikes]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def to_list(self) -> List[Dict[str, Any]]:
        """
        Convert CurrentListings to a list of dictionaries.
        
        Returns:
            List of bike dictionaries
        """
        return [bike.to_dict() for bike in self.bikes]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current listings.
        
        Returns:
            Dictionary with various statistics
        """
        total_bikes = len(self.bikes)
        bikes_with_price = sum(1 for bike in self.bikes if bike.get_numeric_price() is not None)
        bikes_without_price = total_bikes - bikes_with_price
        
        # Price statistics
        prices = [bike.get_numeric_price() for bike in self.bikes if bike.get_numeric_price() is not None]
        avg_price = sum(prices) / len(prices) if prices else 0
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        
        # Brand statistics
        brands = {}
        for bike in self.bikes:
            brand = bike.get_brand()
            if brand:
                brands[brand] = brands.get(brand, 0) + 1
        
        # Condition statistics
        conditions = {}
        for bike in self.bikes:
            condition = bike.get_condition()
            if condition:
                conditions[condition] = conditions.get(condition, 0) + 1
        
        return {
            'total_bikes': total_bikes,
            'bikes_with_price': bikes_with_price,
            'bikes_without_price': bikes_without_price,
            'average_price': round(avg_price, 2),
            'min_price': min_price,
            'max_price': max_price,
            'brands': brands,
            'conditions': conditions,
            'last_updated': self._last_updated.isoformat()
        }
    
    def __len__(self) -> int:
        """
        Return the number of bikes in the collection.
        
        Returns:
            Number of bikes
        """
        return len(self.bikes)
    
    def __iter__(self):
        """
        Make CurrentListings iterable.
        
        Returns:
            Iterator over bikes
        """
        return iter(self.bikes)
    
    def __str__(self) -> str:
        """
        String representation of CurrentListings.
        
        Returns:
            Formatted string with listing count
        """
        return f"CurrentListings({len(self.bikes)} bikes)"
    
    def __repr__(self) -> str:
        """
        Detailed string representation for debugging.
        
        Returns:
            Detailed string representation
        """
        return f"CurrentListings(bikes={len(self.bikes)}, last_updated={self._last_updated})"
