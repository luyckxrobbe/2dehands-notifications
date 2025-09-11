#!/usr/bin/env python3
"""
Script to run multiple bike monitors simultaneously with optional buffer initialization.
"""

import asyncio
import subprocess
import sys
import json
import time
import glob
import concurrent.futures
import threading
import logging
import queue
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime, time as dt_time

from centralized_logging import setup_logging, get_logger

# Configure logging
setup_logging()
logger = get_logger(__name__)


class CentralizedScheduler:
    """
    Centralized scheduler that manages timing intervals for all monitors
    and runs them sequentially to avoid simultaneous scraping.
    """
    
    def __init__(self, configs: List[Dict[str, Any]], centralized_config: Dict[str, Any] = None):
        """
        Initialize the centralized scheduler.
        
        Args:
            configs: List of configuration dictionaries for all monitors
            centralized_config: Centralized configuration dictionary
        """
        self.configs = configs
        self.centralized_config = centralized_config or {}
        self.running = False
        self.monitors = []  # List of (config_file, process, stdout_thread, stderr_thread)
        self.process_counter = 1
        
        # Use centralized config for timing
        if self.centralized_config.get('centralized_timing'):
            timing_config = self.centralized_config['centralized_timing']
            self.base_interval = timing_config.get('base_interval', 300)
            self.time_based_intervals = timing_config.get('time_based_intervals', {})
            self.monitor_delay = timing_config.get('monitor_delay', 10)
            logger.info(f"🕐 Using centralized timing config - base interval: {self.base_interval} seconds")
        else:
            # Default values if no centralized config
            self.base_interval = 300
            self.time_based_intervals = {}
            self.monitor_delay = 10
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
    
    def add_monitor(self, config_file: str, process: subprocess.Popen, 
                   stdout_thread: threading.Thread, stderr_thread: threading.Thread):
        """
        Add a monitor to the scheduler.
        
        Args:
            config_file: Path to the config file
            process: The subprocess for the monitor
            stdout_thread: Thread handling stdout
            stderr_thread: Thread handling stderr
        """
        self.monitors.append((config_file, process, stdout_thread, stderr_thread))
        logger.info(f"📋 Added monitor to scheduler: {config_file}")
    
    async def trigger_check(self):
        """
        Trigger a check for all monitors sequentially, waiting for each to complete before starting the next.
        """
        if not self.monitors:
            return
        
        logger.info(f"🔄 Triggering sequential check for {len(self.monitors)} monitors...")
        
        for i, (config_file, process, stdout_thread, stderr_thread) in enumerate(self.monitors):
            if process.poll() is not None:
                logger.warning(f"⚠️  Monitor {config_file} is not running, skipping...")
                continue
            
            logger.info(f"🚀 [{i+1}/{len(self.monitors)}] Triggering check for: {config_file}")
            
            # Send SIGUSR1 signal to trigger a check
            try:
                process.send_signal(subprocess.signal.SIGUSR1)
            except Exception as e:
                logger.error(f"❌ Error triggering check for {config_file}: {e}")
                continue
            
            # Wait for this monitor to complete its scraping before moving to the next
            await self._wait_for_monitor_completion(process, config_file)
        
        logger.info("✅ Sequential check cycle completed")
    
    async def _wait_for_monitor_completion(self, process: subprocess.Popen, config_file: str):
        """
        Wait for a monitor to complete its scraping using status file communication.
        
        Args:
            process: The subprocess to monitor
            config_file: Config file name for identification
        """
        logger.info(f"⏳ Waiting for {config_file} to complete scraping...")
        
        # Create status file path based on config file name
        # Extract the monitor name from the config file path
        config_name = Path(config_file).stem  # e.g., "config-2dehands-sportfietsen"
        # Remove "config-" prefix to get the monitor name
        monitor_name = config_name.replace("config-", "")  # e.g., "2dehands-sportfietsen"
        status_file = Path(f"status_{monitor_name}.json")
        
        logger.info(f"   Looking for status file: {status_file}")
        
        # Clear any existing status file
        if status_file.exists():
            status_file.unlink()
        
        # Wait for the monitor to create and update the status file
        timeout_seconds = 300  # 5 minutes timeout
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            try:
                # Check if process is still running
                if process.poll() is not None:
                    logger.warning(f"   Process {config_file} stopped unexpectedly during scraping")
                    return
                
                # Check if status file exists and indicates completion
                if status_file.exists():
                    try:
                        with open(status_file, 'r') as f:
                            status = json.load(f)
                        
                        if status.get('status') == 'completed':
                            logger.info(f"   ✅ {config_file} scraping completed (status file confirmed)")
                            # Clean up status file
                            status_file.unlink()
                            return
                        elif status.get('status') == 'error':
                            logger.error(f"   ❌ {config_file} scraping failed: {status.get('error', 'Unknown error')}")
                            status_file.unlink()
                            return
                            
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"   Invalid status file format: {e}")
                
                # Wait a bit before checking again
                await asyncio.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                logger.error(f"   Error monitoring {config_file}: {e}")
                break
        
        # If we get here, we've reached the timeout
        logger.warning(f"   ⏰ Timeout waiting for {config_file} to complete scraping")
        # Clean up status file if it exists
        if status_file.exists():
            status_file.unlink()
    
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


def run_init_buffer(config_file: str) -> Tuple[str, bool]:
    """
    Run buffer initialization for a config file.
    
    Args:
        config_file: Path to the JSON configuration file
        
    Returns:
        Tuple of (config_file, success_status)
    """
    logger.info(f"🔄 Initializing buffer for: {config_file}")
    
    try:
        # Run init_buffer.py with the config file
        result = subprocess.run(
            [sys.executable, "init_buffer.py", config_file],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Buffer initialization successful for: {config_file}")
            return (config_file, True)
        else:
            logger.error(f"❌ Buffer initialization failed for: {config_file}")
            logger.error(f"Error: {result.stderr}")
            return (config_file, False)
            
    except subprocess.TimeoutExpired:
        logger.error(f"⏰ Buffer initialization timed out for: {config_file}")
        return (config_file, False)
    except Exception as e:
        logger.error(f"❌ Error running buffer initialization for: {config_file}: {e}")
        return (config_file, False)




def stream_output(process: subprocess.Popen, prefix: str, config_file: str):
    """
    Stream output from a subprocess with a prefix.
    
    Args:
        process: The subprocess to stream output from
        prefix: Prefix to add to each line (e.g., "[1]")
        config_file: Config file name for identification
    """
    def read_stdout():
        try:
            for line in iter(process.stdout.readline, b''):
                if line:
                    line_str = line.decode('utf-8').rstrip()
                    # Extract just the message part, removing the log header
                    clean_message = extract_log_message(line_str)
                    logger.info(f"{prefix} {clean_message}")
        except Exception as e:
            logger.error(f"{prefix} Error reading stdout: {e}")
    
    def read_stderr():
        try:
            for line in iter(process.stderr.readline, b''):
                if line:
                    line_str = line.decode('utf-8').rstrip()
                    # Extract just the message part, removing the log header
                    clean_message = extract_log_message(line_str)
                    
                    # Parse the log level from the original line and use appropriate logger level
                    if ' - ERROR - ' in line_str:
                        logger.error(f"{prefix} {clean_message}")
                    elif ' - WARNING - ' in line_str:
                        logger.warning(f"{prefix} {clean_message}")
                    elif ' - DEBUG - ' in line_str:
                        logger.debug(f"{prefix} {clean_message}")
                    else:
                        # Default to info for INFO level and other messages
                        logger.info(f"{prefix} {clean_message}")
        except Exception as e:
            logger.error(f"{prefix} Error reading stderr: {e}")
    
    def extract_log_message(line_str):
        """
        Extract the actual message from a log line, removing the timestamp and log level header.
        Expected format: "2025-09-11 08:33:49,785 - __main__ - INFO - actual message here"
        """
        # Look for the pattern: timestamp - logger_name - level - message
        parts = line_str.split(' - ', 3)
        if len(parts) >= 4:
            # Return just the message part (everything after the third ' - ')
            return parts[3]
        else:
            # If it doesn't match the expected format, return the whole line
            return line_str
    
    # Start threads for stdout and stderr
    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    
    stdout_thread.start()
    stderr_thread.start()
    
    return stdout_thread, stderr_thread


def run_monitor(config_file: str, process_id: int) -> Tuple[subprocess.Popen, threading.Thread, threading.Thread]:
    """
    Start a monitor process for the given config file with output streaming.
    The monitor will run in centralized mode (no internal timing loop).
    
    Args:
        config_file: Path to the JSON configuration file
        process_id: Unique ID for this process (used in prefix)
        
    Returns:
        Tuple of (process, stdout_thread, stderr_thread)
    """
    # Load config to check if we should skip initial check
    config = load_config(config_file)
    skip_initial = config.get('initial_check', True) == False  # Default to True (don't skip) if not specified
    
    cmd = [sys.executable, "bike_monitor.py", config_file]
    if skip_initial:
        cmd.append("--skip-initial")
    
    # Add centralized mode flag
    cmd.append("--centralized")
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Create prefix based on process ID and config file name
    config_name = Path(config_file).stem
    prefix = f"[{process_id}] {config_name}"
    
    # Start output streaming threads
    stdout_thread, stderr_thread = stream_output(process, prefix, config_file)
    
    return process, stdout_thread, stderr_thread


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
        logger.info("  - Starts all monitors immediately (no startup delays in centralized mode)")
        logger.info("  - Runs buffer initialization in parallel (configurable concurrency)")
        logger.info("  - Starts monitors as soon as their buffer initialization completes")
        logger.info("  - Supports folders (finds all *.json files)")
        logger.info("  - Supports glob patterns")
        logger.info("  - Handles graceful shutdown with Ctrl+C")
        logger.info("  - Real-time output streaming with process prefixes")
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
    
    # Load all configs for the centralized scheduler
    all_configs = []
    for config_file in config_files:
        if Path(config_file).exists():
            config = load_config(config_file)
            if config:
                all_configs.append(config)
    
    if not all_configs:
        logger.error("❌ No valid configs found")
        sys.exit(1)
    
    # Create centralized scheduler with centralized config
    scheduler = CentralizedScheduler(all_configs, centralized_config)
    
    processes = []
    process_counter = 1
    
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
    
    # Start monitors immediately for configs that don't need buffer initialization
    if configs_ready_to_start:
        logger.info(f"🚀 Starting {len(configs_ready_to_start)} monitors immediately (centralized mode)...")
        
        for i, config_file in enumerate(configs_ready_to_start):
            logger.info(f"   Starting monitor: {config_file}")
            process, stdout_thread, stderr_thread = run_monitor(config_file, process_counter)
            processes.append((config_file, process, stdout_thread, stderr_thread))
            scheduler.add_monitor(config_file, process, stdout_thread, stderr_thread)
            process_counter += 1
    
    # Run buffer initialization in parallel for configs that need it
    if configs_needing_init:
        logger.info(f"🔄 Running buffer initialization for {len(configs_needing_init)} configs in parallel...")
        
        # Get max concurrent workers from centralized config
        max_workers = 4  # default
        if centralized_config.get('scheduler', {}).get('max_concurrent_buffer_init'):
            max_workers = centralized_config['scheduler']['max_concurrent_buffer_init']
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(configs_needing_init), max_workers)) as executor:
            # Submit all buffer initialization tasks
            future_to_config = {
                executor.submit(run_init_buffer, config_file): config_file 
                for config_file in configs_needing_init
            }
            
            # Collect results and start monitors as they complete
            for i, future in enumerate(concurrent.futures.as_completed(future_to_config)):
                config_file, success = future.result()
                if success:
                    logger.info(f"✅ Buffer initialized for: {config_file}")
                    logger.info(f"🚀 Starting monitor: {config_file}")
                    process, stdout_thread, stderr_thread = run_monitor(config_file, process_counter)
                    processes.append((config_file, process, stdout_thread, stderr_thread))
                    scheduler.add_monitor(config_file, process, stdout_thread, stderr_thread)
                    process_counter += 1
                else:
                    logger.error(f"❌ Failed to initialize buffer for: {config_file}")
                    logger.info(f"   Skipping monitor startup for: {config_file}")
    
    if not processes:
        logger.error("❌ No configs ready to start")
        sys.exit(1)
    
    logger.info(f"\n✅ Started {len(processes)} monitors")
    logger.info("Press Ctrl+C to stop all monitors")
    logger.info("Output format: [ID] config_name message")
    logger.info("Centralized timing: Monitors will run sequentially when triggered")
    logger.info("")
    
    try:
        # Start the centralized scheduler
        await scheduler.run()
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Stopping all monitors...")
        
        # Stop the scheduler first
        scheduler.stop()
        
        # Terminate all processes
        for config_file, process, stdout_thread, stderr_thread in processes:
            logger.info(f"Stopping: {config_file}")
            process.terminate()
        
        # Wait for processes to terminate
        for config_file, process, stdout_thread, stderr_thread in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"Force killing: {config_file}")
                process.kill()
        
        logger.info("✅ All monitors stopped")


if __name__ == "__main__":
    asyncio.run(main())
