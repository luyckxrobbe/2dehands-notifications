#!/usr/bin/env python3
"""
Migration script to convert existing backup files to minimal format.
"""

import json
import shutil
from pathlib import Path
from bike import Bike
from bike_minimal import BikeMinimal, BikeMinimalListings
from centralized_logging import setup_logging, get_logger

# Configure logging
setup_logging()
logger = get_logger(__name__)


def migrate_backup_file(backup_file: Path) -> bool:
    """
    Migrate a single backup file to minimal format.
    
    Args:
        backup_file: Path to the backup file to migrate
        
    Returns:
        True if migration successful, False otherwise
    """
    if not backup_file.exists():
        logger.warning(f"Backup file does not exist: {backup_file}")
        return False
    
    # Create backup of original file
    backup_original = backup_file.with_suffix('.backup')
    shutil.copy2(backup_file, backup_original)
    logger.info(f"Created backup of original: {backup_original}")
    
    try:
        # Load original backup file
        with open(backup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert to minimal format
        minimal_bikes = []
        for item in data:
            if isinstance(item, dict):
                # Create full bike object first
                full_bike = Bike.from_dict(item)
                # Convert to minimal format
                minimal_bike = BikeMinimal(
                    title=full_bike.title,
                    price=full_bike.price,
                    href=full_bike.href,
                    scraped_at=full_bike._scraped_at
                )
                minimal_bikes.append(minimal_bike)
        
        # Create minimal listings
        minimal_listings = BikeMinimalListings(minimal_bikes)
        
        # Save minimal version
        minimal_listings.to_json_file(backup_file)
        
        # Calculate size reduction
        original_size = backup_original.stat().st_size
        minimal_size = backup_file.stat().st_size
        reduction = ((original_size - minimal_size) / original_size) * 100
        
        logger.info(f"✅ Migrated {backup_file.name}")
        logger.info(f"   Original size: {original_size / 1024 / 1024:.2f} MB")
        logger.info(f"   Minimal size: {minimal_size / 1024 / 1024:.2f} MB")
        logger.info(f"   Size reduction: {reduction:.1f}%")
        logger.info(f"   Bikes: {len(minimal_bikes)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error migrating {backup_file}: {e}")
        # Restore original file
        shutil.copy2(backup_original, backup_file)
        logger.info(f"Restored original file from backup")
        return False


def main():
    """Migrate all backup files to minimal format."""
    logger.info("🔄 Starting migration to minimal backup format...")
    
    # Find all backup files
    backup_dir = Path("backups")
    if not backup_dir.exists():
        logger.warning("No backups directory found")
        return
    
    backup_files = list(backup_dir.glob("*.json"))
    if not backup_files:
        logger.warning("No backup files found")
        return
    
    logger.info(f"Found {len(backup_files)} backup files to migrate")
    
    successful = 0
    failed = 0
    
    for backup_file in backup_files:
        logger.info(f"\n📁 Processing: {backup_file.name}")
        
        if migrate_backup_file(backup_file):
            successful += 1
        else:
            failed += 1
    
    logger.info(f"\n📊 Migration Summary:")
    logger.info(f"   ✅ Successful: {successful}")
    logger.info(f"   ❌ Failed: {failed}")
    logger.info(f"   📁 Total: {len(backup_files)}")
    
    if successful > 0:
        logger.info("\n🎉 Migration completed! Backup files now use minimal format.")
        logger.info("   - Only essential fields stored (title, price, href, scraped_at)")
        logger.info("   - Significant size reduction achieved")
        logger.info("   - All details still available via individual page scraping")
        logger.info("   - Original files backed up with .backup extension")


if __name__ == "__main__":
    main()
