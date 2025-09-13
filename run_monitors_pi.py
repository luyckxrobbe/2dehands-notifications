#!/usr/bin/env python3
"""
Raspberry Pi optimized script to run multiple bike monitors sequentially.
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


class CentralizedSchedulerPi:
    """
    Raspberry Pi optimized centralized scheduler with longer intervals and reduced resource usage.
    """
    
    def __init__(self, monitors: List[BikeMonitor], centralized_config: Dict[str, Any] = None):
        """
        Initialize the Pi-optimized centralized scheduler.
        
        Args:
            monitors: List of BikeMonitor instances
            centralized_config: Centralized configuration dictionary
        """
        self.monitors = monitors
        self.centralized_config = centralized_config or {}
        self.running = False
        
        # Use Pi-optimized timing from config
        if self.centralized_config.get('centralized_timing'):
            timing_config = self.centralized_config['centralized_timing']
            self.base_interval = timing_config.get('base_interval', 600)  # 10 minutes default
            self.time_based_intervals = timing_config.get('time_based_intervals', {})
            self.monitor_delay = timing_config.get('monitor_delay', 15)  # Use config value
            logger.info(f"🕐 Using Pi-optimized timing - base interval: {self.base_interval} seconds")
        else:
            # Pi-optimized defaults
            self.base_interval = 600  # 10 minutes
            self.time_based_intervals = {}
            self.monitor_delay = 15  # Fallback default
            logger.warning(f"⚠️  No centralized timing config found, using Pi defaults - base interval: {self.base_interval} seconds")
    
    def _get_current_interval(self) -> int:
        """Get the current interval based on the time of day."""
        current_time = datetime.now().time()
        
        if self.time_based_intervals:
            for time_range, interval in self.time_based_intervals.items():
                start_str, end_str = time_range.split('-')
                start_time = dt_time.fromisoformat(start_str)
                end_time = dt_time.fromisoformat(end_str)
                
                if start_time <= end_time:
                    if start_time <= current_time <= end_time:
                        return interval
                else:
                    if current_time >= start_time or current_time <= end_time:
                        return interval
        
        return self.base_interval
    
    async def trigger_check(self):
        """Trigger a check for all monitors sequentially with Pi-optimized delays."""
        if not self.monitors:
            return
        
        logger.info(f"🔄 Triggering Pi-optimized sequential check for {len(self.monitors)} monitors...")
        
        for i, monitor in enumerate(self.monitors):
            logger.info(f"🚀 [{i+1}/{len(self.monitors)}] Running check for: {monitor.log_file}")
            
            try:
                # Run the check directly on the monitor instance
                await monitor.check_for_new_listings()
                logger.info(f"✅ Completed check for: {monitor.log_file}")
                
                # Add delay between monitors for Pi (reduces load)
                if i < len(self.monitors) - 1:
                    logger.info(f"⏳ Waiting {self.monitor_delay} seconds before next monitor...")
                    await asyncio.sleep(self.monitor_delay)
                
            except Exception as e:
                logger.error(f"❌ Error running check for {monitor.log_file}: {e}")
                continue
        
        logger.info("✅ Pi-optimized sequential check cycle completed")
    
    async def run(self):
        """Run the Pi-optimized centralized scheduler loop."""
        self.running = True
        logger.info("🕐 Starting Pi-optimized centralized scheduler...")
        
        # Start with an immediate check cycle after a delay
        logger.info("🚀 Starting with immediate scrape cycle...")
        logger.info("⏳ Waiting 10 seconds for all monitors to initialize...")
        await asyncio.sleep(10)
        await self.trigger_check()
        
        while self.running:
            try:
                current_interval = self._get_current_interval()
                
                # Log interval change if it's different from the last one
                if hasattr(self, '_last_interval') and self._last_interval != current_interval:
                    logger.info(f"⏰ Interval changed to {current_interval} seconds ({current_interval/60:.1f} minutes)")
                elif not hasattr(self, '_last_interval'):
                    logger.info(f"⏰ Using Pi-optimized interval: {current_interval} seconds ({current_interval/60:.1f} minutes)")
                
                self._last_interval = current_interval
                
                # Wait for the interval
                await asyncio.sleep(current_interval)
                
                if self.running:
                    await self.trigger_check()
                    
            except asyncio.CancelledError:
                logger.info("🛑 Pi scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in Pi scheduler loop: {e}")
                await asyncio.sleep(30)  # Wait longer before retrying on Pi
    
    def stop(self):
        """Stop the Pi-optimized centralized scheduler."""
        logger.info("🛑 Stopping Pi-optimized centralized scheduler...")
        self.running = False


def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Error loading config {config_file}: {e}")
        return {}


def load_centralized_config(config_file: str = "config-pi/centralized-config.json") -> Dict[str, Any]:
    """Load Pi-optimized centralized configuration."""
    try:
        if Path(config_file).exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info(f"✅ Loaded Pi-optimized centralized config from {config_file}")
                return config
        else:
            logger.warning(f"⚠️  Pi centralized config file not found: {config_file}")
            return {}
    except Exception as e:
        logger.error(f"❌ Error loading Pi centralized config {config_file}: {e}")
        return {}


async def run_init_buffer_pi(config_file: str) -> tuple[str, bool]:
    """Run Pi-optimized buffer initialization."""
    logger.info(f"🔄 Initializing Pi-optimized buffer for: {config_file}")
    
    try:
        from init_buffer_pi import init_buffer_pi
        await init_buffer_pi(config_file)
        logger.info(f"✅ Pi buffer initialization successful for: {config_file}")
        return (config_file, True)
    except Exception as e:
        logger.error(f"❌ Error running Pi buffer initialization for: {config_file}: {e}")
        return (config_file, False)


def create_monitor_pi(config_file: str) -> BikeMonitor:
    """Create a Pi-optimized BikeMonitor instance."""
    config = load_config(config_file)
    
    # Add default check_interval if missing (use centralized config default)
    if 'check_interval' not in config:
        centralized_config = load_centralized_config()
        default_interval = centralized_config.get('centralized_timing', {}).get('base_interval', 600)
        config['check_interval'] = default_interval
    
    # Ensure Pi optimization is enabled
    config['pi_optimized'] = True
    
    # Create monitor instance in centralized mode
    monitor = BikeMonitor(config, skip_initial=True, centralized=True)
    
    return monitor


def find_config_files(paths: List[str]) -> List[str]:
    """Find all config files from the given paths."""
    config_files = []
    
    for path in paths:
        path_obj = Path(path)
        
        if path_obj.is_file():
            if path.endswith('.json') and not path.endswith('centralized-config.json'):
                config_files.append(str(path_obj))
        elif path_obj.is_dir():
            json_files = list(path_obj.glob('*.json'))
            monitor_config_files = [f for f in json_files if f.name != 'centralized-config.json']
            if monitor_config_files:
                logger.info(f"📁 Found {len(monitor_config_files)} monitor config files in {path}:")
                for json_file in sorted(monitor_config_files):
                    logger.info(f"   - {json_file.name}")
                    config_files.append(str(json_file))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_config_files = []
    for config_file in config_files:
        if config_file not in seen:
            seen.add(config_file)
            unique_config_files.append(config_file)
    
    return unique_config_files


async def main():
    """Main function to run Pi-optimized monitors."""
    if len(sys.argv) < 2:
        logger.info("Usage: python run_monitors_pi.py <config1.json> [config2.json] ... [folder/] [*.json]")
        logger.info("")
        logger.info("Examples:")
        logger.info("  python run_monitors_pi.py config-2dehands-pi.json")
        logger.info("  python run_monitors_pi.py configs/")
        logger.info("")
        logger.info("Pi-optimized features:")
        logger.info("  - Longer intervals to reduce CPU load")
        logger.info("  - Reduced page counts and memory usage")
        logger.info("  - Optimized browser settings for ARM")
        logger.info("  - Sequential execution with delays")
        logger.info("  - Automatic buffer initialization")
        sys.exit(1)
    
    # Find all config files
    input_paths = sys.argv[1:]
    config_files = find_config_files(input_paths)
    
    if not config_files:
        logger.error("❌ No valid config files found")
        sys.exit(1)
    
    logger.info(f"📋 Found {len(config_files)} config files to process")
    logger.info("")
    
    # Load Pi-optimized centralized config
    centralized_config = load_centralized_config()
    
    logger.info("🚴‍♂️ Starting Pi-optimized bike monitors...")
    logger.info("")
    
    # Identify which configs need buffer initialization
    configs_needing_init = []
    configs_ready_to_start = []
    
    for config_file in config_files:
        if not Path(config_file).exists():
            logger.error(f"❌ Config file not found: {config_file}")
            continue
        
        config = load_config(config_file)
        if not config:
            continue
        
        if config.get('init_buffer', False):
            backup_file = config.get('backup_file', '')
            if backup_file and Path(backup_file).exists():
                logger.warning(f"⚠️  Backup file already exists: {backup_file}")
                logger.info(f"   Skipping buffer initialization for: {config_file}")
                configs_ready_to_start.append(config_file)
            else:
                logger.info(f"📋 Config {config_file} needs Pi buffer initialization")
                configs_needing_init.append(config_file)
        else:
            configs_ready_to_start.append(config_file)
    
    # Run Pi-optimized buffer initialization sequentially
    if configs_needing_init:
        logger.info(f"🔄 Running Pi-optimized buffer initialization for {len(configs_needing_init)} configs...")
        
        for config_file in configs_needing_init:
            config_file, success = await run_init_buffer_pi(config_file)
            if success:
                logger.info(f"✅ Pi buffer initialized for: {config_file}")
                configs_ready_to_start.append(config_file)
            else:
                logger.error(f"❌ Failed to initialize Pi buffer for: {config_file}")
    
    if not configs_ready_to_start:
        logger.error("❌ No configs ready to start")
        sys.exit(1)
    
    # Create Pi-optimized monitor instances
    monitors = []
    for config_file in configs_ready_to_start:
        try:
            logger.info(f"🚀 Creating Pi-optimized monitor: {config_file}")
            monitor = create_monitor_pi(config_file)
            monitors.append(monitor)
        except Exception as e:
            logger.error(f"❌ Failed to create Pi monitor for {config_file}: {e}")
    
    if not monitors:
        logger.error("❌ No Pi monitors created successfully")
        sys.exit(1)
    
    # Create Pi-optimized centralized scheduler
    scheduler = CentralizedSchedulerPi(monitors, centralized_config)
    
    logger.info(f"\n✅ Created {len(monitors)} Pi-optimized monitors")
    logger.info("Press Ctrl+C to stop all monitors")
    logger.info("Pi-optimized timing: Longer intervals, reduced resource usage")
    logger.info("")
    
    try:
        # Start the Pi-optimized centralized scheduler
        await scheduler.run()
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Stopping all Pi monitors...")
        
        # Stop the scheduler first
        scheduler.stop()
        
        # Stop all monitors
        for monitor in monitors:
            logger.info(f"Stopping: {monitor.log_file}")
            monitor.stop()
        
        logger.info("✅ All Pi monitors stopped")


if __name__ == "__main__":
    asyncio.run(main())
