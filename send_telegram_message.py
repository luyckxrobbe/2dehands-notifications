#!/usr/bin/env python3
"""
Simple script to send a Telegram message
"""

import asyncio
import os
import logging
from dotenv import load_dotenv
from telegram_bot import TelegramBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


async def send_simple_message():
    """
    Send a simple message using the Telegram bot
    """
    # Get bot token from environment variable
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        logger.error("Error: TELEGRAM_BOT_TOKEN not found in .env file")
        logger.error("Please create a .env file with your bot token")
        logger.error("Copy env_template.txt to .env and fill in your values")
        return
    
    # Get chat ID from environment variable
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not chat_id:
        logger.error("Error: TELEGRAM_CHAT_ID not found in .env file")
        logger.error("You can find your chat ID by messaging @userinfobot on Telegram")
        logger.error("Add it to your .env file")
        return
    
    # Initialize bot
    bot = TelegramBot(bot_token)
    
    # Message to send
    message = "Hello from your Python Telegram bot! 🚀"
    
    # Send the message
    logger.info(f"Sending message to chat {chat_id}...")
    success = await bot.send_message(chat_id, message)
    
    if success:
        logger.info("✅ Message sent successfully!")
    else:
        logger.error("❌ Failed to send message")


if __name__ == "__main__":
    asyncio.run(send_simple_message())
