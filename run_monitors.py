#!/usr/bin/env python3
"""
Script to run multiple bike monitors simultaneously.
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import List


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


def main():
    """
    Main function to run multiple monitors.
    """
    if len(sys.argv) < 2:
        print("Usage: python run_monitors.py <config1.json> [config2.json] ...")
        print()
        print("Examples:")
        print("  python run_monitors.py configs/2dehands_racefietsen.json")
        print("  python run_monitors.py configs/*.json")
        print("  python run_monitors.py configs/2dehands_racefietsen.json configs/marktplaats_racefietsen.json")
        sys.exit(1)
    
    config_files = sys.argv[1:]
    processes = []
    
    print("🚴‍♂️ Starting multiple bike monitors...")
    print()
    
    # Start all monitors
    for config_file in config_files:
        if not Path(config_file).exists():
            print(f"❌ Config file not found: {config_file}")
            continue
        
        print(f"Starting monitor: {config_file}")
        process = run_monitor(config_file)
        processes.append((config_file, process))
    
    if not processes:
        print("❌ No valid config files found")
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
            import time
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
