#!/usr/bin/env python3
"""
Script to run multiple bike monitors sequentially with optional buffer initialization.
"""

import asyncio
import sys
import json
import time
import glob
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, time as dt_time

from centralized_logging import setup_logging, get_logger
from bike_monitor import BikeMonitor

# Configure logging
setup_logging()
logger = get_logger(__name__)


class CentralizedScheduler:
    """
    Centralized scheduler that manages timing intervals for all monitors
    and runs them sequentially to avoid simultaneous scraping.
    """
    
    def __init__(self, monitors: List[BikeMonitor], centralized_config: Dict[str, Any] = None):
        """
        Initialize the centralized scheduler.
        
        Args:
            monitors: List of BikeMonitor instances
            centralized_config: Centralized configuration dictionary
        """
        self.monitors = monitors
        self.centralized_config = centralized_config or {}
        self.running = False
        
        # Use centralized config for timing
        if self.centralized_config.get('centralized_timing'):
            timing_config = self.centralized_config['centralized_timing']
            self.base_interval = timing_config.get('base_interval', 300)
            self.time_based_intervals = timing_config.get('time_based_intervals', {})
            self.monitor_delay = timing_config.get('monitor_delay', 10)  # Use config value
            logger.info(f"🕐 Using centralized timing config - base interval: {self.base_interval} seconds")
        else:
            # Default values if no centralized config
            self.base_interval = 300
            self.time_based_intervals = {}
            self.monitor_delay = 10  # Fallback default
            logger.warning(f"⚠️  No centralized timing config found, using defaults - base interval: {self.base_interval} seconds")
        
    
    def _get_current_interval(self) -> int:
        """
        Get the current interval based on the time of day.
        Uses only centralized timing config.
        """
        current_time = datetime.now().time()
        
        # Use centralized time-based intervals
        if self.time_based_intervals:
            for time_range, interval in self.time_based_intervals.items():
                start_str, end_str = time_range.split('-')
                start_time = dt_time.fromisoformat(start_str)
                end_time = dt_time.fromisoformat(end_str)
                
                # Handle the case where the range crosses midnight
                if start_time <= end_time:
                    if start_time <= current_time <= end_time:
                        return interval
                else:
                    if current_time >= start_time or current_time <= end_time:
                        return interval
        
        # Fallback to base interval
        return self.base_interval
    
    async def trigger_check(self):
        """
        Trigger a check for all monitors sequentially, waiting for each to complete before starting the next.
        """
        if not self.monitors:
            return
        
        logger.info(f"🔄 Triggering sequential check for {len(self.monitors)} monitors...")
        
        for i, monitor in enumerate(self.monitors):
            logger.info(f"🚀 [{i+1}/{len(self.monitors)}] Running check for: {monitor.log_file}")
            
            try:
                # Run the check directly on the monitor instance
                await monitor.check_for_new_listings()
                logger.info(f"✅ Completed check for: {monitor.log_file}")
            except Exception as e:
                logger.error(f"❌ Error running check for {monitor.log_file}: {e}")
                continue
        
        logger.info("✅ Sequential check cycle completed")
    
    
    async def run(self):
        """
        Run the centralized scheduler loop.
        """
        self.running = True
        logger.info("🕐 Starting centralized scheduler...")
        
        # Start with an immediate check cycle after a short delay to ensure all monitors are initialized
        logger.info("🚀 Starting with immediate scrape cycle...")
        logger.info("⏳ Waiting 5 seconds for all monitors to initialize...")
        await asyncio.sleep(5)
        await self.trigger_check()
        
        while self.running:
            try:
                current_interval = self._get_current_interval()
                
                # Log interval change if it's different from the last one
                if hasattr(self, '_last_interval') and self._last_interval != current_interval:
                    logger.info(f"⏰ Interval changed to {current_interval} seconds ({current_interval/60:.1f} minutes)")
                elif not hasattr(self, '_last_interval'):
                    logger.info(f"⏰ Using interval: {current_interval} seconds ({current_interval/60:.1f} minutes)")
                
                self._last_interval = current_interval
                
                # Wait for the interval
                await asyncio.sleep(current_interval)
                
                if self.running:
                    await self.trigger_check()
                    
            except asyncio.CancelledError:
                logger.info("🛑 Scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in scheduler loop: {e}")
                await asyncio.sleep(10)  # Wait a bit before retrying
    
    def stop(self):
        """
        Stop the centralized scheduler.
        """
        logger.info("🛑 Stopping centralized scheduler...")
        self.running = False


def load_config(config_file: str) -> Dict[str, Any]:
    """
    Load configuration from JSON file.
    
    Args:
        config_file: Path to the JSON configuration file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Error loading config {config_file}: {e}")
        return {}


def load_centralized_config(config_file: str = "configs/centralized-config.json") -> Dict[str, Any]:
    """
    Load centralized configuration from JSON file.
    
    Args:
        config_file: Path to the centralized configuration file
        
    Returns:
        Centralized configuration dictionary
    """
    try:
        if Path(config_file).exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info(f"✅ Loaded centralized config from {config_file}")
                return config
        else:
            logger.warning(f"⚠️  Centralized config file not found: {config_file}")
            return {}
    except Exception as e:
        logger.error(f"❌ Error loading centralized config {config_file}: {e}")
        return {}


async def run_init_buffer(config_file: str) -> tuple[str, bool]:
    """
    Run buffer initialization for a config file.
    
    Args:
        config_file: Path to the JSON configuration file
        
    Returns:
        Tuple of (config_file, success_status)
    """
    logger.info(f"🔄 Initializing buffer for: {config_file}")
    
    try:
        # Import and call init_buffer function directly
        from init_buffer import init_buffer
        
        # Call the init_buffer function directly
        await init_buffer(config_file)
        logger.info(f"✅ Buffer initialization successful for: {config_file}")
        return (config_file, True)
            
    except Exception as e:
        logger.error(f"❌ Error running buffer initialization for: {config_file}: {e}")
        return (config_file, False)




def create_monitor(config_file: str) -> BikeMonitor:
    """
    Create a BikeMonitor instance for the given config file.
    
    Args:
        config_file: Path to the JSON configuration file
        
    Returns:
        BikeMonitor instance
    """
    # Load config
    config = load_config(config_file)
    
    # Add default check_interval if missing (for centralized mode)
    if 'check_interval' not in config:
        centralized_config = CentralizedLogger.load_centralized_config()
        default_interval = centralized_config.get('centralized_timing', {}).get('base_interval', 300)
        config['check_interval'] = default_interval
    
    # Create monitor instance in centralized mode since we handle timing ourselves
    monitor = BikeMonitor(config, skip_initial=True, centralized=True)
    
    return monitor


def find_config_files(paths: List[str]) -> List[str]:
    """
    Find all config files from the given paths.
    Supports both individual files and folders.
    Excludes centralized-config.json as it's not a monitor config.
    
    Args:
        paths: List of file paths or folder paths
        
    Returns:
        List of config file paths
    """
    config_files = []
    
    for path in paths:
        path_obj = Path(path)
        
        if path_obj.is_file():
            # Single file
            if path.endswith('.json') and not path.endswith('centralized-config.json'):
                config_files.append(str(path_obj))
            else:
                logger.warning(f"⚠️  Skipping non-JSON file: {path}")
        elif path_obj.is_dir():
            # Folder - find all JSON files except centralized-config.json
            json_files = list(path_obj.glob('*.json'))
            # Filter out centralized-config.json
            monitor_config_files = [f for f in json_files if f.name != 'centralized-config.json']
            if monitor_config_files:
                logger.info(f"📁 Found {len(monitor_config_files)} monitor config files in {path}:")
                for json_file in sorted(monitor_config_files):
                    logger.info(f"   - {json_file.name}")
                    config_files.append(str(json_file))
            else:
                logger.warning(f"⚠️  No monitor config files found in folder: {path}")
        else:
            # Try glob pattern
            try:
                glob_files = glob.glob(path)
                if glob_files:
                    for glob_file in glob_files:
                        if Path(glob_file).is_file() and glob_file.endswith('.json') and not glob_file.endswith('centralized-config.json'):
                            config_files.append(glob_file)
                        elif Path(glob_file).is_dir():
                            # Recursively find JSON files in glob-matched directories
                            sub_files = find_config_files([glob_file])
                            config_files.extend(sub_files)
                else:
                    logger.warning(f"⚠️  No files found matching pattern: {path}")
            except Exception as e:
                logger.warning(f"⚠️  Error processing path {path}: {e}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_config_files = []
    for config_file in config_files:
        if config_file not in seen:
            seen.add(config_file)
            unique_config_files.append(config_file)
    
    return unique_config_files


async def main():
    """
    Main function to run multiple monitors with centralized timing.
    """
    if len(sys.argv) < 2:
        logger.info("Usage: python run_monitors.py <config1.json> [config2.json] ... [folder/] [*.json]")
        logger.info("")
        logger.info("Examples:")
        logger.info("  python run_monitors.py config-2dehands.json")
        logger.info("  python run_monitors.py config-2dehands.json config-marktplaats.json")
        logger.info("  python run_monitors.py configs/")
        logger.info("  python run_monitors.py configs/*.json")
        logger.info("  python run_monitors.py configs/ config-2dehands.json")
        logger.info("")
        logger.info("Features:")
        logger.info("  - Centralized timing scheduler prevents simultaneous scraping")
        logger.info("  - Monitors run sequentially when triggered (scrape1 → scrape2 → scrape3 → WAIT → repeat)")
        logger.info("  - Uses centralized-config.json for timing and scheduler settings")
        logger.info("  - Automatically initializes buffer if 'init_buffer': true in config")
        logger.info("  - Runs buffer initialization sequentially")
        logger.info("  - Supports folders (finds all *.json files)")
        logger.info("  - Supports glob patterns")
        logger.info("  - Handles graceful shutdown with Ctrl+C")
        sys.exit(1)
    
    # Find all config files from the provided paths
    input_paths = sys.argv[1:]
    config_files = find_config_files(input_paths)
    
    if not config_files:
        logger.error("❌ No valid config files found")
        sys.exit(1)
    
    logger.info(f"📋 Found {len(config_files)} config files to process")
    logger.info("")
    
    # Load centralized config
    centralized_config = load_centralized_config()
    
    logger.info("🚴‍♂️ Starting multiple bike monitors with centralized timing...")
    logger.info("")
    
    # First, identify which configs need buffer initialization
    configs_needing_init = []
    configs_ready_to_start = []
    
    for config_file in config_files:
        if not Path(config_file).exists():
            logger.error(f"❌ Config file not found: {config_file}")
            continue
        
        # Load config to check if buffer initialization is needed
        config = load_config(config_file)
        if not config:
            continue
        
        # Check if buffer initialization is needed
        if config.get('init_buffer', False):
            # Check if backup file already exists
            backup_file = config.get('backup_file', '')
            if backup_file and Path(backup_file).exists():
                logger.warning(f"⚠️  Backup file already exists: {backup_file}")
                logger.info(f"   Skipping buffer initialization for: {config_file}")
                configs_ready_to_start.append(config_file)
            else:
                logger.info(f"📋 Config {config_file} needs buffer initialization")
                configs_needing_init.append(config_file)
        else:
            configs_ready_to_start.append(config_file)
    
    # Run buffer initialization sequentially for configs that need it
    if configs_needing_init:
        logger.info(f"🔄 Running buffer initialization for {len(configs_needing_init)} configs sequentially...")
        
        for config_file in configs_needing_init:
            config_file, success = await run_init_buffer(config_file)
            if success:
                logger.info(f"✅ Buffer initialized for: {config_file}")
                configs_ready_to_start.append(config_file)
            else:
                logger.error(f"❌ Failed to initialize buffer for: {config_file}")
                logger.info(f"   Skipping monitor startup for: {config_file}")
    
    if not configs_ready_to_start:
        logger.error("❌ No configs ready to start")
        sys.exit(1)
    
    # Create monitor instances
    monitors = []
    for config_file in configs_ready_to_start:
        try:
            logger.info(f"🚀 Creating monitor: {config_file}")
            monitor = create_monitor(config_file)
            monitors.append(monitor)
        except Exception as e:
            logger.error(f"❌ Failed to create monitor for {config_file}: {e}")
    
    if not monitors:
        logger.error("❌ No monitors created successfully")
        sys.exit(1)
    
    # Create centralized scheduler with monitors
    scheduler = CentralizedScheduler(monitors, centralized_config)
    
    logger.info(f"\n✅ Created {len(monitors)} monitors")
    logger.info("Press Ctrl+C to stop all monitors")
    logger.info("Centralized timing: Monitors will run sequentially when triggered")
    logger.info("")
    
    try:
        # Start the centralized scheduler
        await scheduler.run()
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Stopping all monitors...")
        
        # Stop the scheduler first
        scheduler.stop()
        
        # Stop all monitors
        for monitor in monitors:
            logger.info(f"Stopping: {monitor.log_file}")
            monitor.stop()
        
        logger.info("✅ All monitors stopped")


if __name__ == "__main__":
    asyncio.run(main())
