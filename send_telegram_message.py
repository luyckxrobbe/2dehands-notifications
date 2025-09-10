#!/usr/bin/env python3
"""
Simple script to send a Telegram message
"""

import asyncio
import os
from dotenv import load_dotenv
from telegram_bot import TelegramBot

# Load environment variables from .env file
load_dotenv()


async def send_simple_message():
    """
    Send a simple message using the Telegram bot
    """
    # Get bot token from environment variable
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env file")
        print("Please create a .env file with your bot token")
        print("Copy env_template.txt to .env and fill in your values")
        return
    
    # Get chat ID from environment variable
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not chat_id:
        print("Error: TELEGRAM_CHAT_ID not found in .env file")
        print("You can find your chat ID by messaging @userinfobot on Telegram")
        print("Add it to your .env file")
        return
    
    # Initialize bot
    bot = TelegramBot(bot_token)
    
    # Message to send
    message = "Hello from your Python Telegram bot! 🚀"
    
    # Send the message
    print(f"Sending message to chat {chat_id}...")
    success = await bot.send_message(chat_id, message)
    
    if success:
        print("✅ Message sent successfully!")
    else:
        print("❌ Failed to send message")


if __name__ == "__main__":
    asyncio.run(send_simple_message())
