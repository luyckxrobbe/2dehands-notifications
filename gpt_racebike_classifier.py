#!/usr/bin/env python3
"""
GPT-based race bike classifier to filter out non-race bikes.
"""

import os
import logging
from typing import Optional, Dict, Any
from openai import OpenAI
from centralized_logging import get_logger

logger = get_logger(__name__)


class RaceBikeClassifier:
    """
    GPT-based classifier to determine if a bike is a race bike (koersfiets).
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the race bike classifier.
        
        Args:
            config: Configuration dictionary with GPT settings from centralized config
        """
        self.model = config.get('model', 'gpt-4o-mini')
        self.max_completion_tokens = config.get('max_completion_tokens', 10)
        self.temperature = config.get('temperature', 0.1)
        self.prompt_template = config.get('prompt', 
            "Is this a race bike (koersfiets) based on the title and description? Answer only 'YES' or 'NO'.")
        
        # Initialize OpenAI client
        self.client = None
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.client = OpenAI(api_key=api_key)
            logger.info(f"Race bike classifier initialized with model: {self.model}")
        else:
            logger.warning("OPENAI_API_KEY not found, race bike classifier will not work")
    
    def is_race_bike(self, title: str, description: str = None) -> bool:
        """
        Determine if a bike is a race bike using GPT.
        
        Args:
            title: Bike title
            description: Optional bike description
            
        Returns:
            True if it's a race bike, False otherwise
        """
        if not self.client:
            logger.warning("Race bike classifier not available (no API key), allowing all bikes")
            return True
        
        try:
            # Prepare the input text
            input_text = f"Title: {title}"
            if description:
                input_text += f"\nDescription: {description}"
            
            # Create the prompt
            prompt = f"{self.prompt_template}\n\n{input_text}"
            
            # Call GPT API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=self.max_completion_tokens,
                temperature=self.temperature
            )
            
            # Parse response
            result = response.choices[0].message.content.strip().upper()
            
            is_race_bike = result == 'YES'
            
            logger.debug(f"GPT classification for '{title[:50]}...': {result} -> {is_race_bike}")
            
            return is_race_bike
            
        except Exception as e:
            logger.error(f"Error in race bike classification: {e}")
            # On error, allow the bike through (fail open)
            return True
    
    def classify_bike(self, bike_data: Dict[str, Any]) -> bool:
        """
        Classify a bike using title and description from bike data.
        
        Args:
            bike_data: Dictionary containing bike information
            
        Returns:
            True if it's a race bike, False otherwise
        """
        title = bike_data.get('title', '')
        description = bike_data.get('description', '')
        
        return self.is_race_bike(title, description)


def create_classifier_from_centralized_config() -> RaceBikeClassifier:
    """
    Create a race bike classifier using the centralized configuration.
    
    Returns:
        Configured RaceBikeClassifier instance
    """
    from centralized_logging import CentralizedLogger
    
    # Load centralized config
    centralized_config = CentralizedLogger.load_centralized_config()
    gpt_config = centralized_config.get('racebike_check_gpt', {})
    
    return RaceBikeClassifier(gpt_config)
