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
from datetime import datetime, time
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from scrape_2dehands_live import scrape_bikes
from scrape_2dehands_pi import scrape_bikes_pi
from current_listings import CurrentListings
from bike import Bike
from bike_minimal import BikeMinimal, BikeMinimalListings
from telegram_bot import TelegramBot
from listing_scraper import ListingScraper
from listing_scraper_pi import ListingScraperPi
from centralized_logging import setup_logging, get_logger
from gpt_racebike_classifier import create_classifier_from_centralized_config

# Load environment variables
load_dotenv()

# Set up centralized logging
setup_logging(log_file='bike_monitor.log')
logger = get_logger(__name__)


class BikeMonitor:
    """
    Continuous bike monitoring system that checks for new listings and sends notifications.
    """
    
    def __init__(self, config: Dict[str, Any], skip_initial: bool = False, centralized: bool = False):
        """
        Initialize the bike monitor from configuration.
        
        Args:
            config: Configuration dictionary with monitor settings
            skip_initial: If True, skip the initial buffer building phase
            centralized: If True, run in centralized mode (wait for signals)
        """
        self.url = config['url']
        # In centralized mode, check_interval is not needed as timing is handled centrally
        if centralized:
            self.check_interval = 300  # Default value, not used in centralized mode
            self.time_based_intervals = {}  # Not used in centralized mode
        else:
            self.check_interval = config['check_interval']
            self.time_based_intervals = config.get('time_based_intervals', {})
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
        
        # Race bike classifier - only enable if specified in config
        self.race_bike_classifier = None
        enable_gpt_check = config.get('enable_gpt_racebike_check', False)
        if enable_gpt_check:
            self.race_bike_classifier = create_classifier_from_centralized_config()
            logger.info("GPT race bike classifier enabled (configured in config file)")
        else:
            logger.info("GPT race bike classifier disabled (not enabled in config file)")
        
        # Pi optimization settings
        self.pi_optimized = config.get('pi_optimized', False)
        self.request_delay = config.get('request_delay', self.request_delay)
        
        self.running = False
        self.centralized = centralized
        
        # Try to load existing minimal buffer from backup file
        if self.backup_file and self.backup_file.exists():
            try:
                logger.info(f"🔄 Loading existing minimal buffer from {self.backup_file}...")
                self.previous_listings_minimal = BikeMinimalListings.from_json_file(self.backup_file, max_bikes=self.max_bikes)
                logger.info(f"✅ Successfully loaded minimal buffer with {len(self.previous_listings_minimal)} bikes from backup")
                
                # Show some buffer statistics
                if len(self.previous_listings_minimal) > 0:
                    # Get a sample of recent bikes
                    recent_bikes = sorted(self.previous_listings_minimal.bikes, key=lambda b: b._scraped_at, reverse=True)[:3]
                    logger.info(f"📊 Buffer contains bikes from {recent_bikes[-1]._scraped_at.strftime('%Y-%m-%d %H:%M')} to {recent_bikes[0]._scraped_at.strftime('%Y-%m-%d %H:%M')}")
                    logger.info(f"🔗 Sample recent bikes:")
                    for i, bike in enumerate(recent_bikes, 1):
                        logger.info(f"   {i}. {bike.title[:60]}... (€{bike.price})")
                else:
                    logger.warning("⚠️  Loaded buffer is empty")
                    
            except Exception as e:
                logger.error(f"❌ Could not load existing buffer from {self.backup_file}: {e}")
                logger.info("🆕 Starting with empty buffer")
                self.previous_listings_minimal = BikeMinimalListings(max_bikes=self.max_bikes)
        else:
            if self.backup_file:
                logger.info(f"📁 Backup file {self.backup_file} does not exist")
            else:
                logger.info("📁 No backup file configured")
            logger.info("🆕 Starting with empty buffer")
            self.previous_listings_minimal = BikeMinimalListings(max_bikes=self.max_bikes)  # Rolling window of minimal bikes
        
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
        
        logger.info(f"🚴‍♂️ BikeMonitor initialized for URL: {self.url}")
        
        if self.time_based_intervals:
            logger.info(f"⏰ Time-based intervals configured:")
            for time_range, interval in self.time_based_intervals.items():
                logger.info(f"   • {time_range}: {interval/60:.0f} minutes ({interval} seconds)")
            logger.info(f"⏰ Default interval: {self.check_interval} seconds")
        else:
            logger.info(f"⏰ Check interval: {self.check_interval} seconds")
        
        logger.info(f"🪟 Rolling window: {self.max_bikes} bikes")
        logger.info(f"📄 Initial pages: {self.initial_pages} (for buffer filling)")
        logger.info(f"📄 Ongoing pages: {self.ongoing_pages} (for monitoring)")
        if self.backup_file:
            logger.info(f"💾 Backup file: {self.backup_file}")
        else:
            logger.info("💾 Backup file: disabled")
        logger.info(f"📝 Log file: {self.log_file}")
        logger.info(f"📱 Telegram chat ID: {self.chat_id}")
        
        # Show buffer status
        if len(self.previous_listings_minimal) > 0:
            logger.info(f"🧠 Buffer status: {len(self.previous_listings_minimal)} bikes loaded and ready")
        else:
            logger.info("🧠 Buffer status: Empty - will build buffer on first run")
            
        if skip_initial:
            if self.backup_file and self.backup_file.exists():
                logger.info("🏗️  Initial buffer building: SKIPPED (using existing buffer)")
            else:
                logger.warning("🏗️  Initial buffer building: SKIPPED but no backup file found - will start with empty buffer")
        else:
            logger.info("🏗️  Initial buffer building: ENABLED")
    
    def get_current_interval(self) -> int:
        """
        Get the current check interval based on the time of day.
        
        Returns:
            Interval in seconds
        """
        if not self.time_based_intervals:
            return self.check_interval
        
        current_time = datetime.now().time()
        
        for time_range, interval in self.time_based_intervals.items():
            start_str, end_str = time_range.split('-')
            start_time = time.fromisoformat(start_str)
            end_time = time.fromisoformat(end_str)
            
            # Handle the case where the range crosses midnight (e.g., 16:00-00:00)
            if start_time <= end_time:
                # Normal range (e.g., 07:00-16:00)
                if start_time <= current_time <= end_time:
                    return interval
            else:
                # Range crosses midnight (e.g., 16:00-00:00)
                if current_time >= start_time or current_time <= end_time:
                    return interval
        
        # Fallback to default interval if no time range matches
        return self.check_interval
    
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
            # Use Pi-optimized scraper if in Pi mode
            if self.pi_optimized:
                scraper = ListingScraperPi(
                    headless=True,
                    proxies=self.proxies if self.proxies else None,
                    request_delay=self.request_delay
                )
            else:
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
        # Format date with time - use the actual listing posting time if available
        date_display = bike.date  # fallback to search results date
        if detailed_info and detailed_info.get('date_posted'):
            try:
                # Parse the ISO date from the individual listing page
                from datetime import datetime
                listing_datetime = datetime.fromisoformat(detailed_info['date_posted'].replace('Z', '+00:00'))
                # Format as readable date and time
                date_display = listing_datetime.strftime('%d/%m/%Y %H:%M')
            except Exception as e:
                logger.debug(f"Could not parse date_posted '{detailed_info['date_posted']}': {e}")
                # Fallback to search results date with scraped time
                try:
                    time_str = bike._scraped_at.strftime('%H:%M')
                    date_display = f"{bike.date}, {time_str}"
                except Exception:
                    pass
        else:
            # No detailed info available, use search results date with scraped time
            try:
                time_str = bike._scraped_at.strftime('%H:%M')
                date_display = f"{bike.date}, {time_str}"
            except Exception:
                pass
        
        message += f"<b>Date Posted:</b> {date_display}\n\n"
        
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
        # Safety check: don't process bikes that are already in our minimal cache
        bike_minimal = BikeMinimal(bike.title, bike.price, bike.href, bike._scraped_at)
        if bike_minimal in self.previous_listings_minimal.bikes:
            logger.warning(f"Bike {bike.title} is already in cache - skipping notification check")
            return False
        
        max_retries = 2  # Try up to 2 times (initial attempt + 1 retry)
        
        for attempt in range(max_retries):
            try:
                detailed_info = None
                
                # Try to get detailed information from the listing page
                try:
                    if not self.listing_scraper:
                        # Use Pi-optimized scraper if in Pi mode
                        if self.pi_optimized:
                            self.listing_scraper = ListingScraperPi(
                                headless=True,
                                proxies=self.proxies if self.proxies else None,
                                request_delay=self.request_delay
                            )
                        else:
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
                        logger.debug(f"Found date_posted for {bike.title}: {detailed_info['date_posted']}")
                    else:
                        logger.debug(f"No date_posted found for {bike.title}. Detailed info keys: {list(detailed_info.keys()) if detailed_info else 'None'}")
                    
                    # Use scraped_at timestamp instead of unreliable website date
                    # Check if bike was scraped today (more reliable than website date)
                    is_today = bike.is_scraped_today()
                    
                    if is_today:
                        # Check if seller is a business seller
                        seller_type = None
                        if detailed_info and detailed_info.get('seller'):
                            seller_type = detailed_info['seller'].get('type', '').strip()
                        
                        if seller_type and seller_type.lower() == "zakelijke verkoper":
                            logger.info(f"Bike is from business seller - skipping notification: {bike.title}")
                            return False
                        
                        # Check if it's actually a race bike using GPT (only for sportfietsen configs)
                        if self.race_bike_classifier:
                            is_race_bike = self.race_bike_classifier.classify_bike({
                                'title': bike.title,
                                'description': detailed_info.get('description', '')
                            })
                            
                            if not is_race_bike:
                                logger.info(f"Bike is not a race bike according to GPT - skipping notification: {bike.title}")
                                return False
                        
                        logger.info(f"Bike is from today and is a race bike - sending notification: {bike.title}")
                        
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
    
    def save_backup(self) -> None:
        """
        Save the current minimal buffer to backup file.
        This should be called when new listings are found to ensure data persistence.
        """
        if self.backup_file:
            try:
                self.previous_listings_minimal.to_json_file(self.backup_file)
                logger.info(f"💾 Backed up {len(self.previous_listings_minimal)} minimal listings to {self.backup_file}")
                logger.debug(f"📁 Backup file size: {self.backup_file.stat().st_size / 1024 / 1024:.2f} MB")
            except Exception as e:
                logger.error(f"❌ Failed to save backup: {e}")
        else:
            logger.debug("No backup file configured - skipping backup")
    
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
            if self.pi_optimized:
                current_listings = await scrape_bikes_pi(
                    url=self.url, 
                    max_pages=pages_to_scrape,
                    proxies=self.proxies if self.proxies else None,
                    request_delay=self.request_delay
                )
            else:
                current_listings = await scrape_bikes(
                    url=self.url, 
                    headless=True, 
                    max_pages=pages_to_scrape,
                    proxies=self.proxies if self.proxies else None,
                    request_delay=self.request_delay
                )
            
            # Use rolling window logic to find truly new bikes
            if len(self.previous_listings_minimal) > 0:
                # Convert current listings to minimal format for comparison
                current_minimal = [BikeMinimal(bike.title, bike.price, bike.href, bike._scraped_at) for bike in current_listings.bikes]
                initial_new_count = len([bike for bike in current_minimal if bike not in self.previous_listings_minimal.bikes])
                truly_new_minimal = [bike for bike in current_minimal if bike not in self.previous_listings_minimal.bikes]
                
                logger.info(f"Scraped {len(current_listings)} total listings")
                logger.info(f"Found {initial_new_count} listings not in rolling window")
                logger.info(f"After duplicate detection: {len(truly_new_minimal)} truly new listings")
                
                # Check if we found too many new bikes (monitor was likely offline)
                if len(truly_new_minimal) > 20:
                    logger.info(f"Found {len(truly_new_minimal)} new bikes (>20) - monitor was likely offline. Adding all to buffer without notifications.")
                    # Just add all bikes to minimal cache without processing notifications
                    self.previous_listings_minimal.add_bikes(truly_new_minimal)
                    logger.info(f"Added {len(truly_new_minimal)} bikes to minimal buffer (no notifications sent)")
                    # Save backup since we found new listings
                    self.save_backup()
                    return
                
                # Process truly new bikes and add them to cache after processing
                notifications_sent = 0
                processed_bikes_minimal = []
                
                for bike_minimal in truly_new_minimal:
                    # Find the corresponding full bike object
                    full_bike = None
                    for bike in current_listings.bikes:
                        if (bike.title == bike_minimal.title and 
                            bike.price == bike_minimal.price and 
                            bike.href == bike_minimal.href):
                            full_bike = bike
                            break
                    
                    if full_bike:
                        # This method will check if it's from today and only send if it is
                        success = await self.check_and_send_bike_notification(full_bike)
                        if success:
                            notifications_sent += 1
                    
                    # Add bike to processed list regardless of notification success
                    processed_bikes_minimal.append(bike_minimal)
                    
                    # Small delay between checks to avoid rate limiting
                    await asyncio.sleep(2)
                
                # Add all processed bikes to minimal cache to prevent re-processing
                self.previous_listings_minimal.add_bikes(processed_bikes_minimal)
                logger.info(f"Added {len(processed_bikes_minimal)} processed bikes to minimal cache")
                
                # Save backup since we found new listings (regardless of notifications sent)
                if len(processed_bikes_minimal) > 0:
                    self.save_backup()
                
                if notifications_sent > 0:
                    logger.info(f"Sent {notifications_sent} notifications for today's listings")
                else:
                    logger.info("No new listings from today found")
            else:
                if self.is_initial_run:
                    logger.info(f"Initial run - building minimal buffer with {len(current_listings)} listings from {pages_to_scrape} pages")
                else:
                    logger.info("First run - no previous listings to compare with")
                # On first run, convert all current listings to minimal format and store
                current_minimal = [BikeMinimal(bike.title, bike.price, bike.href, bike._scraped_at) for bike in current_listings.bikes]
                self.previous_listings_minimal = BikeMinimalListings(current_minimal, max_bikes=self.max_bikes)
                # Save backup on initial run
                self.save_backup()
            
            # Mark initial run as complete
            if self.is_initial_run:
                self.is_initial_run = False
                logger.info("Initial buffer building complete - switching to ongoing monitoring mode")
            
            logger.info(f"Rolling window now contains {len(self.previous_listings_minimal)} bikes")
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
        
        if self.centralized:
            startup_message += f"Mode: Centralized (signal-triggered)\n"
        else:
            if self.time_based_intervals:
                startup_message += f"Time-based intervals:\n"
                for time_range, interval in self.time_based_intervals.items():
                    startup_message += f"• {time_range}: {interval/60:.0f} minutes\n"
                startup_message += f"Default interval: {self.check_interval} seconds\n"
            else:
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
        
        # await self.telegram_bot.send_message(
        #     chat_id=self.chat_id,
        #     message=startup_message,
        #     parse_mode='HTML'
        # )
        
        if self.centralized:
            # In centralized mode, skip initial check and wait for signals
            logger.info("Running in centralized mode - waiting for signals...")
            await self._run_centralized()
        else:
            # Original timing-based loop with initial check
            await self.check_for_new_listings()
            await self._run_timed()
    
    async def _run_timed(self) -> None:
        """
        Run the original timing-based monitoring loop.
        """
        while self.running:
            try:
                # Get current interval based on time of day
                current_interval = self.get_current_interval()
                
                # Log interval change if it's different from the last one
                if hasattr(self, '_last_interval') and self._last_interval != current_interval:
                    logger.info(f"⏰ Interval changed to {current_interval} seconds ({current_interval/60:.1f} minutes)")
                elif not hasattr(self, '_last_interval'):
                    logger.info(f"⏰ Using interval: {current_interval} seconds ({current_interval/60:.1f} minutes)")
                
                self._last_interval = current_interval
                
                await asyncio.sleep(current_interval)
                if self.running:  # Check again in case we were stopped during sleep
                    await self.check_for_new_listings()
            except asyncio.CancelledError:
                logger.info("Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                # Continue running even if there's an error
                await asyncio.sleep(10)  # Wait a bit before retrying
    
    async def _run_centralized(self) -> None:
        """
        Run in centralized mode - wait for signals to trigger checks.
        """
        logger.info("Running in centralized mode - waiting for signals...")
        
        # Set up signal handler for SIGUSR1
        def signal_handler(signum, frame):
            logger.info("Received SIGUSR1 - triggering check...")
            asyncio.create_task(self.check_for_new_listings())
        
        signal.signal(signal.SIGUSR1, signal_handler)
        
        # Keep the process alive
        while self.running:
            try:
                await asyncio.sleep(1)  # Sleep for 1 second at a time
            except asyncio.CancelledError:
                logger.info("Centralized monitoring cancelled")
                break
            except Exception as e:
                logger.error(f"Error in centralized monitoring: {e}")
                await asyncio.sleep(10)
    
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


def load_config(config_file: Path, centralized: bool = False) -> Dict[str, Any]:
    """
    Load configuration from JSON file.
    
    Args:
        config_file: Path to the JSON configuration file
        centralized: If True, check_interval is optional (timing handled centrally)
        
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
    required_fields = ['url', 'max_bikes', 'initial_pages', 'ongoing_pages', 'backup_file', 'log_file']
    # In centralized mode, check_interval is not required
    if not centralized:
        required_fields.append('check_interval')
    
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
    parser.add_argument("--centralized", action="store_true",
                       help="Run in centralized mode - wait for signals instead of using internal timing")
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(Path(args.config), centralized=args.centralized)
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)
    
    # Configure logging using centralized system
    # Command line arg can override centralized config
    force_level = args.log_level if args.log_level != "INFO" else None
    setup_logging(log_file=config['log_file'], force_level=force_level)
    
    # Check required environment variables
    required_env_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these in your .env file or environment")
        sys.exit(1)
    
    # Create monitor
    try:
        monitor = BikeMonitor(config, skip_initial=args.skip_initial, centralized=args.centralized)
    except ValueError as e:
        logger.error(f"Error initializing monitor: {e}")
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
    # shutdown_message = f"🚴‍♂️ <b>Enhanced Bike Monitor Stopped</b>\n\n"
    # shutdown_message += f"URL: {config['url']}\n"
    # shutdown_message += f"Mode: Only notified for today's listings\n"
    # shutdown_message += f"Stopped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # try:
    #     await monitor.telegram_bot.send_message(
    #         chat_id=monitor.chat_id,
    #         message=shutdown_message,
    #         parse_mode='HTML'
    #     )
    # except Exception as e:
    #     logger.error(f"Error sending shutdown notification: {e}")


if __name__ == "__main__":
    # Run the monitor
    asyncio.run(main())
