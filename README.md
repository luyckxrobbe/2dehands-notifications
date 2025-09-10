# 🚴‍♂️ Bike Monitor System

A continuous monitoring system that checks for new bike listings on 2dehands/marktplaats every minute and sends Telegram notifications for new bikes.

## Features

- **Continuous Monitoring**: Runs every minute to check for new listings
- **Smart Notifications**: Sends formatted Telegram messages with bike details
- **Object-Oriented Design**: Clean, maintainable code structure
- **Rich Data Extraction**: Automatically extracts brand, condition, size, price
- **Comparison System**: Tracks new, removed, and updated listings
- **Error Handling**: Robust error handling and logging
- **Easy Setup**: Simple configuration process

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Configuration

Run the setup script to configure your Telegram bot:

```bash
python setup_monitor.py
```

This will guide you through:
- Creating a Telegram bot with @BotFather
- Getting your chat ID
- Setting the monitoring URL
- Configuring check interval

### 3. Test Configuration

```bash
python setup_monitor.py test
```

### 4. Start Monitoring

```bash
python bike_monitor.py
```

The monitor will:
- Send a startup notification
- Check for new listings every minute
- Send notifications for new bikes
- Log all activity to `bike_monitor.log`

## Manual Configuration

If you prefer to configure manually, create a `.env` file:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Bike Monitor Configuration
BIKE_MONITOR_URL=https://www.2dehands.be/fietsen-en-brommers/fietsen-racefietsen/
BIKE_MONITOR_OUTPUT=current_listings.json
BIKE_MONITOR_INTERVAL=60
```

## Usage Examples

### Basic Monitoring
```bash
python bike_monitor.py
```

### Custom URL and Interval
```bash
# Set environment variables
export BIKE_MONITOR_URL="https://www.marktplaats.nl/c/fietsen-en-brommers/fietsen-racefietsen/"
export BIKE_MONITOR_INTERVAL=30

python bike_monitor.py
```

### Manual Scraping with Comparison
```bash
python scrape_2dehands_live.py "https://www.2dehands.be/fietsen-en-brommers/fietsen-racefietsen/" -c current_listings.json
```

## File Structure

```
├── bike.py                 # Bike class for individual listings
├── current_listings.py     # CurrentListings class for collections
├── scrape_2dehands_live.py # Web scraper
├── bike_monitor.py         # Main monitoring script
├── telegram_bot.py         # Telegram bot integration
├── setup_monitor.py        # Setup and configuration script
├── config.env.example      # Example configuration file
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Notification Format

When a new bike is found, you'll receive a Telegram message like:

```
🚴‍♂️ New Bike Listing!

Title: Trek Domane SL 6 GEN 4
Brand: Trek
Price: € 3,299.00
Condition: Nieuw
Size: 28 inch
Location: Stabroek
Seller: Bikeselection - BMS BV
Date: Vandaag

Description: Nl & fr 12 maanden garantie! Nieuwprijs 5199,00 € nu voor 3299,00 € incl. Btw! Klik op onderstaande link voor meer i

🔗 View Listing
```

## Logging

All activity is logged to `bike_monitor.log` with timestamps. The log includes:
- Startup/shutdown events
- Scraping results
- New listings found
- Notification status
- Errors and warnings

## Stopping the Monitor

Press `Ctrl+C` to gracefully stop the monitor. It will:
- Stop the monitoring loop
- Send a shutdown notification
- Clean up resources

## Troubleshooting

### Bot Token Issues
- Make sure you created a bot with @BotFather
- Copy the token exactly as provided
- Ensure the token is in your `.env` file

### Chat ID Issues
- Message @userinfobot on Telegram to get your chat ID
- Make sure you've started a conversation with your bot
- Use the numeric chat ID (not username)

### Scraping Issues
- Check if the URL is accessible
- Verify the website hasn't changed its structure
- Check the logs for specific error messages

### Rate Limiting
- The monitor includes delays between messages to avoid rate limiting
- If you get rate limited, increase the check interval

## Advanced Usage

### Filtering Bikes
You can modify the monitoring script to filter bikes by:
- Price range
- Brand
- Condition
- Location
- Frame size

### Multiple URLs
To monitor multiple URLs, run multiple instances of the monitor with different configuration files.

### Custom Notifications
Modify the `format_bike_message()` method in `bike_monitor.py` to customize notification format.

## Dependencies

- `playwright` - Web scraping
- `python-telegram-bot` - Telegram integration
- `python-dotenv` - Environment variable management
- `asyncio` - Asynchronous programming

## License

This project is for personal use. Please respect the terms of service of the websites you're scraping.
