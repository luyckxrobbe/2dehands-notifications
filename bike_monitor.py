#!/usr/bin/env python3
"""
Continuous bike monitoring system that checks for new listings every minute
and sends Telegram notifications for new bikes.
"""

import asyncio
import argparse
import json
import logging
import os
import signal
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from scrape_2dehands_live import scrape_bikes
from current_listings import CurrentListings
from bike import Bike
from telegram_bot import TelegramBot
from listing_scraper import ListingScraper

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bike_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class BikeMonitor:
    """
    Continuous bike monitoring system that checks for new listings and sends notifications.
    """
    
    def __init__(self, config: Dict[str, Any], skip_initial: bool = False):
        """
        Initialize the bike monitor from configuration.
        
        Args:
            config: Configuration dictionary with monitor settings
            skip_initial: If True, skip the initial buffer building phase
        """
        self.url = config['url']
        self.check_interval = config['check_interval']
        self.max_bikes = config['max_bikes']
        self.initial_pages = config['initial_pages']
        self.ongoing_pages = config['ongoing_pages']
        
        # Handle backup file - if empty string or None, disable backup
        backup_file = config['backup_file']
        if backup_file and backup_file.strip():
            self.backup_file = Path(backup_file)
        else:
            self.backup_file = None
            
        self.log_file = config['log_file']
        
        # Proxy configuration (optional)
        self.proxies = config.get('proxies', [])
        self.request_delay = config.get('request_delay', 1.0)
        
        self.running = False
        
        # Try to load existing buffer from backup file
        if self.backup_file and self.backup_file.exists():
            try:
                self.previous_listings = CurrentListings.from_json_file(self.backup_file, max_bikes=self.max_bikes)
                logger.info(f"Loaded existing buffer with {len(self.previous_listings)} bikes from {self.backup_file}")
            except Exception as e:
                logger.warning(f"Could not load existing buffer: {e}")
                self.previous_listings = CurrentListings(max_bikes=self.max_bikes)
        else:
            self.previous_listings = CurrentListings(max_bikes=self.max_bikes)  # Rolling window of bikes
        
        # Initialize Telegram bot
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
        
        self.telegram_bot = TelegramBot(bot_token)
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID not found in environment variables")
        
        # Initialize listing scraper for detailed information
        self.listing_scraper = None
        self.is_initial_run = not skip_initial  # Track if this is the first run
        
        logger.info(f"BikeMonitor initialized for URL: {self.url}")
        logger.info(f"Check interval: {self.check_interval} seconds")
        logger.info(f"Rolling window: {self.max_bikes} bikes")
        logger.info(f"Initial pages: {self.initial_pages} (for buffer filling)")
        logger.info(f"Ongoing pages: {self.ongoing_pages} (for monitoring)")
        if self.backup_file:
            logger.info(f"Backup file: {self.backup_file}")
        else:
            logger.info("Backup file: disabled")
        logger.info(f"Log file: {self.log_file}")
        logger.info(f"Telegram chat ID: {self.chat_id}")
        if skip_initial:
            if self.backup_file and self.backup_file.exists():
                logger.info("Initial buffer building: SKIPPED (using existing buffer)")
            else:
                logger.warning("Initial buffer building: SKIPPED but no backup file found - will start with empty buffer")
        else:
            logger.info("Initial buffer building: ENABLED")
    
    def format_bike_message(self, bike: Bike, detailed_info: Optional[Dict[str, Any]] = None) -> str:
        """
        Format a bike listing into a nice Telegram message.
        
        Args:
            bike: Bike object to format
            detailed_info: Optional detailed information from listing scraper
            
        Returns:
            Formatted message string
        """
        # Extract key information
        brand = bike.get_brand() or "Unknown Brand"
        condition = bike.get_condition() or "Unknown Condition"
        frame_size = bike.get_frame_size() or "Unknown Size"
        numeric_price = bike.get_numeric_price()
        
        # Format price
        if numeric_price:
            price_str = f"€ {numeric_price:,.2f}".replace(',', ' ')
        else:
            price_str = bike.price
        
        # Check if it's from today if we have detailed info
        is_today = False
        if detailed_info and detailed_info.get('date_posted'):
            scraper = ListingScraper(
                headless=True,
                proxies=self.proxies if self.proxies else None,
                request_delay=self.request_delay
            )
            is_today = scraper.is_today(detailed_info['date_posted'])
        
        # Create message with today indicator
        today_indicator = " 🆕" if is_today else ""
        message = f"🚴‍♂️ <b>New Bike Listing!</b>{today_indicator}\n\n"
        message += f"<b>Title:</b> {bike.title}\n"
        message += f"<b>Brand:</b> {brand}\n"
        message += f"<b>Price:</b> {price_str}\n"
        message += f"<b>Condition:</b> {condition}\n"
        message += f"<b>Size:</b> {frame_size}\n"
        message += f"<b>Location:</b> {bike.location}\n"
        message += f"<b>Seller:</b> {bike.seller}\n"
        message += f"<b>Date:</b> {bike.date}\n\n"
        
        # Add detailed specifications if available
        if detailed_info and detailed_info.get('specifications'):
            specs = detailed_info['specifications']
            if specs:
                message += "<b>Specifications:</b>\n"
                for key, value in list(specs.items())[:5]:  # Show first 5 specs
                    # Convert key to readable format
                    readable_key = key.replace('_', ' ').title()
                    message += f"• {readable_key}: {value}\n"
                message += "\n"
        
        # Add description (prefer detailed description if available)
        description = ""
        if detailed_info and detailed_info.get('description'):
            description = detailed_info['description']
        elif bike.description:
            description = bike.description
        
        if description:
            desc = description[:300] + "..." if len(description) > 300 else description
            message += f"<b>Description:</b> {desc}\n\n"
        
        # Add seller info if available
        if detailed_info and detailed_info.get('seller'):
            seller = detailed_info['seller']
            if seller.get('type'):
                message += f"<b>Seller Type:</b> {seller['type']}\n"
            if seller.get('years_on_platform'):
                message += f"<b>Years on Platform:</b> {seller['years_on_platform']}\n"
            message += "\n"
        
        # Add stats if available
        if detailed_info and detailed_info.get('stats'):
            stats = detailed_info['stats']
            if stats.get('views'):
                message += f"👁️ {stats['views']} views"
            if stats.get('favorites'):
                message += f" ❤️ {stats['favorites']} favorites"
            if stats.get('views') or stats.get('favorites'):
                message += "\n\n"
        
        # Add link
        message += f"🔗 <a href='{bike.href}'>View Listing</a>"
        
        return message
    
    async def check_and_send_bike_notification(self, bike: Bike) -> bool:
        """
        Check if a bike is from today and send notification only if it is.
        Includes retry logic when date cannot be determined.
        
        Args:
            bike: Bike object to check and potentially send notification for
            
        Returns:
            True if notification sent successfully, False if not from today or error
        """
        max_retries = 2  # Try up to 2 times (initial attempt + 1 retry)
        
        for attempt in range(max_retries):
            try:
                detailed_info = None
                
                # Try to get detailed information from the listing page
                try:
                    if not self.listing_scraper:
                        self.listing_scraper = ListingScraper(
                            headless=True,
                            proxies=self.proxies if self.proxies else None,
                            request_delay=self.request_delay
                        )
                        await self.listing_scraper.__aenter__()
                    
                    if attempt == 0:
                        logger.info(f"Scraping detailed info for: {bike.title}")
                    else:
                        logger.info(f"Retrying to scrape detailed info for: {bike.title} (attempt {attempt + 1})")
                    
                    detailed_info = await self.listing_scraper.scrape_listing(bike.href)
                    
                    # Check if it's from today
                    if detailed_info and detailed_info.get('date_posted'):
                        scraper = ListingScraper(
                            headless=True,
                            proxies=self.proxies if self.proxies else None,
                            request_delay=self.request_delay
                        )
                        is_today = scraper.is_today(detailed_info['date_posted'])
                        
                        if is_today:
                            logger.info(f"Bike is from today - sending notification: {bike.title}")
                            
                            # Format message with detailed info
                            message = self.format_bike_message(bike, detailed_info)
                            
                            # Send message with HTML parsing
                            success = await self.telegram_bot.send_message(
                                chat_id=self.chat_id,
                                message=message,
                                parse_mode='HTML'
                            )
                            
                            if success:
                                logger.info(f"Notification sent for today's bike: {bike.title}")
                            else:
                                logger.error(f"Failed to send notification for bike: {bike.title}")
                            
                            return success
                        else:
                            logger.info(f"Bike is not from today - skipping notification: {bike.title}")
                            return False
                    else:
                        if attempt < max_retries - 1:
                            logger.warning(f"Could not determine date for bike: {bike.title} - retrying in 2 seconds...")
                            await asyncio.sleep(2)  # Wait 2 seconds before retry
                            continue
                        else:
                            logger.warning(f"Could not determine date for bike after {max_retries} attempts: {bike.title}")
                            return False
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Could not scrape detailed info for {bike.title}: {e} - retrying in 2 seconds...")
                        await asyncio.sleep(2)  # Wait 2 seconds before retry
                        continue
                    else:
                        logger.warning(f"Could not scrape detailed info for {bike.title} after {max_retries} attempts: {e}")
                        return False
                
            except Exception as e:
                logger.error(f"Error checking/sending notification for bike {bike.title}: {e}")
                return False
        
        return False
    
    async def check_for_new_listings(self) -> None:
        """
        Check for new listings and send notifications only for bikes posted today.
        """
        try:
            # Determine how many pages to scrape
            if self.is_initial_run:
                pages_to_scrape = self.initial_pages
                logger.info(f"Starting initial bike listing check (reading {pages_to_scrape} pages)...")
            else:
                pages_to_scrape = self.ongoing_pages
                logger.info(f"Starting ongoing bike listing check (reading {pages_to_scrape} pages)...")
            
            # Scrape current listings directly as objects
            current_listings = await scrape_bikes(
                url=self.url, 
                headless=True, 
                max_pages=pages_to_scrape,
                proxies=self.proxies if self.proxies else None,
                request_delay=self.request_delay
            )
            
            # Use rolling window logic to find truly new bikes
            if len(self.previous_listings) > 0:
                initial_new_count = len([bike for bike in current_listings.bikes if bike not in self.previous_listings.bikes])
                truly_new_bikes = self.previous_listings.update_with_new_listings(current_listings)
                
                logger.info(f"Scraped {len(current_listings)} total listings")
                logger.info(f"Found {initial_new_count} listings not in rolling window")
                logger.info(f"After duplicate detection: {len(truly_new_bikes)} truly new listings")
                
                # Check each new bike and only send notifications for today's listings
                notifications_sent = 0
                for bike in truly_new_bikes:
                    # This method will check if it's from today and only send if it is
                    success = await self.check_and_send_bike_notification(bike)
                    if success:
                        notifications_sent += 1
                    
                    # Small delay between checks to avoid rate limiting
                    await asyncio.sleep(2)
                
                if notifications_sent > 0:
                    logger.info(f"Sent {notifications_sent} notifications for today's listings")
                else:
                    logger.info("No new listings from today found")
            else:
                if self.is_initial_run:
                    logger.info(f"Initial run - building buffer with {len(current_listings)} listings from {pages_to_scrape} pages")
                else:
                    logger.info("First run - no previous listings to compare with")
                # On first run, just store all current listings
                self.previous_listings = current_listings
            
            # Mark initial run as complete
            if self.is_initial_run:
                self.is_initial_run = False
                logger.info("Initial buffer building complete - switching to ongoing monitoring mode")
            
            # Optional: backup to file for debugging
            if self.backup_file:
                self.previous_listings.to_json_file(self.backup_file)
                logger.debug(f"Backed up {len(self.previous_listings)} listings to {self.backup_file}")
            
            logger.info(f"Rolling window now contains {len(self.previous_listings)} bikes")
            logger.info("Bike listing check completed successfully")
            
        except Exception as e:
            logger.error(f"Error during bike listing check: {e}")
    
    async def run(self) -> None:
        """
        Start the continuous monitoring loop.
        """
        self.running = True
        logger.info("Starting bike monitor...")
        
        # Send startup notification
        startup_message = f"🚴‍♂️ <b>Enhanced Bike Monitor Started</b>\n\n"
        startup_message += f"Monitoring: {self.url}\n"
        startup_message += f"Check interval: {self.check_interval} seconds\n"
        startup_message += f"Buffer size: {self.max_bikes} bikes\n"
        if self.is_initial_run:
            startup_message += f"Initial scan: {self.initial_pages} pages\n"
        else:
            startup_message += f"Initial scan: SKIPPED (using existing buffer)\n"
        startup_message += f"Ongoing scan: {self.ongoing_pages} pages\n"
        startup_message += f"Mode: Only notify for listings posted TODAY\n"
        startup_message += f"Features: Detailed specs, seller info, view counts\n"
        startup_message += f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await self.telegram_bot.send_message(
            chat_id=self.chat_id,
            message=startup_message,
            parse_mode='HTML'
        )
        
        # Initial check
        await self.check_for_new_listings()
        
        # Main monitoring loop
        while self.running:
            try:
                await asyncio.sleep(self.check_interval)
                if self.running:  # Check again in case we were stopped during sleep
                    await self.check_for_new_listings()
            except asyncio.CancelledError:
                logger.info("Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                # Continue running even if there's an error
                await asyncio.sleep(10)  # Wait a bit before retrying
    
    def stop(self) -> None:
        """
        Stop the monitoring loop.
        """
        logger.info("Stopping bike monitor...")
        self.running = False
        
        # Clean up listing scraper if it exists
        if self.listing_scraper:
            try:
                asyncio.create_task(self.listing_scraper.__aexit__(None, None, None))
            except Exception as e:
                logger.warning(f"Error cleaning up listing scraper: {e}")


def load_config(config_file: Path) -> Dict[str, Any]:
    """
    Load configuration from JSON file.
    
    Args:
        config_file: Path to the JSON configuration file
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
        KeyError: If required configuration keys are missing
    """
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in config file {config_file}: {e}")
    
    # Validate required fields
    required_fields = ['url', 'check_interval', 'max_bikes', 'initial_pages', 'ongoing_pages', 'backup_file', 'log_file']
    missing_fields = [field for field in required_fields if field not in config]
    if missing_fields:
        raise KeyError(f"Missing required configuration fields: {missing_fields}")
    
    return config


async def main():
    """
    Main function to run the bike monitor.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Bike monitoring system with Telegram notifications")
    parser.add_argument("config", type=str, help="Path to JSON configuration file")
    parser.add_argument("--log-level", type=str, default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level (default: INFO)")
    parser.add_argument("--skip-initial", action="store_true",
                       help="Skip the initial buffer building phase and go straight to ongoing monitoring")
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(Path(args.config))
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)
    
    # Configure logging
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config['log_file']),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Check required environment variables
    required_env_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file or environment")
        sys.exit(1)
    
    # Create monitor
    try:
        monitor = BikeMonitor(config, skip_initial=args.skip_initial)
    except ValueError as e:
        print(f"Error initializing monitor: {e}")
        sys.exit(1)
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        monitor.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Run the monitor
        await monitor.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        monitor.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        monitor.stop()
    
    # Send shutdown notification
    shutdown_message = f"🚴‍♂️ <b>Enhanced Bike Monitor Stopped</b>\n\n"
    shutdown_message += f"URL: {config['url']}\n"
    shutdown_message += f"Mode: Only notified for today's listings\n"
    shutdown_message += f"Stopped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    try:
        await monitor.telegram_bot.send_message(
            chat_id=monitor.chat_id,
            message=shutdown_message,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error sending shutdown notification: {e}")


if __name__ == "__main__":
    # Run the monitor
    asyncio.run(main())
