#!/usr/bin/env python3
"""
Setup script for the bike monitor system.
"""

import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_env_file():
    """
    Create a .env file with Telegram bot configuration.
    """
    logger.info("🚴‍♂️ Bike Monitor Setup")
    logger.info("=" * 50)
    logger.info("")
    
    # Check if .env already exists
    env_file = Path('.env')
    if env_file.exists():
        response = input(".env file already exists. Overwrite? (y/N): ").lower()
        if response != 'y':
            logger.info("Setup cancelled.")
            return
    
    print("Please provide the following information:")
    print()
    
    # Get Telegram bot token
    print("1. Telegram Bot Token")
    print("   - Create a bot with @BotFather on Telegram")
    print("   - Copy the token you receive")
    bot_token = input("   Bot Token: ").strip()
    
    if not bot_token:
        print("Error: Bot token is required!")
        return
    
    # Get Telegram chat ID
    print()
    print("2. Telegram Chat ID")
    print("   - Message @userinfobot on Telegram to get your chat ID")
    print("   - Or start a chat with your bot and use the chat ID")
    chat_id = input("   Chat ID: ").strip()
    
    if not chat_id:
        print("Error: Chat ID is required!")
        return
    
    # Create .env file
    env_content = f"""# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN={bot_token}

# Your Telegram Chat ID
TELEGRAM_CHAT_ID={chat_id}
"""
    
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        
        print()
        print("✅ Telegram configuration saved to .env file!")
        print()
        print("Next steps:")
        print("1. Test your bot: python telegram_bot.py")
        print("2. Create a config file: python setup_monitor.py config")
        print("3. Start monitoring: python bike_monitor.py <config.json>")
        print()
        
    except Exception as e:
        print(f"Error creating .env file: {e}")


def create_config_file():
    """
    Create a JSON configuration file for a monitor.
    """
    print("🚴‍♂️ Bike Monitor Configuration")
    print("=" * 40)
    print()
    
    # Get config file name
    config_name = input("Config file name (e.g., '2dehands_racefietsen'): ").strip()
    if not config_name:
        config_name = "bike_monitor"
    
    config_file = f"{config_name}.json"
    
    # Check if config file already exists
    if Path(config_file).exists():
        response = input(f"{config_file} already exists. Overwrite? (y/N): ").lower()
        if response != 'y':
            logger.info("Setup cancelled.")
            return
    
    print()
    print("Please provide the following information:")
    print()
    
    # Get monitoring URL
    print("1. Monitoring URL")
    print("   - Enter the 2dehands or marktplaats URL to monitor")
    print("   - Example: https://www.2dehands.be/fietsen-en-brommers/fietsen-racefietsen/")
    url = input("   URL: ").strip()
    
    if not url:
        print("Error: URL is required!")
        return
    
    # Get check interval
    print()
    print("2. Check Interval")
    print("   - How often to check for new listings (in seconds)")
    print("   - Recommended: 60 seconds (1 minute)")
    interval_input = input("   Interval in seconds (press Enter for 60): ").strip()
    
    try:
        interval = int(interval_input) if interval_input else 60
    except ValueError:
        interval = 60
    
    # Get rolling window size
    print()
    print("3. Rolling Window Size")
    print("   - Number of bikes to keep in memory to prevent false positives")
    print("   - Recommended: 450 bikes")
    max_bikes_input = input("   Max bikes (press Enter for 450): ").strip()
    
    try:
        max_bikes = int(max_bikes_input) if max_bikes_input else 450
    except ValueError:
        max_bikes = 450
    
    # Get initial pages for buffer initialization
    print()
    print("4. Initial Pages")
    print("   - Number of pages to scrape when initializing the buffer")
    print("   - Recommended: 15 pages")
    initial_pages_input = input("   Initial pages (press Enter for 15): ").strip()
    
    try:
        initial_pages = int(initial_pages_input) if initial_pages_input else 15
    except ValueError:
        initial_pages = 15
    
    # Get ongoing pages for monitoring
    print()
    print("5. Ongoing Pages")
    print("   - Number of pages to scrape during ongoing monitoring")
    print("   - Recommended: 5 pages")
    ongoing_pages_input = input("   Ongoing pages (press Enter for 5): ").strip()
    
    try:
        ongoing_pages = int(ongoing_pages_input) if ongoing_pages_input else 5
    except ValueError:
        ongoing_pages = 5
    
    # Get backup file preference
    print()
    print("6. Backup File")
    print("   - Save listings to file for debugging")
    print("   - Leave empty to disable backup")
    backup_input = input(f"   Backup file (press Enter for {config_name}_backup.json): ").strip()
    backup_file = backup_input if backup_input else f"{config_name}_backup.json"
    
    # Get log file preference
    print()
    print("7. Log File")
    print("   - File to store monitoring logs")
    log_input = input(f"   Log file (press Enter for {config_name}.log): ").strip()
    log_file = log_input if log_input else f"{config_name}.log"
    
    # Get proxy configuration (optional)
    print()
    print("8. Proxy Configuration (Optional)")
    print("   - Add proxy URLs to avoid IP blocking")
    print("   - Format: http://proxy1:port,http://proxy2:port")
    print("   - Leave empty to disable proxies")
    proxy_input = input("   Proxy URLs (comma-separated): ").strip()
    proxies = [p.strip() for p in proxy_input.split(',') if p.strip()] if proxy_input else []
    
    # Get request delay
    print()
    print("9. Request Delay")
    print("   - Delay between requests in seconds")
    print("   - Recommended: 1.0 seconds")
    delay_input = input("   Request delay (press Enter for 1.0): ").strip()
    
    try:
        request_delay = float(delay_input) if delay_input else 1.0
    except ValueError:
        request_delay = 1.0
    
    # Create config file
    config = {
        "url": url,
        "check_interval": interval,
        "max_bikes": max_bikes,
        "initial_pages": initial_pages,
        "ongoing_pages": ongoing_pages,
        "backup_file": backup_file,
        "log_file": log_file,
        "request_delay": request_delay
    }
    
    # Add proxies if configured
    if proxies:
        config["proxies"] = proxies
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print()
        print(f"✅ Configuration saved to {config_file}!")
        print()
        print("Next steps:")
        print("1. Initialize buffer: python init_buffer.py {config_file}")
        print("2. Start monitoring: python bike_monitor.py {config_file}")
        print()
        print("To run multiple monitors:")
        print("python bike_monitor.py config1.json &")
        print("python bike_monitor.py config2.json &")
        print()
        
    except Exception as e:
        print(f"Error creating config file: {e}")


def test_configuration():
    """
    Test the current configuration.
    """
    print("🧪 Testing Configuration")
    print("=" * 30)
    
    # Check if .env exists
    if not Path('.env').exists():
        print("❌ .env file not found. Run setup first.")
        return
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check required variables
    required_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return
    
    print("✅ All required environment variables found")
    
    # Test Telegram bot
    try:
        import asyncio
        from telegram_bot import TelegramBot
        
        async def test_bot():
            bot = TelegramBot(os.getenv('TELEGRAM_BOT_TOKEN'))
            bot_info = await bot.get_bot_info()
            
            if bot_info:
                print(f"✅ Bot connected: @{bot_info.get('username', 'Unknown')}")
                
                # Test message
                test_message = "🧪 Test message from Bike Monitor setup"
                success = await bot.send_message(
                    chat_id=os.getenv('TELEGRAM_CHAT_ID'),
                    message=test_message
                )
                
                if success:
                    print("✅ Test message sent successfully!")
                else:
                    print("❌ Failed to send test message")
            else:
                print("❌ Failed to connect to bot")
        
        asyncio.run(test_bot())
        
    except Exception as e:
        print(f"❌ Error testing bot: {e}")


def main():
    """
    Main setup function.
    """
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test':
            test_configuration()
        elif sys.argv[1] == 'config':
            create_config_file()
        else:
            print("Usage:")
            print("  python setup_monitor.py          # Setup Telegram bot (.env)")
            print("  python setup_monitor.py config   # Create monitor config (.json)")
            print("  python setup_monitor.py test     # Test configuration")
    else:
        create_env_file()


if __name__ == "__main__":
    main()
