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
from pathlib import Path
from typing import List, Dict, Any, Tuple


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
        print(f"❌ Error loading config {config_file}: {e}")
        return {}


def run_init_buffer(config_file: str) -> Tuple[str, bool]:
    """
    Run buffer initialization for a config file.
    
    Args:
        config_file: Path to the JSON configuration file
        
    Returns:
        Tuple of (config_file, success_status)
    """
    print(f"🔄 Initializing buffer for: {config_file}")
    
    try:
        # Run init_buffer.py with the config file
        result = subprocess.run(
            [sys.executable, "init_buffer.py", config_file],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            print(f"✅ Buffer initialization successful for: {config_file}")
            return (config_file, True)
        else:
            print(f"❌ Buffer initialization failed for: {config_file}")
            print(f"Error: {result.stderr}")
            return (config_file, False)
            
    except subprocess.TimeoutExpired:
        print(f"⏰ Buffer initialization timed out for: {config_file}")
        return (config_file, False)
    except Exception as e:
        print(f"❌ Error running buffer initialization for: {config_file}: {e}")
        return (config_file, False)


def run_monitor(config_file: str) -> subprocess.Popen:
    """
    Start a monitor process for the given config file.
    
    Args:
        config_file: Path to the JSON configuration file
        
    Returns:
        Process object
    """
    cmd = [sys.executable, "bike_monitor.py", config_file]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def find_config_files(paths: List[str]) -> List[str]:
    """
    Find all config files from the given paths.
    Supports both individual files and folders.
    
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
            if path.endswith('.json'):
                config_files.append(str(path_obj))
            else:
                print(f"⚠️  Skipping non-JSON file: {path}")
        elif path_obj.is_dir():
            # Folder - find all JSON files
            json_files = list(path_obj.glob('*.json'))
            if json_files:
                print(f"📁 Found {len(json_files)} config files in {path}:")
                for json_file in sorted(json_files):
                    print(f"   - {json_file.name}")
                    config_files.append(str(json_file))
            else:
                print(f"⚠️  No JSON files found in folder: {path}")
        else:
            # Try glob pattern
            try:
                glob_files = glob.glob(path)
                if glob_files:
                    for glob_file in glob_files:
                        if Path(glob_file).is_file() and glob_file.endswith('.json'):
                            config_files.append(glob_file)
                        elif Path(glob_file).is_dir():
                            # Recursively find JSON files in glob-matched directories
                            sub_files = find_config_files([glob_file])
                            config_files.extend(sub_files)
                else:
                    print(f"⚠️  No files found matching pattern: {path}")
            except Exception as e:
                print(f"⚠️  Error processing path {path}: {e}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_config_files = []
    for config_file in config_files:
        if config_file not in seen:
            seen.add(config_file)
            unique_config_files.append(config_file)
    
    return unique_config_files


def main():
    """
    Main function to run multiple monitors with optional buffer initialization.
    """
    if len(sys.argv) < 2:
        print("Usage: python run_monitors.py <config1.json> [config2.json] ... [folder/] [*.json]")
        print()
        print("Examples:")
        print("  python run_monitors.py config-2dehands.json")
        print("  python run_monitors.py config-2dehands.json config-marktplaats.json")
        print("  python run_monitors.py configs/")
        print("  python run_monitors.py configs/*.json")
        print("  python run_monitors.py configs/ config-2dehands.json")
        print()
        print("Features:")
        print("  - Automatically initializes buffer if 'init_buffer': true in config")
        print("  - Starts monitors immediately for configs that don't need buffer initialization")
        print("  - Runs buffer initialization in parallel (up to 4 concurrent)")
        print("  - Starts monitors as soon as their buffer initialization completes")
        print("  - Staggered startup (2-minute delay between monitors) to spread scraping load")
        print("  - Supports folders (finds all *.json files)")
        print("  - Supports glob patterns")
        print("  - Handles graceful shutdown with Ctrl+C")
        sys.exit(1)
    
    # Find all config files from the provided paths
    input_paths = sys.argv[1:]
    config_files = find_config_files(input_paths)
    
    if not config_files:
        print("❌ No valid config files found")
        sys.exit(1)
    
    print(f"📋 Found {len(config_files)} config files to process")
    print()
    
    processes = []
    
    print("🚴‍♂️ Starting multiple bike monitors...")
    print()
    
    # First, identify which configs need buffer initialization
    configs_needing_init = []
    configs_ready_to_start = []
    
    for config_file in config_files:
        if not Path(config_file).exists():
            print(f"❌ Config file not found: {config_file}")
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
                print(f"⚠️  Backup file already exists: {backup_file}")
                print(f"   Skipping buffer initialization for: {config_file}")
                configs_ready_to_start.append(config_file)
            else:
                print(f"📋 Config {config_file} needs buffer initialization")
                configs_needing_init.append(config_file)
        else:
            configs_ready_to_start.append(config_file)
    
    # Start monitors immediately for configs that don't need buffer initialization
    if configs_ready_to_start:
        print(f"🚀 Starting {len(configs_ready_to_start)} monitors with staggered startup...")
        
        for i, config_file in enumerate(configs_ready_to_start):
            if i > 0:  # Add delay for all monitors except the first one
                delay_minutes = 2
                print(f"   Waiting {delay_minutes} minutes before starting next monitor...")
                time.sleep(delay_minutes * 60)  # Convert minutes to seconds
            
            print(f"   Starting monitor: {config_file}")
            process = run_monitor(config_file)
            processes.append((config_file, process))
    
    # Run buffer initialization in parallel for configs that need it
    if configs_needing_init:
        print(f"🔄 Running buffer initialization for {len(configs_needing_init)} configs in parallel...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(configs_needing_init), 4)) as executor:
            # Submit all buffer initialization tasks
            future_to_config = {
                executor.submit(run_init_buffer, config_file): config_file 
                for config_file in configs_needing_init
            }
            
            # Collect results and start monitors as they complete
            for i, future in enumerate(concurrent.futures.as_completed(future_to_config)):
                config_file, success = future.result()
                if success:
                    print(f"✅ Buffer initialized for: {config_file}")
                    
                    # Add delay for monitors that start after buffer initialization
                    if i > 0:  # Add delay for all monitors except the first one
                        delay_minutes = 2
                        print(f"   Waiting {delay_minutes} minutes before starting next monitor...")
                        time.sleep(delay_minutes * 60)  # Convert minutes to seconds
                    
                    print(f"🚀 Starting monitor: {config_file}")
                    process = run_monitor(config_file)
                    processes.append((config_file, process))
                else:
                    print(f"❌ Failed to initialize buffer for: {config_file}")
                    print(f"   Skipping monitor startup for: {config_file}")
    
    if not processes:
        print("❌ No configs ready to start")
        sys.exit(1)
    
    print(f"\n✅ Started {len(processes)} monitors")
    print("Press Ctrl+C to stop all monitors")
    print()
    
    try:
        # Wait for all processes
        while True:
            # Check if any process has died
            for config_file, process in processes[:]:
                if process.poll() is not None:
                    print(f"⚠️  Monitor {config_file} stopped unexpectedly")
                    processes.remove((config_file, process))
            
            if not processes:
                print("❌ All monitors have stopped")
                break
            
            # Wait a bit before checking again
            time.sleep(5)
    
    except KeyboardInterrupt:
        print("\n🛑 Stopping all monitors...")
        
        # Terminate all processes
        for config_file, process in processes:
            print(f"Stopping: {config_file}")
            process.terminate()
        
        # Wait for processes to terminate
        for config_file, process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"Force killing: {config_file}")
                process.kill()
        
        print("✅ All monitors stopped")


if __name__ == "__main__":
    main()
